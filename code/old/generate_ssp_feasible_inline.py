import numpy as np
import pandas as pd
import itertools

def load_ssp_instance(filepath):
    """
    Load an SSP instance from the standard text format.

    Format (first non-blank line):  J  T  C
    Followed by a T × J (tools × jobs) binary incidence matrix.

    Returns
    -------
    J : int   — number of jobs
    T : int   — number of tools
    C : int   — magazine capacity  (b)
    A : ndarray shape (T, J)  — incidence matrix  A[t, j] = 1 iff job j needs tool t
    """
    with open(filepath, 'r') as fh:
        tokens = fh.read().split()
    tokens = [int(x) for x in tokens if x.strip()]
    J, T_dim, C = tokens[0], tokens[1], tokens[2]
    A = np.array(tokens[3:], dtype=int).reshape((T_dim, J))
    # Per-job tool requirement list
    T_j = {j: [t for t in range(T_dim) if A[t, j] == 1]
        for j in range(J)}
    return J, T_dim, C, A, T_j

def compute_switch_cost(cfg_a, cfg_b, cap):
    return cap - len(set(cfg_a).intersection(set(cfg_b)))

def add_configs_from_job_sequence(job_sequence):
    if len(job_sequence) == 1:
        return all_configs[H_j[job_sequence[0]]]
    x = job_sequence[0];
    n = len(job_sequence)
    ret = np.empty((0,n,b),int)
    for config_id in H_j[x]:
        ret = np.vstack((ret,np.array([np.vstack((all_configs[config_id],tcfg)) for tcfg in add_configs_from_job_sequence(job_sequence[1:])])))
    return ret

def compute_cost2(configs):
    cost = 0
    prev_cfg = None
    for cfg in configs:
        if prev_cfg is not None:
            cost += compute_switch_cost(prev_cfg, cfg, b)
        prev_cfg = cfg
    return cost

filepath = './shankar-example.txt'
num_jobs, num_tools, b, matrix, T_j = load_ssp_instance(filepath)

all_configs = np.array(list(itertools.combinations(range(num_tools), b)))

print(f"Instance loaded: {filepath}")
print(f"  Jobs={num_jobs}, Tools={num_tools}, Capacity={b}")
print(f"  Config space size: C({num_tools},{b}) = "
      f"{len(all_configs)}")


# H_j[j] = list of configs that can serve job j
H_j = {j: [] for j in range(num_jobs)}
for (index, cfg) in enumerate(all_configs):
    cfg_set = set(cfg)
    for j in range(num_jobs):
        if set(T_j[j]).issubset(cfg_set):
            H_j[j].append(index)

all_job_sequences = np.array(list(itertools.permutations(range(num_jobs), num_jobs)))
print(f"Number of job sequences: {len(all_job_sequences)}")

feasible_solutions = pd.DataFrame(columns=['#','Job Sequence', 'Configurations', 'SSP Cost']);
row_id = 0
for job_sequence in all_job_sequences:
    for sequence_configs in add_configs_from_job_sequence(job_sequence):
        feasible_solutions.loc[row_id, : ] = [row_id+1, job_sequence, sequence_configs, compute_cost2(sequence_configs)]
        row_id += 1

print(f"Number of feasible solutions: {len(feasible_solutions)}")
feasible_solutions.to_csv("ssp_feasible_solutions.csv")