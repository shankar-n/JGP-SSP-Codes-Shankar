"""BBC code audit tests (Claude-Fable, 2026-06-10).

T1: pure-python helpers (subtour detection, sequence extraction, x_bar build)
    of BranchAndBendersCutSSP_CPLEX, exercised without CPLEX.
T2: scipy mirror of the code's DSP (variables lam, lam_d, mu, nu, eta;
    rows dy, dz with rhs=1 for all t) -- check DSP opt == compute_ktns.
T3: THE CUT BUG TEST. The code's cut omits the depot-arc dual terms
    sum_j (x_dj - 1) lam_d[j,t].  Demonstrate: there exists an optimal dual
    vertex with lam_d[j,.] > 0 for j != seq[0] (second-stage LP maximising that
    mass at fixed optimal objective); from it, the TRUNCATED cut evaluated at
    another sequence x' exceeds KTNS(x') => the cut is INVALID (cuts off a
    feasible (x', theta=true cost) point).  The FULL cut (with depot terms)
    must never exceed KTNS(x') -- checked as control.
"""
import sys, random, itertools
import numpy as np
from scipy.optimize import linprog
sys.path.insert(0, "/sessions/peaceful-happy-lovelace/mnt/JGP-SSP-Codes-Shankar/src/SSP")
sys.path.insert(0, "/sessions/peaceful-happy-lovelace/mnt/JGP-SSP-Codes-Shankar/src/BBC")
from utils import compute_ktns
from branch_and_benders_cut_cplex import BranchAndBendersCutSSP_CPLEX as S

# ---------- T1: pure helpers ----------
def mk(n_jobs, tool_req, cap, nT):
    s = S.__new__(S)
    s.n_jobs, s.n_tools, s.capacity, s.tool_req = n_jobs, nT, cap, tool_req
    s.depot = n_jobs
    return s

s = mk(4, {0:[0],1:[1],2:[2],3:[3]}, 2, 4)
d = 4
# valid depot tour d->2->0->3->1->d
tour = {(d,2):1.0,(2,0):1.0,(0,3):1.0,(3,1):1.0,(1,d):1.0}
assert S._find_subtours_from_sol(s, tour) == []
assert S._get_sequence_from_sol(s, tour) == [2,0,3,1]
assert S._build_x_bar_from_sequence(s, [2,0,3,1]) == tour
# two subtours: d->0->d and 1->2->3->1
two = {(d,0):1.0,(0,d):1.0,(1,2):1.0,(2,3):1.0,(3,1):1.0}
sts = S._find_subtours_from_sol(s, two)
assert sorted(len(c) for c in sts) == [2,3], sts
print("T1 OK: subtour detection / sequence extraction / x_bar build")

# ---------- DSP mirror (dual side, exactly as _build_dsp_cplex_model) ----------
def dsp_solve(n, T, tool_req, cap, x_bar, second_stage=False):
    """Solve max c'v s.t. dy,dz rows; returns (obj, vars dict).
    Variable order: lam[i,j,t], lam_d[j,t], mu[j], nu[j,t], eta[j,t]."""
    Tl = list(range(T))
    lam_i, ld_i, mu_i, nu_i, eta_i = {}, {}, {}, {}, {}
    k = 0
    for i in range(n):
        for j in range(n):
            if i != j:
                for t in Tl: lam_i[i,j,t] = k; k += 1
    for j in range(n):
        for t in Tl: ld_i[j,t] = k; k += 1
    for j in range(n): mu_i[j] = k; k += 1
    for j in range(n):
        for t in Tl: nu_i[j,t] = k; k += 1
    for j in range(n):
        for t in Tl: eta_i[j,t] = k; k += 1
    nv = k
    c = np.zeros(nv)
    for (i,j,t),col in lam_i.items(): c[col] = x_bar.get((i,j),0.0) - 1.0
    for (j,t),col in ld_i.items():    c[col] = x_bar.get((n,j),0.0) - 1.0  # depot=n
    for j,col in mu_i.items():        c[col] = -float(cap)
    for (j,t),col in nu_i.items():    c[col] = 1.0 if t in tool_req[j] else 0.0
    A, b = [], []
    for j in range(n):
        Tj = set(tool_req[j])
        for t in Tl:
            r = np.zeros(nv)              # dy
            r[mu_i[j]] = -1; r[ld_i[j,t]] = -1
            for i in range(n):
                if i != j: r[lam_i[i,j,t]] = -1
            for kk in range(n):
                if kk != j: r[lam_i[j,kk,t]] = 1
            if t in Tj: r[nu_i[j,t]] = 1
            A.append(r); b.append(0.0)
            r = np.zeros(nv)              # dz (rhs=1 for ALL t, as in code)
            r[ld_i[j,t]] = 1
            for i in range(n):
                if i != j: r[lam_i[i,j,t]] = 1
            if t not in Tj: r[eta_i[j,t]] = 1
            A.append(r); b.append(1.0)
    bounds = [(0,None)]*nv
    for col in nu_i.values(): bounds[col] = (None,None)
    for col in eta_i.values(): bounds[col] = (None,None)
    res = linprog(-c, A_ub=np.array(A), b_ub=np.array(b), bounds=bounds, method="highs")
    assert res.status == 0, res.message
    opt = -res.fun
    if not second_stage:
        return opt, None
    # stage 2: maximise depot-lam mass on j != seq-first  s.t. obj == opt
    first = [j for j in range(n) if x_bar.get((n,j),0)>0.5][0]
    c2 = np.zeros(nv)
    for (j,t),col in ld_i.items():
        if j != first: c2[col] = 1.0
    A_eq = np.array([c]); b_eq = np.array([opt])
    res2 = linprog(-c2, A_ub=np.array(A), b_ub=np.array(b), A_eq=A_eq, b_eq=b_eq,
                   bounds=bounds, method="highs")
    assert res2.status == 0, res2.message
    v = res2.x
    p = dict(lam={kk: v[col] for kk,col in lam_i.items()},
             lam_d={kk: v[col] for kk,col in ld_i.items()},
             mu={kk: v[col] for kk,col in mu_i.items()},
             nu={kk: v[col] for kk,col in nu_i.items()},
             extra=-res2.fun)
    return opt, p

def cut_rhs_at(p, xq, n, T, tool_req, cap, with_depot):
    val = 0.0
    for (i,j,t),l in p['lam'].items(): val += (xq.get((i,j),0.0)-1.0)*l
    if with_depot:
        for (j,t),l in p['lam_d'].items(): val += (xq.get((n,j),0.0)-1.0)*l
    for j,m in p['mu'].items(): val -= cap*m
    for (j,t),nuv in p['nu'].items():
        if t in tool_req[j]: val += nuv
    return val

# ---------- T2 + T3 ----------
random.seed(11)
t2_bad = 0; witnesses = 0; tried = 0; deg_found = 0
for trial in range(40):
    nT = random.randint(3,5); cap = random.choice([2,3]); n = random.randint(3,4)
    tool_req = {j: sorted(random.sample(range(nT), random.randint(1,cap))) for j in range(n)}
    seq = list(range(n)); random.shuffle(seq)
    xb = {(seq[k],seq[k+1]):1.0 for k in range(n-1)}; xb[(n,seq[0])]=1.0; xb[(seq[-1],n)]=1.0
    opt, p = dsp_solve(n, nT, tool_req, cap, xb, second_stage=True)
    kf,_ = compute_ktns(seq, tool_req, cap)
    tried += 1
    if abs(opt - kf) > 1e-6: t2_bad += 1; continue
    if p['extra'] < 1e-6: continue           # no degenerate depot mass at this vertex
    deg_found += 1
    # evaluate truncated vs full cut at every other sequence
    for perm in itertools.permutations(range(n)):
        if list(perm) == seq: continue
        xq = {(perm[k],perm[k+1]):1.0 for k in range(n-1)}
        xq[(n,perm[0])]=1.0; xq[(perm[-1],n)]=1.0
        true_cost,_ = compute_ktns(list(perm), tool_req, cap)
        rhs_full  = cut_rhs_at(p, xq, n, nT, tool_req, cap, with_depot=True)
        rhs_trunc = cut_rhs_at(p, xq, n, nT, tool_req, cap, with_depot=False)
        assert rhs_full <= true_cost + 1e-6, "FULL cut invalid?! (should never happen)"
        if rhs_trunc > true_cost + 1e-6:
            witnesses += 1
            if witnesses <= 3:
                print(f"T3 WITNESS: req={tool_req} cap={cap} gen-seq={seq} "
                      f"victim={list(perm)}: truncated cut forces theta>={rhs_trunc:.3f} "
                      f"> true cost {true_cost} (full cut rhs={rhs_full:.3f})")
print(f"T2: DSP==compute_ktns on {tried} pairs, mismatches={t2_bad}")
print(f"T3: degenerate depot-lam optima found in {deg_found}/{tried} instances; "
      f"invalid-truncated-cut witnesses: {witnesses}")
if witnesses:
    print(">>> CONFIRMED BUG: _build_benders_cut_sparsepair omits depot-arc dual terms;")
    print(">>> with a degenerate DSP vertex the added cut can cut off true optima.")
else:
    print("No witness found (bug remains a logical-validity gap; CPLEX vertex choice may differ).")
