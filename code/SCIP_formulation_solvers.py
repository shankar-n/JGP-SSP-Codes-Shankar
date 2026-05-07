
import itertools
from pyscipopt import Model, quicksum
import networkx as nx

def solve_jgp_arf(n_jobs, n_tools, cap, tool_req):
        """
        Solve the Job Grouping Problem via the ARF MILP formulation
        (Catanzaro et al. 2015 / Felipe's branch-and-cut thesis).

        Minimises the number of batches  k  such that every batch
        fits within magazine capacity  cap.

        Returns
        -------
        obj_val : float  — optimal number of batches
        batches : list of (job_list, tool_list) tuples
        """
        mdl = Model("JGP_ARF")
        mdl.hideOutput()

        # v[i, h] = 1 iff job i is in batch h   (h <= i, ARF indexing)
        v = {}
        for i in range(n_jobs):
            for h in range(i + 1):          # h in {0, ..., i}
                v[i, h] = mdl.addVar(vtype="B", name=f"v_{i}_{h}")

        # y[t, h] = 1 iff tool t is loaded in batch h
        y = {}
        for t in range(n_tools):
            for h in range(n_jobs):
                y[t, h] = mdl.addVar(vtype="B", name=f"y_{t}_{h}")

        # Objective: minimise number of active batches
        mdl.setObjective(
            quicksum(v[h, h] for h in range(n_jobs)), "minimize"
        )

        # Each job assigned to exactly one batch
        for i in range(n_jobs):
            mdl.addCons(
                quicksum(v[i, h] for h in range(i + 1)) == 1,
                f"Assign_{i}"
            )

        for i in range(n_jobs):
            for h in range(i + 1):
                # Batch h must be active if job i is in it
                mdl.addCons(v[i, h] <= v[h, h], f"Active_{i}_{h}")
                # If job i in batch h, all its tools must be in batch h
                for t in tool_req[i]:
                    mdl.addCons(v[i, h] <= y[t, h], f"ToolReq_{i}_{h}_{t}")

        # Capacity of each batch
        for h in range(n_jobs):
            mdl.addCons(
                quicksum(y[t, h] for t in range(n_tools)) <= cap * v[h, h],
                f"Cap_{h}"
            )

        mdl.optimize()

        if mdl.getStatus() != "optimal":
            print(f"WARNING: JGP solver status = {mdl.getStatus()}")
            return None, []

        # ── Extract batches ──────────────────────────────────────────────
        # BUG FIX: must check ALL jobs (range(n_jobs)), not range(h, n_jobs)
        batches = []
        for h in range(n_jobs):
            if mdl.getVal(v[h, h]) > 0.5:
                jobs_in_h  = [i for i in range(h,n_jobs) #added h, find out [TODO]
                              if mdl.getVal(v[i, h]) > 0.5]
                tools_in_h = [t for t in range(n_tools)
                              if mdl.getVal(y[t, h]) > 0.5]
                batches.append((jobs_in_h, tools_in_h))

        return float(mdl.getObjVal()), batches



def solve_ssp_gtsp(n_jobs, n_tools, cap, tool_req, verbose=True):
        """
        Solve the SSP exactly via the configuration-based GTSP MILP with
        the Intersecting-to-Nonintersecting (I-N) transformation.

        The I-N transformation introduces a DUMMY job to convert the
        Hamiltonian cycle required by GTSP into an open Hamiltonian path
        (which is what SSP needs).

        Returns
        -------
        obj_val  : float — minimum total switch cost
        ssp_route: list of (config_tuple, job_index) pairs
                   in sequence order, DUMMY excluded
        """
        if verbose:
            print("\n── GTSP/SSP Solver (I-N Transformation) ─────────────────")

        # ── 1. Build configuration clusters ─────────────────────────────
        all_configs = list(itertools.combinations(range(n_tools), cap))
        if verbose:
            print(f"   Config space: C({n_tools},{cap}) = {len(all_configs)}")

        # H_j[j] = list of configs that can serve job j
        H_j = {j: [] for j in range(n_jobs)}
        for cfg in all_configs:
            cfg_set = set(cfg)
            for j in range(n_jobs):
                if set(tool_req[j]).issubset(cfg_set):
                    H_j[j].append(cfg)

        for j in range(n_jobs):
            if not H_j[j]:
                raise ValueError(
                    f"Job {j} requires tools {tool_req[j]} "
                    f"but no config of size {cap} covers them."
                )

        # ── 2. I-N Transformation: add dummy job ─────────────────────────
        DUMMY = n_jobs          # index of dummy job
        DUMMY_CFG = "DUMMY"     # sentinel config value (not a tuple)
        H_j[DUMMY] = [DUMMY_CFG]
        nodes = list(range(n_jobs + 1))  # real jobs + dummy

        def switch_cost(cfg_a, cfg_b):
            """Switch cost between two configurations (0 if either is DUMMY)."""
            if cfg_a == DUMMY_CFG or cfg_b == DUMMY_CFG:
                return 0
            return cap - len(set(cfg_a).intersection(set(cfg_b)))

        # ── 3. Build MILP ────────────────────────────────────────────────
        mdl = Model("SSP_GTSP_IN")
        mdl.hideOutput()

        # y[cfg, j] = 1 iff configuration cfg is used for job j
        y = {}
        for j in nodes:
            for cfg in H_j[j]:
                y[cfg, j] = mdl.addVar(vtype="B", name=f"y_{j}_{id(cfg)}")

        # x[cfg_i, i, cfg_j, j] = 1 iff transition i→j with configs cfg_i→cfg_j
        x = {}
        for i in nodes:
            for j in nodes:
                if i == j:
                    continue
                for ci in H_j[i]:
                    for cj in H_j[j]:
                        x[ci, i, cj, j] = mdl.addVar(
                            vtype="B", name=f"x_{i}_{j}_{id(ci)}_{id(cj)}"
                        )

        # Objective: minimise total switch cost
        mdl.setObjective(
            quicksum(
                switch_cost(ci, cj) * x[ci, i, cj, j]
                for i in nodes for j in nodes if i != j
                for ci in H_j[i] for cj in H_j[j]
            ),
            "minimize"
        )

        # Constraint: each node visited exactly once
        for j in nodes:
            mdl.addCons(
                quicksum(y[cfg, j] for cfg in H_j[j]) == 1,
                f"Cover_{j}"
            )

        # Flow conservation: out-degree == y[cfg,j]
        for j in nodes:
            for cfg in H_j[j]:
                mdl.addCons(
                    quicksum(x[cfg, j, cj2, j2]
                             for j2 in nodes if j2 != j
                             for cj2 in H_j[j2]) == y[cfg, j],
                    f"FlowOut_{j}_{id(cfg)}"
                )
                # Flow conservation: in-degree == y[cfg,j]
                mdl.addCons(
                    quicksum(x[ci2, j2, cfg, j]
                             for j2 in nodes if j2 != j
                             for ci2 in H_j[j2]) == y[cfg, j],
                    f"FlowIn_{j}_{id(cfg)}"
                )

        # GSEC: for every proper non-empty subset S of real jobs,
        # number of internal arcs <= |active configs in H(S)| - 1
        # (prevents sub-tours among clusters)
        job_set = set(range(n_jobs))   # real jobs only (no dummy in GSEC)
        for r in range(2, n_jobs):
            for S in itertools.combinations(job_set, r):
                S_set = set(S)
                mdl.addCons(
                    quicksum(
                        x[ci, i, cj, j]
                        for i in S_set for j in S_set if i != j
                        for ci in H_j[i] for cj in H_j[j]
                    ) <= quicksum(
                        y[cfg, j] for j in S_set for cfg in H_j[j]
                    ) - 1,
                    f"GSEC_{'_'.join(map(str, S))}"
                )

        # ── 4. Solve ─────────────────────────────────────────────────────
        if verbose:
            print("   Solving… (this may take a moment for larger instances)")
        mdl.optimize()
        status = mdl.getStatus()
        if verbose:
            print(f"   Solver status: {status}")

        if status != "optimal":
            print(f"WARNING: SSP solver status = {status}")
            return None, []

        obj_val = float(mdl.getObjVal())
        if verbose:
            print(f"   Objective (total switches): {obj_val}")

        # ── 5. Reconstruct path ──────────────────────────────────────────
        # Collect active edges as dict: node → next_node
        active_edges = {}
        for i in nodes:
            for j in nodes:
                if i == j:
                    continue
                for ci in H_j[i]:
                    for cj in H_j[j]:
                        if mdl.getVal(x[ci, i, cj, j]) > 0.5:
                            active_edges[(ci, i)] = (cj, j)

        # Find the node representing the DUMMY job (start of the path)
        start_node = (DUMMY_CFG, DUMMY)
        if start_node not in active_edges:
            # Try to find it as a destination (the path may enter dummy first)
            for src, dst in active_edges.items():
                if dst[1] == DUMMY:
                    start_node = dst
                    break

        # Traverse from dummy: dummy → job_1 → job_2 → ... → job_n → dummy
        ssp_route = []
        curr = start_node
        visited = set()
        for _ in range(n_jobs + 2):  # at most n+1 steps + dummy
            next_node = active_edges.get(curr)
            if next_node is None:
                break
            visited.add(curr)
            if next_node[1] == DUMMY:
                break                   # back to dummy: path complete
            ssp_route.append(next_node)
            curr = next_node
            if curr in visited:
                break

        if verbose:
            print(f"   Route ({len(ssp_route)} jobs): "
                  f"{[f'j{r[1]+1}' for r in ssp_route]}")

        return obj_val, ssp_route



def solve_ssp_tang_denardo_crama(num_jobs, num_tools, b, A, T_j):
    """
    Solves the SSP using the classic positional Mixed Integer Linear Program (Formulation 1).
    """
    J = list(range(num_jobs))  # 0 to n-1
    T = list(range(num_tools)) # 0 to m-1
    K = list(range(num_jobs))  # Sequence positions 0 to n-1

    model = Model("SSP_TangDenardo_Crama")
    model.hideOutput()

    y = {} 
    z = {} 
    w = {} 
    for k in K:
        for t in T:
            z[t, k] = model.addVar(vtype="B", name=f"z_{t}_{k}")
            w[t, k] = model.addVar(vtype="B", name=f"w_{t}_{k}")
        for j in J:
            y[j, k] = model.addVar(vtype="B", name=f"y_{j}_{k}")

    model.setObjective(quicksum(w[t, k] for t in T for k in K), "minimize")

    for j in J:
        model.addCons(quicksum(y[j, k] for k in K) == 1)
    for k in K:
        model.addCons(quicksum(y[j, k] for j in J) == 1)
        model.addCons(quicksum(z[t, k] for t in T) <= b)
        for j in J:
            for t in T_j[j]:
                model.addCons(z[t, k] >= y[j, k])

    for t in T:
        model.addCons(w[t, 0] >= z[t, 0])
        for k in range(1, num_jobs):
            model.addCons(w[t, k] >= z[t, k] - z[t, k-1])

    model.optimize()
    if model.getStatus() == "optimal":
        obj_val = model.getObjVal()
        route = [j for k in K for j in J if model.getVal(y[j, k]) > 0.5]
        return obj_val, route
    return None, None


def solve_ssp_laporte(num_jobs, num_tools, b, A, T_j):
    """
    Solves the SSP using Laporte's graph-based formulation (Formulation 2).
    """

    # Map the 0-indexed T_j to 1-indexed jobs, leaving 0 for the dummy depot
    T_req = {j: T_j[j-1] for j in range(1, num_jobs + 1)}
    T_req = [] 

    J0 = list(range(num_jobs + 1))
    J = list(range(1, num_jobs + 1))
    T = list(range(num_tools))

    model = Model("SSP_Laporte")
    model.hideOutput()

    x = {(i, j): model.addVar(vtype="B", name=f"x_{i}_{j}") for i in J0 for j in J0 if i != j}
    y = {(j, t): model.addVar(vtype="B", name=f"y_{j}_{t}") for j in J for t in T}
    z = {(j, t): model.addVar(vtype="B", name=f"z_{j}_{t}") for j in J for t in T}

    model.setObjective(quicksum(z[j, t] for j in J for t in T), "minimize")

    for i in J0:
        model.addCons(quicksum(x[i, j] for j in J0 if i != j) == 1)
    for j in J0:
        model.addCons(quicksum(x[i, j] for i in J0 if i != j) == 1)

    for j in J:
        model.addCons(quicksum(y[j, t] for t in T) <= b)
        for t in T:
            if t in T_req[j]:
                model.addCons(y[j, t] == 1) 
            else:
                model.addCons(z[j, t] == 0) 

            model.addCons(x[0, j] + y[j, t] <= z[j, t] + 1)
            for i in J:
                if i != j:
                    model.addCons(x[i, j] + y[j, t] - y[i, t] <= z[j, t] + 1)

    while True:
        model.optimize()
        if model.getStatus() != "optimal": return None, None

        active_edges = [(i, j) for (i, j) in x if model.getVal(x[i, j]) > 0.5]
        G = nx.DiGraph()
        G.add_edges_from(active_edges)
        cycles = list(nx.simple_cycles(G))

        if len(cycles) == 1 and len(cycles) == num_jobs + 1: break

        model.freeTransform() 
        for cycle in cycles:
            if len(cycle) < num_jobs + 1:
                edges_internal = quicksum(x[i, j] for i in cycle for j in cycle if i != j)
                model.addCons(edges_internal <= len(cycle) - 1)

    route = []
    curr = 0
    while True:
        next_node = [j for (i, j) in active_edges if i == curr]
        if next_node == 0: break
        route.append(next_node - 1) # Shift back to 0-indexed for output
        curr = next_node

    return model.getObjVal(), route

def solve_ssp_catanzaro(num_jobs, num_tools, b, A, T_j):
    """
    Solves the SSP using the tightened Catanzaro Formulation 4.
    """
    # Map the 0-indexed T_j to 1-indexed jobs for the dummy depot
    T_req = {j: T_j[j-1] for j in range(1, num_jobs + 1)}
    T_req = [] 

    J0 = list(range(num_jobs + 1))
    J = list(range(1, num_jobs + 1))
    T = list(range(num_tools))

    model = Model("SSP_Catanzaro")
    model.hideOutput()

    x = {(i, j): model.addVar(vtype="B", name=f"x_{i}_{j}") for i in J0 for j in J0 if i != j}
    Y = {(i, j, t): model.addVar(vtype="B", name=f"Y_{i}_{j}_{t}") for i in J0 for j in J0 if i != j for t in T}

    obj = quicksum(len(T_req[j]) * x[0, j] for j in J)
    for i in J:
        for j in J:
            if i != j:
                for t in T_req[j]:
                    if t not in T_req[i]:
                        obj += (x[i, j] - Y[i, j, t])
    model.setObjective(obj, "minimize")

    for i in J0:
        model.addCons(quicksum(x[i, j] for j in J0 if i != j) == 1)
    for j in J0:
        model.addCons(quicksum(x[i, j] for i in J0 if i != j) == 1)

    for i in J0:
        for j in J0:
            if i != j:
                model.addCons(quicksum(Y[i, j, t] for t in T if t not in T_req[j]) <= (b - len(T_req[j])) * x[i, j])
                for t in T:
                    model.addCons(Y[i, j, t] <= x[i, j])
                    if t in T_req[i] and t in T_req[j]:
                        model.addCons(Y[i, j, t] == x[i, j]) 

    for i in J0:
        for t in T:
            if t not in T_req[i]:
                model.addCons(quicksum(Y[k, i, t] for k in J0 if k != i) - 
                                quicksum(Y[i, j, t] for j in J0 if j != i) >= 0)

    while True:
        model.optimize()
        if model.getStatus() != "optimal": return None, None

        active_edges = [(i, j) for (i, j) in x if model.getVal(x[i, j]) > 0.5]
        G = nx.DiGraph()
        G.add_edges_from(active_edges)
        cycles = list(nx.simple_cycles(G))

        if len(cycles) == 1 and len(cycles) == num_jobs + 1: break

        model.freeTransform()
        for cycle in cycles:
            if len(cycle) < num_jobs + 1:
                edges_internal = quicksum(x[i, j] for i in cycle for j in cycle if i != j)
                model.addCons(edges_internal <= len(cycle) - 1)

    route = []
    curr = 0
    while True:
        next_node = [j for (i, j) in active_edges if i == curr]
        if next_node == 0: break
        route.append(next_node - 1) # Shift back to 0-indexed
        curr = next_node

    return model.getObjVal(), route