<VSCode.Cell id="#VSC-setup-imports" language="mo-python">
import re
import numpy as np
import pandas as pd
import marimo as mo
import matplotlib.pyplot as plt
import seaborn as sns
import networkx as nx
from matplotlib.colors import ListedColormap
import itertools
import time
from pyscipopt import Model, quicksum
</VSCode.Cell>

<VSCode.Cell id="#VSC-file-loading" language="mo-python">
# ==========================================
# 1. FILE LOADING AND INSTANCE PREPROCESSING
# ==========================================

instances_pth = './Instances_from_felipe/data/'
sample_instance = 'Catanzaro/Tabela1C/A0-0.txt'

# File loading function
def load_ssp_instance(filepath):
    """
    Load SSP instance from standard format.
    Format: J T C (on first line) followed by T x J incidence matrix
    """
    with open(filepath, 'r') as f:
        s = f.read()
        lines = [el for el in s.splitlines() if el.strip()]
        matrix = [[int(x) for x in el.split()] for el in lines]
        matrix = sum(matrix, [])
        
        J = matrix[0]  # Number of jobs
        T = matrix[1]  # Number of tools
        C = matrix[2]  # Magazine capacity
        
        # Extract incidence matrix (T x J)
        A = np.array(matrix[3:]).reshape((T, J))
        
    return J, T, C, A

# Load instance
file = instances_pth + sample_instance
J, T, C, A = load_ssp_instance(file)

print(f"Instance loaded: {J} Jobs, {T} Tools, Capacity {C}")
print(f"Incidence matrix shape: {A.shape}")
</VSCode.Cell>

<VSCode.Cell id="#VSC-preprocessing" language="mo-python">
# ==========================================
# 2. DATA PREPROCESSING AND EXTRACTION
# ==========================================

num_tools = T
num_jobs = J
b = C
matrix = A

# Compute tool requirements per job
T_j = {j: [i for i, val in enumerate(A[:, j]) if val == 1] for j in range(num_jobs)}

# Create readable DataFrame
row_names = [f"Tool_{x+1}" for x in range(num_tools)]
col_names = [f"Job_{x+1}" for x in range(num_jobs)]

df = pd.DataFrame(
    matrix,
    index=row_names,
    columns=col_names
)

# Display styled incidence matrix
styled = df.style.map(
    lambda v: "background-color: lightblue" if v > 0 else ""
)

print(f"\n{num_jobs} Jobs, {num_tools} Tools, Capacity {b}")
print("\nIncidence Matrix (Tools x Jobs):")
styled
</VSCode.Cell>

<VSCode.Cell id="#VSC-0block-detection" language="mo-python">
# ==========================================
# 3. 0-BLOCK DETECTION AND VISUALIZATION
# ==========================================

def detect_0blocks(A):
    """
    Detect 0-blocks in incidence matrix (consecutive zeros in tool rows).
    Returns: dict mapping tool -> list of (start_job, end_job) gaps
    """
    T, J = A.shape
    blocks = {}
    
    for t in range(T):
        blocks[t] = []
        in_block = False
        block_start = None
        
        for j in range(J):
            if A[t, j] == 0:
                if not in_block:
                    in_block = True
                    block_start = j
            else:  # A[t, j] == 1
                if in_block:
                    blocks[t].append((block_start, j - 1))
                    in_block = False
        
        if in_block:
            blocks[t].append((block_start, J - 1))
    
    return blocks

blocks = detect_0blocks(A)
print("\n0-Blocks (tool gaps in sequence):")
for t, block_list in blocks.items():
    if block_list:
        print(f"  Tool {t+1}: {block_list}")
</VSCode.Cell>

<VSCode.Cell id="#VSC-viz-incidence-0blocks" language="mo-python">
# ==========================================
# 4. VISUALIZATION 1: INCIDENCE MATRIX WITH 0-BLOCKS
# ==========================================

def plot_incidence_with_0blocks(A, blocks):
    """Highlight 0-blocks in incidence matrix."""
    fig, ax = plt.subplots(figsize=(14, 8))
    
    T, J = A.shape
    sns.heatmap(A, cmap='Blues', cbar_kws={'label': '1=Required'}, ax=ax,
                xticklabels=[f'Job {j}' for j in range(J)],
                yticklabels=[f'Tool {t}' for t in range(T)],
                cbar=True)
    
    # Highlight 0-blocks with red dashed rectangles
    for t, block_list in blocks.items():
        for (start_j, end_j) in block_list:
            width = end_j - start_j + 1
            rect = plt.Rectangle((start_j, t), width, 1,
                fill=False, edgecolor='red', lw=2.5, linestyle='--')
            ax.add_patch(rect)
    
    ax.set_title('Incidence Matrix: 0-Blocks Highlighted (Tool Gaps)', 
                fontsize=14, fontweight='bold')
    ax.set_xlabel('Jobs (Sequence)', fontsize=12)
    ax.set_ylabel('Tools', fontsize=12)
    
    return fig

fig1 = plot_incidence_with_0blocks(A, blocks)
plt.tight_layout()
plt.show()
</VSCode.Cell>

<VSCode.Cell id="#VSC-jgp-solver" language="mo-python">
# ==========================================
# 5. JGP SOLVER (Calmels/Felipe ARF Model)
# ==========================================

def solve_jgp_arf(num_jobs, num_tools, b, T_j):
    """
    Solve Job Grouping Problem using ARF formulation (Felipe/Calmels).
    Returns: (objective_value, list of (jobs, tools) batches)
    """
    model = Model("JGP_ARF")
    model.hideOutput()  # Hide SCIP logs
    
    # Variables
    v = {}  # v[i,h] = 1 if job i is in group h
    y = {}  # y[t,h] = 1 if tool t is in group h
    
    for i in range(num_jobs):
        for h in range(i + 1):
            v[i, h] = model.addVar(vtype="B", name=f"v_{i}_{h}")
    
    for t in range(num_tools):
        for h in range(num_jobs):
            y[t, h] = model.addVar(vtype="B", name=f"y_{t}_{h}")
    
    # Objective: Minimize active groups
    model.setObjective(quicksum(v[h, h] for h in range(num_jobs)), "minimize")
    
    # Constraints
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

# Solve JGP
jgp_obj, jgp_batches = solve_jgp_arf(num_jobs, num_tools, b, T_j)
print(f"\nJGP Solution: {jgp_obj} batches")
for i, (jobs, tools) in enumerate(jgp_batches):
    print(f"  Batch {i+1}: Jobs {jobs} -> Tools {tools}")
</VSCode.Cell>

<VSCode.Cell id="#VSC-ssp-gtsp-solver" language="mo-python">
# ==========================================
# 6. SSP SOLVER VIA GTSP WITH I-N TRANSFORMATION
# ==========================================

def solve_ssp_gtsp_disjoint(num_jobs, num_tools, b, A, T_j):
    """
    Solve SSP via GTSP with I-N transformation (disjoint clusters).
    """
    print("\n--- GTSP Solver (I-N Transformation) ---")
    print(f"Jobs: {num_jobs}, Tools: {num_tools}, Capacity: {b}")
    
    # Generate all valid configurations of size b
    all_tools = list(range(num_tools))
    all_configs = list(itertools.combinations(all_tools, b))
    num_configs = len(all_configs)
    print(f"Config space size: {num_configs}")
    
    # Build job clusters: H_j = {C : T_j ⊆ C}
    V_j = {j: [] for j in range(num_jobs)}
    for conf in all_configs:
        c_set = set(conf)
        for j in range(num_jobs):
            if set(T_j[j]).issubset(c_set):
                V_j[j].append(conf)
    
    # Check feasibility
    for j in range(num_jobs):
        if not V_j[j]:
            print(f"ERROR: Job {j} requires more tools than capacity {b}!")
            return 0, []
    
    # Build MILP: minimize transitions
    model = Model("SSP_GTSP")
    model.hideOutput()
    
    # Variables: y[config][job] = 1 if config used for job, x[c1][c2][j1][j2] = transition
    y = {}  # y[config, job]
    x = {}  # x[config1, config2, job_from, job_to]
    
    for j in range(num_jobs):
        for c in V_j[j]:
            y[(c, j)] = model.addVar(vtype="B", name=f"y_{id(c)}_{j}")
    
    for j1 in range(num_jobs):
        for j2 in range(num_jobs):
            if j1 != j2:
                for c1 in V_j[j1]:
                    for c2 in V_j[j2]:
                        cost = b - len(set(c1).intersection(set(c2)))
                        x[(c1, c2, j1, j2)] = model.addVar(vtype="B", name=f"x_{j1}_{j2}_{id(c1)}_{id(c2)}")
    
    # Objective
    model.setObjective(
        quicksum(
            (b - len(set(c1).intersection(set(c2)))) * x[(c1, c2, j1, j2)]
            for j1 in range(num_jobs)
            for j2 in range(num_jobs)
            if j1 != j2
            for c1 in V_j[j1]
            for c2 in V_j[j2]
        ), "minimize"
    )
    
    # Coverage: each job processed exactly once
    for j in range(num_jobs):
        model.addCons(quicksum(y[(c, j)] for c in V_j[j]) >= 1, f"Cover_{j}")
    
    # Flow balance (simplified for open path)
    for j in range(num_jobs):
        model.addCons(
            quicksum(y[(c, j)] for c in V_j[j]) +
            quicksum(x[(c1, c2, j1, j)] for j1 in range(num_jobs) if j1 != j for c1 in V_j[j1] for c2 in V_j[j])
            ==
            quicksum(x[(c1, c2, j, j2)] for j2 in range(num_jobs) if j2 != j for c1 in V_j[j] for c2 in V_j[j2]),
            f"Flow_{j}"
        )
    
    model.optimize()
    
    # Extract solution
    ssp_cost = model.getObjVal()
    ssp_route = []
    
    if model.getStatus() == "optimal":
        # Reconstruct sequence
        for j in range(num_jobs):
            for c in V_j[j]:
                if model.getVal(y[(c, j)]) > 0.5:
                    ssp_route.append((c, j))
                    break
    
    return ssp_cost, ssp_route

# Solve SSP
ssp_obj, ssp_route = solve_ssp_gtsp_disjoint(num_jobs, num_tools, b, A, T_j)
print(f"\nSSP Solution: {ssp_obj} total switches")
if ssp_route:
    print("Route (first 5):", ssp_route[:5])
</VSCode.Cell>

<VSCode.Cell id="#VSC-validators" language="mo-python">
# ==========================================
# 7. SOLUTION VALIDATORS
# ==========================================

def validate_jgp_solution(batches, num_tools, b, T_j):
    """Validate JGP solution feasibility."""
    for batch_idx, (jobs, tools) in enumerate(batches):
        if len(tools) > b:
            raise ValueError(f"Batch {batch_idx}: {len(tools)} tools exceed capacity {b}")
        required = set().union(*[set(T_j[j]) for j in jobs])
        if required != set(tools):
            raise ValueError(f"Batch {batch_idx}: tool mismatch")
    return True

def validate_ssp_solution(ssp_route, num_jobs, b, T_j):
    """Validate SSP solution feasibility."""
    jobs_visited = set()
    for (config, job) in ssp_route:
        if not set(T_j[job]).issubset(set(config)):
            raise ValueError(f"Config {set(config)} cannot process job {job}")
        if len(config) > b:
            raise ValueError(f"Config exceeds capacity")
        jobs_visited.add(job)
    if jobs_visited != set(range(num_jobs)):
        raise ValueError(f"Missing jobs: {set(range(num_jobs)) - jobs_visited}")
    return True

def compute_actual_ssp_cost(ssp_route, b):
    """Compute SSP cost from route."""
    cost = 0
    prev_config = None
    for (config, job) in ssp_route:
        if prev_config:
            switches = b - len(set(prev_config).intersection(set(config)))
            cost += switches
        prev_config = config
    return cost

# Validate solutions
try:
    validate_jgp_solution(jgp_batches, num_tools, b, T_j)
    print("✓ JGP solution is feasible")
except Exception as e:
    print(f"✗ JGP validation error: {e}")

try:
    if ssp_route:
        validate_ssp_solution(ssp_route, num_jobs, b, T_j)
        actual_cost = compute_actual_ssp_cost(ssp_route, b)
        print(f"✓ SSP solution is feasible (actual cost: {actual_cost})")
except Exception as e:
    print(f"✗ SSP validation error: {e}")
</VSCode.Cell>

<VSCode.Cell id="#VSC-bounds-functions" language="mo-python">
# ==========================================
# 8. BOUNDS COMPUTATION FUNCTIONS
# ==========================================

def compute_warmstart_ub(jgp_batches, num_jobs, T_j, b):
    """Compute upper bound by warm-starting with JGP solution."""
    if not jgp_batches:
        return float('inf')
    
    # Flatten batches into sequence
    sequence = []
    for jobs, tools in jgp_batches:
        sequence.extend(jobs)
    
    # Compute SSP cost
    cost = 0
    prev_config = None
    for job_idx in sequence:
        # Find minimal config for this job
        job_config = tuple(T_j[job_idx])
        if prev_config:
            switches = b - len(set(prev_config).intersection(set(job_config)))
            cost += switches
        prev_config = job_config
    
    return cost

def compute_greedy_ffd_ub(num_jobs, T_j, b):
    """Compute upper bound via Greedy First-Fit Decreasing."""
    # Sort jobs by tool requirement size (descending)
    jobs_sorted = sorted(range(num_jobs), key=lambda j: len(T_j[j]), reverse=True)
    
    configs = []  # Active magazine states
    cost = 0
    
    for job in jobs_sorted:
        job_tools = set(T_j[job])
        
        # Try to fit in existing config
        placed = False
        for i, config in enumerate(configs):
            config_set = set(config)
            if job_tools.issubset(config_set):
                # No switch needed
                placed = True
                break
        
        if not placed:
            # Create new config
            if configs:
                cost += b  # Full reload
            new_config = tuple(sorted(job_tools.union(set(range(b - len(job_tools))))))
            configs.append(new_config)
    
    return cost

# Compute bounds
ub_warmstart = compute_warmstart_ub(jgp_batches, num_jobs, T_j, b)
ub_greedy = compute_greedy_ffd_ub(num_jobs, T_j, b)

print(f"\n--- BOUNDS ---")
print(f"Lower Bound (JGP): {jgp_obj}")
print(f"Upper Bound (Warm-Start): {ub_warmstart}")
print(f"Upper Bound (Greedy FFD): {ub_greedy}")
print(f"Upper Bound (SSP GTSP): {ssp_obj}")
</VSCode.Cell>

<VSCode.Cell id="#VSC-viz-bounds" language="mo-python">
# ==========================================
# 9. VISUALIZATION 2: BOUNDS HIERARCHY
# ==========================================

def plot_bounds_hierarchy(jgp_lb, ub_warmstart, ub_greedy, ssp_obj):
    """Show bounds as bars."""
    fig, ax = plt.subplots(figsize=(12, 6))
    
    bounds = {
        'JGP (LB)': jgp_lb,
        'Warm-Start (UB)': ub_warmstart,
        'Greedy FFD (UB)': ub_greedy,
        'SSP GTSP': ssp_obj
    }
    
    x_pos = np.arange(len(bounds))
    colors = ['green', 'salmon', 'coral', 'blue']
    
    bars = ax.bar(x_pos, bounds.values(), color=colors, edgecolor='black', linewidth=2)
    
    # Add value labels
    for bar, val in zip(bars, bounds.values()):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
               f'{val:.1f}', ha='center', va='bottom', fontsize=11, fontweight='bold')
    
    ax.set_xticks(x_pos)
    ax.set_xticklabels(bounds.keys(), fontsize=11)
    ax.set_ylabel('Tool Switching Cost', fontsize=12, fontweight='bold')
    ax.set_title('Bounds Hierarchy: LB ≤ OPT ≤ UB', fontsize=13, fontweight='bold')
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    
    return fig

fig2 = plot_bounds_hierarchy(jgp_obj, ub_warmstart, ub_greedy, ssp_obj)
plt.tight_layout()
plt.show()
</VSCode.Cell>

<VSCode.Cell id="#VSC-results-summary" language="mo-python">
# ==========================================
# 10. RESULTS SUMMARY
# ==========================================

print("\n" + "="*60)
print("COMPUTATIONAL RESULTS SUMMARY")
print("="*60)

results_df = pd.DataFrame({
    'Metric': ['JGP Lower Bound', 'Warm-Start UB', 'Greedy FFD UB', 'SSP GTSP Solver'],
    'Cost': [jgp_obj, ub_warmstart, ub_greedy, ssp_obj],
    'Gap to SSP (%)': [
        (ssp_obj - jgp_obj) / ssp_obj * 100 if ssp_obj > 0 else 0,
        (ub_warmstart - jgp_obj) / jgp_obj * 100 if jgp_obj > 0 else 0,
        (ub_greedy - jgp_obj) / jgp_obj * 100 if jgp_obj > 0 else 0,
        0
    ]
})

print("\n", results_df.to_string(index=False))

print("\n" + "="*60)
print(f"Instance: {J} jobs, {T} tools, capacity {b}")
print(f"Configuration space: {len(list(itertools.combinations(list(range(T)), b)))} configs")
print("="*60)
</VSCode.Cell>
