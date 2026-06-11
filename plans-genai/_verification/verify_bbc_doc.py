"""Verification for plans-genai/08_branch_and_benders.tex (Claude-Fable, 2026-06-10).

Tests the central claim behind the (implemented, default) LP-dual Benders cuts:
for a FIXED job sequence (encoded as a depot Hamiltonian cycle x-bar), the tooling
LP (primal of the DSP: persistence + capacity + required-tools constraints, as in
branch_and_benders_cut_cplex.py) has optimal value equal to the optimal number of
INTER-JOB tool switches (KTNS with free initial load).

Also checks the suspected convention mismatch: utils.compute_ktns charges the first
job's initial load (starts from an empty magazine), so we compare the LP value with
both compute_ktns(seq) and compute_ktns(seq) - |T_seq[0]|.
"""
import sys, random, itertools
import numpy as np
from scipy.optimize import linprog
sys.path.insert(0, "/sessions/peaceful-happy-lovelace/mnt/JGP-SSP-Codes-Shankar/src/SSP")
sys.path.insert(0, "/sessions/peaceful-happy-lovelace/mnt/JGP-SSP-Codes-Shankar/plans-genai/_verification")
from utils import compute_ktns
from ssp_verify import tooling_cost  # exact state-DP, free initial fill (independent check)

def tooling_lp(seq, tool_req, T, cap):
    """Primal tooling LP for fixed sequence; depot node d with T_d = empty.
    Vars y[node,t], z[node,t]; min sum_{j real, t in T_j} z[j,t]
    s.t. y[j,t]-y[i,t]-z[j,t] <= 1-xbar[i,j]  (all ordered node pairs i!=j, all t)
         sum_t y[j,t] <= cap                  (all nodes)
         y[j,t]=1 (t in T_j);  z[j,t]=0 (t not in T_j);  y,z >= 0."""
    n = len(seq); d = n  # nodes 0..n-1 = jobs in seq order? No: nodes = job ids + depot
    jobs = list(tool_req.keys())
    nodes = jobs + ["d"]
    arcs_on = set()
    arcs_on.add(("d", seq[0])); arcs_on.add((seq[-1], "d"))
    for k in range(len(seq) - 1): arcs_on.add((seq[k], seq[k + 1]))
    Tl = sorted(T)
    yi = {(j, t): idx for idx, (j, t) in enumerate((j, t) for j in nodes for t in Tl)}
    off = len(yi)
    zi = {(j, t): off + idx for idx, (j, t) in enumerate((j, t) for j in nodes for t in Tl)}
    nv = off + len(zi)
    c = np.zeros(nv)
    for j in jobs:
        for t in tool_req[j]: c[zi[(j, t)]] = 1.0
    A, bvec = [], []
    for i in nodes:
        for j in nodes:
            if i == j: continue
            xb = 1.0 if (i, j) in arcs_on else 0.0
            for t in Tl:
                row = np.zeros(nv)
                row[yi[(j, t)]] += 1; row[yi[(i, t)]] -= 1; row[zi[(j, t)]] -= 1
                A.append(row); bvec.append(1.0 - xb)
    for j in nodes:
        row = np.zeros(nv)
        for t in Tl: row[yi[(j, t)]] = 1
        A.append(row); bvec.append(float(cap))
    bounds = [None] * nv
    for j in nodes:
        req = set(tool_req[j]) if j != "d" else set()
        for t in Tl:
            bounds[yi[(j, t)]] = (1.0, 1.0) if t in req else (0.0, None)
            bounds[zi[(j, t)]] = (0.0, 0.0) if t not in req else (0.0, None)
    r = linprog(c, A_ub=np.array(A), b_ub=np.array(bvec), bounds=bounds, method="highs")
    assert r.status == 0, r.message
    return r.fun

random.seed(3)
frac_int = 0  # LP value not integral
mismatch_path = 0
trials = 0
for _ in range(25):
    nT = random.randint(4, 6); cap = 3; n = random.randint(3, 4)
    T = list(range(nT))
    tool_req = {j: sorted(random.sample(T, random.randint(1, cap))) for j in range(n)}
    seq = list(range(n)); random.shuffle(seq)
    lp = tooling_lp(seq, tool_req, T, cap)
    k_full, _ = compute_ktns(seq, tool_req, cap)
    k_path = k_full - len(tool_req[seq[0]])
    dp = tooling_cost([frozenset(tool_req[j]) for j in seq], set(T), cap)  # free-init exact DP
    trials += 1
    if abs(lp - round(lp)) > 1e-6: frac_int += 1
    if abs(lp - k_path) > 1e-6: mismatch_path += 1
    status = "OK" if abs(lp - k_path) < 1e-6 else "DIFF"
    if status == "DIFF" or abs(k_path - dp) > 1e-9:
        print(f"seq={seq} req={tool_req}: LP={lp:.3f} ktns_full={k_full} ktns_path={k_path} dp={dp}  {status}")
print(f"{trials} trials: LP==ktns-|T_first| mismatches={mismatch_path}, fractional LP optima={frac_int}")
print("If mismatches==0: LP-dual (DSP) value == inter-job switches (free initial load);")
print("=> compute_ktns (charges initial load) and the DSP use DIFFERENT conventions.")
