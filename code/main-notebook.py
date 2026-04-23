# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "marimo>=0.23.2",
# ]
# ///

import marimo

__generated_with = "0.23.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import re
    import numpy as np
    import pandas as pd
    import marimo as mo
    import matplotlib.pyplot as plt
    import seaborn as sns
    import networkx as nx
    from matplotlib.colors import ListedColormap
    import itertools
    from pyscipopt import Model, quicksum


    return ListedColormap, Model, itertools, np, nx, pd, plt, quicksum, sns


@app.cell
def _():
    instances_pth = './Instances_from_felipe/data/';
    sample_instance =  'Catanzaro/Tabela1C/A0-0.txt';
    return instances_pth, sample_instance


@app.cell
def _(instances_pth, np, sample_instance):
    file = instances_pth + sample_instance;
    shankar_example_file = './shankar-example.txt'

    # file = shankar_example_file

    with open(file,'r') as f:
        s = f.read();
        matrix = list([[int(x) for x in el.split()] for el in s.splitlines() if el.strip()]);
        matrix = sum(matrix,[])
        J = matrix[0];
        T = matrix[1];
        C = matrix[2];
        matrix = np.array(matrix[3:])
        matrix = matrix.reshape((T,J));
    return C, J, T, matrix


@app.cell
def _(C, J, T, matrix, pd):
    row_names = ["Tool_" + str(x+1) for x in range(T)];
    col_names = ["Job_" + str(x+1) for x in range(J)];

    df = pd.DataFrame(
        matrix,
        index=row_names,
        columns=col_names
    )

    # styled = df.style.set_table_styles([
    #     {
    #         "selector": "th.col_heading",
    #         "props": [("background-color", "#40466e"),
    #                   ("color", "white")]
    #     },
    #     {
    #         "selector": "th.row_heading",
    #         "props": [("background-color", "#6c757d"),
    #                   ("color", "white")]
    #     }
    # ])

    styled = df.style.map(
        lambda v: "background-color: lightblue" if v > 0 else ""
    )

    # latex = styled.to_latex()
    print(f"{J} Jobs, {T} Tools, {C} Capacity")
    styled
    return


@app.cell
def _(C, matrix):
    A = matrix
    num_tools, num_jobs = A.shape
    b = C # Magazine capacity

    T_j = {j: [i for i, val in enumerate(A[:, j]) if val == 1] for j in range(num_jobs)}
    return A, T_j, b, num_jobs, num_tools


@app.cell
def _(Model, quicksum):
    # ==========================================
    # 2. FELIPE'S ARF MODEL FOR JGP [3]
    # ==========================================
    def solve_jgp_arf(num_jobs, num_tools, b, T_j):
        model = Model("JGP_ARF")
        model.hideOutput() # Hide SCIP logs for clean output

        # Variables
        v = {} # v[i,h] = 1 if job i is in group h
        y = {} # y[t,h] = 1 if tool t is in group h

        for i in range(num_jobs):
            for h in range(i + 1):
                v[i, h] = model.addVar(vtype="B", name=f"v_{i}_{h}")
        for t in range(num_tools):
            for h in range(num_jobs):
                y[t, h] = model.addVar(vtype="B", name=f"y_{t}_{h}")

        # Objective: Minimize active groups (v_hh)
        model.setObjective(quicksum(v[h, h] for h in range(num_jobs)), "minimize")

        # Constraints [3]
        for i in range(num_jobs):
            model.addCons(quicksum(v[i, h] for h in range(i + 1)) == 1, f"Assign_{i}")
            for h in range(i + 1):
                model.addCons(v[i, h] <= v[h, h], f"GroupActive_{i}_{h}")
                for t in T_j[i]:
                    model.addCons(v[i, h] <= y[t, h], f"ToolReq_{i}_{h}_{t}")

        for h in range(num_jobs):
            model.addCons(quicksum(y[t, h] for t in range(num_tools)) <= b * v[h, h], f"Capacity_{h}")

        model.optimize()

        # Extract batches
        batches = []
        if model.getStatus() == "optimal":
            for h in range(num_jobs):
                if model.getVal(v[h, h]) > 0.5:
                    jobs_in_h = [i for i in range(h, num_jobs) if model.getVal(v[i, h]) > 0.5]
                    tools_in_h = [t for t in range(num_tools) if model.getVal(y[t, h]) > 0.5]
                    batches.append((jobs_in_h, tools_in_h))
        return model.getObjVal(), batches


    return (solve_jgp_arf,)


@app.cell
def _(Model, itertools, quicksum):
    def solve_ssp_gtsp_disjoint(num_jobs, num_tools, b, A, T_j):
            print("\n--- Starting Disjoint GTSP Solver (Path Formulation) ---")
            print(f"Jobs: {num_jobs}, Tools: {num_tools}, Capacity: {b}")

            # 1. Generate all valid configurations of size b
            all_tools = list(range(num_tools))
            all_configs = list(itertools.combinations(all_tools, b))

            # 2. Apply the I-N Transformation (Creating Disjoint Clusters)
            # Add a dummy job to break the tour into an open path
            dummy_job = num_jobs
            num_nodes = num_jobs + 1

            V_j = {j: [] for j in range(num_nodes)}

            # Populate actual jobs with valid configurations
            for conf in all_configs:
                c_set = set(conf)
                for j in range(num_jobs):
                    if set(T_j[j]).issubset(c_set):
                        V_j[j].append(conf) 

            # SAFETY CHECK: Ensure all actual jobs can be processed
            for j in range(num_jobs):
                if not V_j[j]:
                    print(f"CRITICAL ERROR: Job {j} requires more tools than capacity b={b}!")
                    return 0, []

            # Populate the dummy job with a single artificial configuration
            V_j[dummy_job].append("DUMMY_CONFIG")

            # Distance metric: 0 cost to/from the dummy job to break the cycle
            def edge_cost(Cu, i, Cv, j):
                if i == dummy_job or j == dummy_job:
                    return 0
                return b - len(set(Cu).intersection(set(Cv)))

            # 3. Model Setup
            model = Model("SSP_GTSP_Path")

            # Variables
            y = {}
            for j in range(num_nodes):
                for C in V_j[j]:
                    y[C, j] = model.addVar(vtype="B", name=f"y_{C}_{j}")

            x = {}
            for i in range(num_nodes):
                for j in range(num_nodes):
                    if i != j:
                        for Cu in V_j[i]:
                            for Cv in V_j[j]:
                                x[Cu, i, Cv, j] = model.addVar(vtype="B", name=f"x_{Cu}_{i}_{Cv}_{j}")

            # Objective
            model.setObjective(
                quicksum(edge_cost(Cu, i, Cv, j) * x[Cu, i, Cv, j] 
                         for i in range(num_nodes) for j in range(num_nodes) if i != j 
                         for Cu in V_j[i] for Cv in V_j[j]), 
                "minimize"
            )

            # Constraint 1: Exact Covering
            for j in range(num_nodes):
                model.addCons(quicksum(y[C, j] for C in V_j[j]) == 1, f"Cover_{j}")

            # Constraint 2 & 3: Flow Conservation
            for i in range(num_nodes):
                for Cu in V_j[i]:
                    model.addCons(
                        quicksum(x[Cu, i, Cv, j] for j in range(num_nodes) if j != i for Cv in V_j[j]) == y[Cu, i], 
                        f"FlowOut_{Cu}_{i}"
                    )
                    model.addCons(
                        quicksum(x[Cv, j, Cu, i] for j in range(num_nodes) if j != i for Cv in V_j[j]) == y[Cu, i], 
                        f"FlowIn_{Cu}_{i}"
                    )

            # Constraint 4: Static GSECs over disjoint clusters
            nodes_set = set(range(num_nodes))
            for r in range(2, num_nodes):
                for S in itertools.combinations(nodes_set, r):
                    edges_internal = quicksum(x[Cu, i, Cv, j] 
                                              for i in S for j in S if i != j 
                                              for Cu in V_j[i] for Cv in V_j[j])
                    model.addCons(edges_internal <= len(S) - 1, f"GSEC_{S}")

            # 4. Optimize
            print("Model built successfully. Starting optimization...")
            model.optimize()

            status = model.getStatus()
            print(f"Solver Status Finished As: {status}")

            # 5. Extract Optimal Sequence
            obj_val = 0
            ssp_route = []

            if model.getStatus() == "optimal":
                obj_val = model.getObjVal()
                print(f"Objective Value (Minimum Switches) Found: {obj_val}")

                # Extract active edges: format is ((Cu, i), (Cv, j))
                active_edges = [((Cu, i), (Cv, j)) 
                                for i in range(num_nodes) for j in range(num_nodes) if i != j 
                                for Cu in V_j[i] for Cv in V_j[j] 
                                if model.getVal(x[Cu, i, Cv, j]) == 1.0]

                if active_edges:
                    start_edge = active_edges[0]
                    curr_edge = start_edge
                    while True:
                        # Append the (Configuration, Job_Index) tuple of the starting node
                        ssp_route.append(curr_edge) 

                        # Find the edge that starts where the current edge ends
                        next_edge = next((e for e in active_edges if e[0] == curr_edge[1]), None)
                        if next_edge is None or next_edge == active_edges[0]:
                            break
                        curr_edge = next_edge 
            else:
                print("WARNING: Optimal solution was found by the solver.")

            return obj_val, ssp_route

    return (solve_ssp_gtsp_disjoint,)


@app.cell
def _():
    # def solve_ssp_gtsp_disjoint(num_jobs, num_tools, b, A, T_j):
    #     # 1. Generate all valid configurations of size b
    #     all_tools = list(range(num_tools))
    #     all_configs = list(itertools.combinations(all_tools, b))

    #     # 2. Apply the I-N Transformation (Creating Disjoint Clusters)
    #     V_j = {j: [] for j in range(num_jobs)}

    #     for conf in all_configs:
    #         c_set = set(conf)
    #         for j in range(num_jobs):
    #             if set(T_j[j]).issubset(c_set):
    #                 V_j[j].append(conf)


    #     # Distance metric
    #     def dist(Cu, Cv):
    #         return b - len(set(Cu).intersection(set(Cv)))

    #     # 3. Model Setup
    #     model = Model("SSP_GTSP_Disjoint")
    #     model.hideOutput()

    #     # Variables
    #     y = {}
    #     for j in range(num_jobs):
    #         for C in V_j[j]:
    #             y[C, j] = model.addVar(vtype="B", name=f"y_{C}_{j}")

    #     x = {}
    #     for i in range(num_jobs):
    #         for j in range(num_jobs):
    #             if i != j:
    #                 for Cu in V_j[i]:
    #                     for Cv in V_j[j]:
    #                         x[Cu, i, Cv, j] = model.addVar(vtype="B", name=f"x_{Cu}_{i}_{Cv}_{j}")

    #     # Objective
    #     model.setObjective(
    #         quicksum(dist(Cu, Cv) * x[Cu, i, Cv, j] 
    #                  for i in range(num_jobs) for j in range(num_jobs) if i != j 
    #                  for Cu in V_j[i] for Cv in V_j[j]), 
    #         "minimize"
    #     )

    #     # Constraint 1: Exact Covering
    #     for j in range(num_jobs):
    #         model.addCons(quicksum(y[C, j] for C in V_j[j]) == 1, f"Cover_{j}")

    #     # Constraint 2 & 3: Flow Conservation
    #     for i in range(num_jobs):
    #         for Cu in V_j[i]:
    #             model.addCons(
    #                 quicksum(x[Cu, i, Cv, j] for j in range(num_jobs) if j != i for Cv in V_j[j]) == y[Cu, i], 
    #                 f"FlowOut_{Cu}_{i}"
    #             )
    #             model.addCons(
    #                 quicksum(x[Cv, j, Cu, i] for j in range(num_jobs) if j != i for Cv in V_j[j]) == y[Cu, i], 
    #                 f"FlowIn_{Cu}_{i}"
    #             )

    #     # Constraint 4: Static GSECs over disjoint clusters
    #     jobs_set = set(range(num_jobs))
    #     for r in range(2, num_jobs):
    #         for S in itertools.combinations(jobs_set, r):
    #             edges_internal = quicksum(x[Cu, i, Cv, j] 
    #                                       for i in S for j in S if i != j 
    #                                       for Cu in V_j[i] for Cv in V_j[j])
    #             model.addCons(edges_internal <= len(S) - 1, f"GSEC_{S}")

    #     # 4. Optimize
    #     model.optimize()

    #     # 5. Extract Optimal Sequence
    #     obj_val = 0
    #     ssp_route = []

    #     if model.getStatus() == "optimal":
    #         obj_val = model.getObjVal()

    #         # Extract active edges: format is ((Cu, i), (Cv, j))
    #         active_edges = [((Cu, i), (Cv, j)) 
    #                         for i in range(num_jobs) for j in range(num_jobs) if i != j 
    #                         for Cu in V_j[i] for Cv in V_j[j] 
    #                         if model.getVal(x[Cu, i, Cv, j]) == 1.0]

    #         # Reconstruct path sequentially
    #         if active_edges:
    #             start_edge = active_edges[0]
    #             curr_edge = start_edge
    #             while True:
    #                 # Append the (Configuration, Job_Index) tuple of the starting node
    #                 ssp_route.append(curr_edge) 

    #                 # Find the edge that starts where the current edge ends
    #                 next_edge = next((e for e in active_edges if e[0] == curr_edge[1]), None)
    #                 if next_edge is None or next_edge == active_edges[0]:
    #                     break
    #                 curr_edge = next_edge

    #     return obj_val, ssp_route
    return


@app.cell
def _():

    # def solve_ssp_tang_denardo_crama(num_jobs, num_tools, b, A, T_j):
    #     """
    #     Solves the SSP using the classic positional Mixed Integer Linear Program (Formulation 1).
    #     """
    #     J = list(range(num_jobs))  # 0 to n-1
    #     T = list(range(num_tools)) # 0 to m-1
    #     K = list(range(num_jobs))  # Sequence positions 0 to n-1

    #     model = Model("SSP_TangDenardo_Crama")
    #     model.hideOutput()

    #     y = {} 
    #     z = {} 
    #     w = {} 
    #     for k in K:
    #         for t in T:
    #             z[t, k] = model.addVar(vtype="B", name=f"z_{t}_{k}")
    #             w[t, k] = model.addVar(vtype="B", name=f"w_{t}_{k}")
    #         for j in J:
    #             y[j, k] = model.addVar(vtype="B", name=f"y_{j}_{k}")

    #     model.setObjective(quicksum(w[t, k] for t in T for k in K), "minimize")

    #     for j in J:
    #         model.addCons(quicksum(y[j, k] for k in K) == 1)
    #     for k in K:
    #         model.addCons(quicksum(y[j, k] for j in J) == 1)
    #         model.addCons(quicksum(z[t, k] for t in T) <= b)
    #         for j in J:
    #             for t in T_j[j]:
    #                 model.addCons(z[t, k] >= y[j, k])

    #     for t in T:
    #         model.addCons(w[t, 0] >= z[t, 0])
    #         for k in range(1, num_jobs):
    #             model.addCons(w[t, k] >= z[t, k] - z[t, k-1])

    #     model.optimize()
    #     if model.getStatus() == "optimal":
    #         obj_val = model.getObjVal()
    #         route = [j for k in K for j in J if model.getVal(y[j, k]) > 0.5]
    #         return obj_val, route
    #     return None, None
    return


@app.cell
def _():

    # def solve_ssp_laporte(num_jobs, num_tools, b, A, T_j):
    #     """
    #     Solves the SSP using Laporte's graph-based formulation (Formulation 2).
    #     """

    #     # Map the 0-indexed T_j to 1-indexed jobs, leaving 0 for the dummy depot
    #     T_req = {j: T_j[j-1] for j in range(1, num_jobs + 1)}
    #     T_req = [] 

    #     J0 = list(range(num_jobs + 1))
    #     J = list(range(1, num_jobs + 1))
    #     T = list(range(num_tools))

    #     model = Model("SSP_Laporte")
    #     model.hideOutput()

    #     x = {(i, j): model.addVar(vtype="B", name=f"x_{i}_{j}") for i in J0 for j in J0 if i != j}
    #     y = {(j, t): model.addVar(vtype="B", name=f"y_{j}_{t}") for j in J for t in T}
    #     z = {(j, t): model.addVar(vtype="B", name=f"z_{j}_{t}") for j in J for t in T}

    #     model.setObjective(quicksum(z[j, t] for j in J for t in T), "minimize")

    #     for i in J0:
    #         model.addCons(quicksum(x[i, j] for j in J0 if i != j) == 1)
    #     for j in J0:
    #         model.addCons(quicksum(x[i, j] for i in J0 if i != j) == 1)

    #     for j in J:
    #         model.addCons(quicksum(y[j, t] for t in T) <= b)
    #         for t in T:
    #             if t in T_req[j]:
    #                 model.addCons(y[j, t] == 1) 
    #             else:
    #                 model.addCons(z[j, t] == 0) 

    #             model.addCons(x[0, j] + y[j, t] <= z[j, t] + 1)
    #             for i in J:
    #                 if i != j:
    #                     model.addCons(x[i, j] + y[j, t] - y[i, t] <= z[j, t] + 1)

    #     while True:
    #         model.optimize()
    #         if model.getStatus() != "optimal": return None, None

    #         active_edges = [(i, j) for (i, j) in x if model.getVal(x[i, j]) > 0.5]
    #         G = nx.DiGraph()
    #         G.add_edges_from(active_edges)
    #         cycles = list(nx.simple_cycles(G))

    #         if len(cycles) == 1 and len(cycles) == num_jobs + 1: break

    #         model.freeTransform() 
    #         for cycle in cycles:
    #             if len(cycle) < num_jobs + 1:
    #                 edges_internal = quicksum(x[i, j] for i in cycle for j in cycle if i != j)
    #                 model.addCons(edges_internal <= len(cycle) - 1)

    #     route = []
    #     curr = 0
    #     while True:
    #         next_node = [j for (i, j) in active_edges if i == curr]
    #         if next_node == 0: break
    #         route.append(next_node - 1) # Shift back to 0-indexed for output
    #         curr = next_node

    #     return model.getObjVal(), route
    return


@app.cell
def _():

    # def solve_ssp_catanzaro(num_jobs, num_tools, b, A, T_j):
    #     """
    #     Solves the SSP using the tightened Catanzaro Formulation 4.
    #     """
    #     # Map the 0-indexed T_j to 1-indexed jobs for the dummy depot
    #     T_req = {j: T_j[j-1] for j in range(1, num_jobs + 1)}
    #     T_req = [] 

    #     J0 = list(range(num_jobs + 1))
    #     J = list(range(1, num_jobs + 1))
    #     T = list(range(num_tools))

    #     model = Model("SSP_Catanzaro")
    #     model.hideOutput()

    #     x = {(i, j): model.addVar(vtype="B", name=f"x_{i}_{j}") for i in J0 for j in J0 if i != j}
    #     Y = {(i, j, t): model.addVar(vtype="B", name=f"Y_{i}_{j}_{t}") for i in J0 for j in J0 if i != j for t in T}

    #     obj = quicksum(len(T_req[j]) * x[0, j] for j in J)
    #     for i in J:
    #         for j in J:
    #             if i != j:
    #                 for t in T_req[j]:
    #                     if t not in T_req[i]:
    #                         obj += (x[i, j] - Y[i, j, t])
    #     model.setObjective(obj, "minimize")

    #     for i in J0:
    #         model.addCons(quicksum(x[i, j] for j in J0 if i != j) == 1)
    #     for j in J0:
    #         model.addCons(quicksum(x[i, j] for i in J0 if i != j) == 1)

    #     for i in J0:
    #         for j in J0:
    #             if i != j:
    #                 model.addCons(quicksum(Y[i, j, t] for t in T if t not in T_req[j]) <= (b - len(T_req[j])) * x[i, j])
    #                 for t in T:
    #                     model.addCons(Y[i, j, t] <= x[i, j])
    #                     if t in T_req[i] and t in T_req[j]:
    #                         model.addCons(Y[i, j, t] == x[i, j]) 

    #     for i in J0:
    #         for t in T:
    #             if t not in T_req[i]:
    #                 model.addCons(quicksum(Y[k, i, t] for k in J0 if k != i) - 
    #                               quicksum(Y[i, j, t] for j in J0 if j != i) >= 0)

    #     while True:
    #         model.optimize()
    #         if model.getStatus() != "optimal": return None, None

    #         active_edges = [(i, j) for (i, j) in x if model.getVal(x[i, j]) > 0.5]
    #         G = nx.DiGraph()
    #         G.add_edges_from(active_edges)
    #         cycles = list(nx.simple_cycles(G))

    #         if len(cycles) == 1 and len(cycles) == num_jobs + 1: break

    #         model.freeTransform()
    #         for cycle in cycles:
    #             if len(cycle) < num_jobs + 1:
    #                 edges_internal = quicksum(x[i, j] for i in cycle for j in cycle if i != j)
    #                 model.addCons(edges_internal <= len(cycle) - 1)

    #     route = []
    #     curr = 0
    #     while True:
    #         next_node = [j for (i, j) in active_edges if i == curr]
    #         if next_node == 0: break
    #         route.append(next_node - 1) # Shift back to 0-indexed
    #         curr = next_node

    #     return model.getObjVal(), route
    return


@app.cell
def _(A, T_j, b, num_jobs, num_tools, solve_jgp_arf, solve_ssp_gtsp_disjoint):
    jgp_obj, jgp_batches = solve_jgp_arf(num_jobs, num_tools, b, T_j)
    print(f"JGP Optimal Groups (Machine Stops): {jgp_obj}")

    ssp_obj, ssp_route = solve_ssp_gtsp_disjoint(num_jobs, num_tools, b, A, T_j)
    # ssp_obj, ssp_route = solve_ssp_tang_denardo_crama(num_jobs, num_tools, b,A)

    # print(f"SSP Optimal Tool Switches: {ssp_obj}")
    return jgp_batches, ssp_route


@app.cell
def _(ssp_route):
    ssp_route
    return


@app.cell
def _(ListedColormap, np, plt, sns):
    # ==========================================
    # 1. Magazine State Timeline (JGP vs SSP)
    # ==========================================
    def plot_magazine_timeline(ssp_route, jgp_batches, num_tools, b):
        fig, axes = plt.subplots(1, 2, figsize=(16, 6))
        cmap = ListedColormap(['#F0F0F0', '#4682B4']) # White and SteelBlue

        # --- Plot 1: Rigid JGP Batches (Left Plot -> axes) ---
        jgp_matrix = np.zeros((num_tools, len(jgp_batches)))
        for step, (jobs, tools) in enumerate(jgp_batches):
            for t in tools:
                jgp_matrix[t, step] = 1

        sns.heatmap(jgp_matrix, cmap=cmap, cbar=False, linewidths=2, linecolor='white', ax=axes[0])
        axes[0].set_title('JGP: Rigid Batch Formations (Full Stops)', fontsize=14, fontweight='bold')
        axes[0].set_xlabel('Batch Sequence', fontsize=12)
        axes[0].set_ylabel('Tool Magazine', fontsize=12)
        axes[0].set_xticks(np.arange(len(jgp_batches)) + 0.5)
        axes[0].set_xticklabels([f"Batch {i+1}" for i in range(len(jgp_batches))])
        axes[0].set_yticks(np.arange(num_tools) + 0.5)
        axes[0].set_yticklabels([f"t{t+1}" for t in range(num_tools)], rotation=0)

        for i in range(1, len(jgp_batches)):
            axes[0].axvline(x=i, color='#D62728', lw=3, linestyle='--')

        # --- Plot 2: Continuous SSP Routing (Right Plot -> axes[1]) ---
        ssp_matrix = np.zeros((num_tools, len(ssp_route)))
        x_labels = []

        # Unpack the I-N transformation tuples
        for step, edge in enumerate(ssp_route):
            (config, job_idx) = edge[0]
            if(config == "DUMMY_CONFIG"):
                ssp_matrix[-1, step] = 1
            else:
                for t in config:
                    ssp_matrix[t, step] = 1
                # Label precisely which job this configuration replica is serving
            x_labels.append(f"Job {job_idx+1}\n(C_{step+1})")

        sns.heatmap(ssp_matrix, cmap=cmap, cbar=False, linewidths=2, linecolor='white', ax=axes[1])
        axes[1].set_title('SSP: Continuous Routing (Dynamic Switches)', fontsize=14, fontweight='bold')
        axes[1].set_xlabel('Processing Sequence', fontsize=12)

        axes[1].set_xticks(np.arange(len(ssp_route)) + 0.5)
        axes[1].set_xticklabels(x_labels)
        axes[1].set_yticks(np.arange(num_tools) + 0.5)
        axes[1].set_yticklabels([f"t{t+1}" for t in range(num_tools)], rotation=0)

        plt.tight_layout()
        plt.show()


    return (plot_magazine_timeline,)


@app.cell
def _(b, jgp_batches, num_tools, plot_magazine_timeline, ssp_route):
    plot_magazine_timeline(ssp_route, jgp_batches, num_tools, b)
    return


@app.cell
def _(nx, plt):
    # ==========================================
    # 2. The Configuration Transition Network
    # ==========================================
    def plot_configuration_network(ssp_route, b):
        G = nx.DiGraph()

        # Add nodes with their Job_Index as the multipartite 'subset'
        for step, edge in enumerate(ssp_route):
            (config, job_idx) = edge[0]
            node_label = f"C_{step+1}\nJob {job_idx+1}"
            G.add_node(node_label, subset=job_idx)

        # Add directed edges
        nodes = list(G.nodes())
        for i in range(len(nodes)):
            u = nodes[i]
            v = nodes[(i + 1) % len(nodes)]
            G.add_edge(u, v)

        plt.figure(figsize=(10, 6))

        # Layout by disjoint job clusters
        pos = nx.multipartite_layout(G, subset_key="subset")

        nx.draw(G, pos, with_labels=True, node_color='#4682B4', 
                node_size=2000, font_color='white', font_weight='bold', 
                arrowsize=20, edge_color='#D62728', width=2)

        plt.title("GTSP Disjoint Cluster Transition Network", fontsize=16, fontweight='bold')
        plt.show()


    return (plot_configuration_network,)


@app.cell
def _(b, plot_configuration_network, ssp_route):
    plot_configuration_network(ssp_route,b)
    return


@app.cell
def _(np, plt):
    # ==========================================
    # 3. Heuristic Improvement Trajectory
    # ==========================================
    def plot_improvement_trajectory(initial_cost, final_cost, iterations=50):
        # Simulated exponential decay trajectory for a 2-opt/Super Task heuristic
        x = np.arange(iterations)
        decay_rate = 0.1
        y = final_cost + (initial_cost - final_cost) * np.exp(-decay_rate * x)

        # Add minor noise for realism
        y += np.random.normal(0, 0.2, size=iterations) * np.exp(-decay_rate * x)
        y = np.maximum(y, final_cost) # Floor at optimum

        # Actually draw the plot!
        plt.figure(figsize=(10, 6))
        plt.plot(x, y, marker='o', linestyle='-', color='#D62728', alpha=0.7, label='Heuristic Cost')

        # Draw reference bounds
        plt.axhline(y=final_cost, color='#4682B4', linestyle='--', linewidth=2, label='Optimal SSP Bound')
        plt.axhline(y=initial_cost, color='gray', linestyle=':', linewidth=2, label='Initial JGP Bound')

        plt.title('Simulated Heuristic Improvement Trajectory', fontsize=14, fontweight='bold')
        plt.xlabel('Iterations', fontsize=12)
        plt.ylabel('Tool Switches', fontsize=12)
        plt.legend()
        plt.grid(True, linestyle='--', alpha=0.5)
        plt.tight_layout()
        plt.show()

    return (plot_improvement_trajectory,)


@app.cell
def _(plot_improvement_trajectory):
    plot_improvement_trajectory(3,4,0)
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
