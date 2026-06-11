import sys, random
import numpy as np
from scipy.optimize import linprog
sys.path.insert(0, "/sessions/peaceful-happy-lovelace/mnt/JGP-SSP-Codes-Shankar/src/SSP")
from utils import compute_ktns

def tooling_lp_code(seq, tool_req, T, cap):
    """Exact replica of the code's DSP primal: persistence rows for job-to-job (all
    ordered real pairs) + depot->job (y_depot=0); capacity for real jobs; y=1 req,
    z=0 non-req; objective min sum_{j, t in T_j} z_jt. x-bar = depot cycle of seq."""
    jobs = list(tool_req.keys()); Tl = sorted(T)
    xb = {}
    xb[("d", seq[0])] = 1.0
    for k in range(len(seq)-1): xb[(seq[k], seq[k+1])] = 1.0
    yi = {(j,t): i for i,(j,t) in enumerate((j,t) for j in jobs for t in Tl)}
    off = len(yi)
    zi = {(j,t): off+i for i,(j,t) in enumerate((j,t) for j in jobs for t in Tl)}
    nv = off + len(zi)
    c = np.zeros(nv)
    for j in jobs:
        for t in tool_req[j]: c[zi[(j,t)]] = 1.0
    A, b = [], []
    for i in jobs:
        for j in jobs:
            if i == j: continue
            x = xb.get((i,j), 0.0)
            for t in Tl:
                r = np.zeros(nv); r[yi[(j,t)]] += 1; r[yi[(i,t)]] -= 1; r[zi[(j,t)]] -= 1
                A.append(r); b.append(1.0 - x)
    for j in jobs:                      # depot->j rows, y_depot = 0
        x = xb.get(("d", j), 0.0)
        for t in Tl:
            r = np.zeros(nv); r[yi[(j,t)]] += 1; r[zi[(j,t)]] -= 1
            A.append(r); b.append(1.0 - x)
    for j in jobs:                      # capacity
        r = np.zeros(nv)
        for t in Tl: r[yi[(j,t)]] = 1
        A.append(r); b.append(float(cap))
    bounds = [None]*nv
    for j in jobs:
        req = set(tool_req[j])
        for t in Tl:
            bounds[yi[(j,t)]] = (1.0,1.0) if t in req else (0.0,None)
            bounds[zi[(j,t)]] = (0.0,None) if t in req else (0.0,0.0)
    r = linprog(c, A_ub=np.array(A), b_ub=np.array(b), bounds=bounds, method="highs")
    assert r.status == 0
    return r.fun

random.seed(5)
bad = frac = 0; trials = 0
for _ in range(60):
    nT = random.randint(4,6); cap = random.choice([2,3]); n = random.randint(3,5)
    T = list(range(nT))
    tool_req = {j: sorted(random.sample(T, random.randint(1,cap))) for j in range(n)}
    seq = list(range(n)); random.shuffle(seq)
    lp = tooling_lp_code(seq, tool_req, T, cap)
    kf, _ = compute_ktns(seq, tool_req, cap)
    trials += 1
    if abs(lp - round(lp)) > 1e-6: frac += 1
    if abs(lp - kf) > 1e-6:
        bad += 1
        if bad <= 6: print(f"DIFF seq={seq} req={tool_req} cap={cap}: LP={lp:.3f} ktns={kf}")
print(f"{trials} trials: LP != compute_ktns in {bad} cases; fractional LP optima: {frac}")
