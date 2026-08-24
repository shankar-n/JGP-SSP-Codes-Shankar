#!/usr/bin/env python3
"""
verify_report_independent.py
=============================
Independent re-derivation of every small-instance claim in report/JGP-SSP_report.tex.

Written from scratch: shares no code with src/ or plans-genai/_verification/, so
agreement is corroboration rather than a re-run of the same implementation.

Conventions (fixed once, applied everywhere):
  cost_empty = insertions counted from an initially empty magazine
  cost_free  = cost_empty - min(b, |U|)                 ("free-initial")
Every number below is FREE-INITIAL unless the name ends in _empty.

Loading for a fixed order is computed two ways -- an exact DP over magazine states
and the KTNS rule -- and the two are cross-checked, so Proposition 2.2 (Tang &
Denardo) is TESTED rather than assumed.  The optimum Z* is computed by a
Held-Karp DP over (set of finished jobs, current magazine), which is exact and
does not presuppose the report's own machinery.

Usage:  python3 verify_report_independent.py [-v]
Exit 0 iff every check passes.
"""
import sys, random
from itertools import combinations, permutations

VERBOSE = "-v" in sys.argv
RESULTS = []


def check(claim, where, expected, got):
    ok = (expected == got)
    RESULTS.append((claim, where, expected, got, ok))
    print(f"  [{'PASS' if ok else 'FAIL'}] {claim}")
    if VERBOSE or not ok:
        print(f"          {where}: expected {expected}, got {got}")
    return ok


# ---------------------------------------------------------------------------
# loading a fixed order
# ---------------------------------------------------------------------------
def loading_exact_dp(seq, T, b):
    """Exact minimum insertions from an empty magazine (empty-start). No policy assumed."""
    cur = {frozenset(): 0}
    for j in seq:
        req = T[j]
        nxt = {}
        for M, c in cur.items():
            ins = len(req - M)
            union = M | req
            keep = min(b, len(union))
            spare = sorted(union - req)
            need_extra = keep - len(req)
            for extra in combinations(spare, need_extra):
                Mn = frozenset(req | set(extra))
                v = c + ins
                if nxt.get(Mn, 1 << 30) > v:
                    nxt[Mn] = v
        cur = nxt
    return min(cur.values())


def ktns(seq, T, b):
    """Keep-Tool-Needed-Soonest, demand-loading form (empty-start)."""
    n = len(seq)
    nxt = []
    for i in range(n):
        d = {}
        for k in range(n - 1, i, -1):
            for t in T[seq[k]]:
                d[t] = k
        nxt.append(d)
    M, cost = set(), 0
    for i, j in enumerate(seq):
        req = T[j]
        cost += len(req - M)
        M |= req
        if len(M) > b:
            drop = sorted(M - req, key=lambda t: -nxt[i].get(t, 1 << 30))
            while len(M) > b:
                M.discard(drop.pop(0))
    return cost


def Z_empty(T, b):
    """Optimum over all orders, by DP on (finished-jobs mask, magazine)."""
    n = len(T)
    full = (1 << n) - 1
    start = {frozenset(): 0}
    layer = {0: start}
    for _ in range(n):
        nl = {}
        for mask, states in layer.items():
            for j in range(n):
                if mask >> j & 1:
                    continue
                nm = mask | 1 << j
                req = T[j]
                tgt = nl.setdefault(nm, {})
                for M, c in states.items():
                    v = c + len(req - M)
                    union = M | req
                    keep = min(b, len(union))
                    spare = sorted(union - req)
                    for extra in combinations(spare, keep - len(req)):
                        Mn = frozenset(req | set(extra))
                        if tgt.get(Mn, 1 << 30) > v:
                            tgt[Mn] = v
        layer = nl
    return min(layer[full].values())


def U_of(T):
    return sorted(set().union(*T))


def Zstar(T, b):
    return Z_empty(T, b) - min(b, len(U_of(T)))


# ---------------------------------------------------------------------------
# grouping
# ---------------------------------------------------------------------------
def feasible_groups(T, b):
    n = len(T)
    out = []
    for k in range(1, n + 1):
        for g in combinations(range(n), k):
            if len(set().union(*(T[j] for j in g))) <= b:
                out.append(g)
    return out


def partitions_into(T, b, K):
    """All partitions of the jobs into exactly K feasible groups (backtracking)."""
    n = len(T)
    groups = feasible_groups(T, b)
    by_low = {}
    for g in groups:
        by_low.setdefault(g[0], []).append(g)
    res = []

    def rec(used, acc):
        if len(acc) > K:
            return
        if used == (1 << n) - 1:
            if len(acc) == K:
                res.append(list(acc))
            return
        low = next(i for i in range(n) if not used >> i & 1)
        for g in by_low.get(low, []):
            m = 0
            for j in g:
                m |= 1 << j
            if m & used:
                continue
            acc.append(g)
            rec(used | m, acc)
            acc.pop()
    rec(0, [])
    return res


def Kstar(T, b):
    for k in range(1, len(T) + 1):
        if partitions_into(T, b, k):
            return k
    return len(T)


def configs_for(group, T, b, universe):
    u = set().union(*(T[j] for j in group))
    if len(u) > b:
        return []
    spare = sorted(set(universe) - u)
    return [frozenset(u | set(e)) for e in combinations(spare, b - len(u))]


def H_walk(T, b, K):
    """Best configuration-walk cost over minimum-cardinality groupings (free-initial)."""
    U = U_of(T)
    best = None
    for part in partitions_into(T, b, K):
        ch = [configs_for(g, T, b, U) for g in part]
        if any(not c for c in ch):
            continue

        def rec(i, chosen):
            nonlocal best
            if i == len(ch):
                for o in permutations(chosen):
                    c = sum(len(o[l + 1] - o[l]) for l in range(len(o) - 1))
                    if best is None or c < best:
                        best = c
                return
            for cfg in ch[i]:
                rec(i + 1, chosen + [cfg])
        rec(0, [])
    return best


def H_true(T, b, K):
    """The heuristic AS DEFINED (report ssec:jgp step 3): minimum-cardinality grouping,
    group order, within-group order, then KTNS on the flattened job order."""
    U = U_of(T)
    best = None
    for part in partitions_into(T, b, K):
        for order in permutations(part):
            inner = [list(permutations(g)) for g in order]

            def rec(i, seq):
                nonlocal best
                if i == len(inner):
                    c = ktns(tuple(seq), T, b)
                    if best is None or c < best:
                        best = c
                    return
                for w in inner[i]:
                    rec(i + 1, seq + list(w))
            rec(0, [])
    return best - min(b, len(U))


def profile(T, b):
    U = U_of(T)
    K = Kstar(T, b)
    Z = Zstar(T, b)
    return dict(K=K, Z=Z, Hwalk=H_walk(T, b, K), Htrue=H_true(T, b, K),
                U=len(U), q=len(U) - b, R=Z - (len(U) - b))


def ring(k, w=2):
    return [set((i + d) % k for d in range(w)) for i in range(k)]


# ===========================================================================
print("=" * 78)
print("INDEPENDENT VERIFICATION OF report/JGP-SSP_report.tex")
print("=" * 78)

print("\n[0] Oracles: KTNS vs exact DP, and the Z* DP vs brute-force permutations")
random.seed(11)
bad_ktns = bad_dp = 0
for _ in range(120):
    n, m = random.randint(3, 5), random.randint(4, 6)
    b = random.randint(2, 4)
    T = [set(random.sample(range(m), random.randint(1, min(b, m)))) for _ in range(n)]
    for p in permutations(range(n)):
        if ktns(p, T, b) != loading_exact_dp(p, T, b):
            bad_ktns += 1
            break
    if Z_empty(T, b) != min(ktns(p, T, b) for p in permutations(range(n))):
        bad_dp += 1
check("KTNS attains the exact optimal loading on every tested order (Prop 2.2 tested)",
      "prop:ktns (l.472)", 0, bad_ktns)
check("the Held-Karp Z* DP agrees with brute force over all permutations",
      "internal consistency of this verifier", 0, bad_dp)

print("\n[1] The 6-ring (Examples 2.1 and 2.3)")
r6 = ring(6)
p6 = profile(r6, 3)
check("6-ring K* = 3", "ex:ring-group (l.569)", 3, p6["K"])
check("6-ring Z* = 3 free-initial / 6 empty-start", "ex:ring (l.448)",
      (3, 6), (p6["Z"], Z_empty(r6, 3)))
check("6-ring H_walk = 4", "ex:ring-group (l.573)", 4, p6["Hwalk"])
check("6-ring H = 4 (KTNS-evaluated)", "ex:ring-group (l.573)", 4, p6["Htrue"])
check("6-ring gap = 1, ratio 4/3", "ex:ring-group (l.577)",
      (1, 4 / 3), (p6["Htrue"] - p6["Z"], p6["Htrue"] / p6["Z"]))

print("\n[2] Table 3.1, the k-ring at b = 3")
for k, (K, Z, H) in {3: (1, 0, 0), 4: (2, 1, 1), 5: (3, 2, 2),
                     6: (3, 3, 4), 7: (4, 4, 5), 8: (4, 5, 6)}.items():
    pk = profile(ring(k), 3)
    check(f"{k}-ring (K*, Z*, H)", "tab:rings (l.1085-1090)",
          (K, Z, H), (pk["K"], pk["Z"], pk["Htrue"]))

print("\n[3] Proposition 3.2, g tool-disjoint copies of the 6-ring")
for g in (1, 2):
    T, off = [], 0
    for _ in range(g):
        T += [set(t + off for t in s) for s in ring(6)]
        off += 6
    K = Kstar(T, 3)
    Z, H = Zstar(T, 3), H_true(T, 3, K)
    check(f"g={g}: K* = 3g, Z* = 6g-3, H = 7g-3", "prop:unbounded (l.1097)",
          (3 * g, 6 * g - 3, 7 * g - 3), (K, Z, H))
    check(f"g={g}: gap = g", "prop:unbounded (l.1099)", g, H - Z)

print("\n[4] The 8-job sliding-window ring at b = 4")
psw = profile(ring(8, 3), 4)
check("Z* = 5 exceeds max(K*-1, |U|-b) = max(3, 4)", "l.723-724",
      (5, 3, 4, True), (psw["Z"], psw["K"] - 1, psw["U"] - 4,
                        psw["Z"] > max(psw["K"] - 1, psw["U"] - 4)))

print("\n[5] Proposition 3.11, the refutation witness W1 (b = 5)")
W1 = [{0, 1, 2, 4, 7}, {0, 4, 5}, {1, 5}, {2, 6, 8}, {3, 4, 5, 8}]
pw = profile(W1, 5)
check("W1 (K*, q, Z*) = (3, 4, 4)", "prop:refute (l.1355-1361)",
      (3, 4, 4), (pw["K"], pw["q"], pw["Z"]))
check("W1 H_walk = 6, so the WALK gap is 2 > K*-2", "prop:refute (l.1361)",
      (6, 2), (pw["Hwalk"], pw["Hwalk"] - pw["Z"]))
check("W1 H = 5, so the HEURISTIC gap is 1 and gap<=K*-2 is NOT refuted",
      "prop:refute (l.1366)", (5, 1), (pw["Htrue"], pw["Htrue"] - pw["Z"]))
check("W1 lies on the boundary 2b = q + 3R + 6", "prop:refute (l.1362)",
      True, 2 * 5 == pw["q"] + 3 * pw["R"] + 6)

print("\n[6] Proposition 3.14, the clutter pair at b = 4")
I0 = [{0, 2, 6}, {1, 2, 3}, {2, 3, 4, 5}, {3, 4, 5}]
I1 = [{0, 1, 3, 6}, {1, 4, 5, 6}, {2, 4}, {3, 5}]
for nm, inst, gap in (("I0", I0, 0), ("I1", I1, 1)):
    pi = profile(inst, 4)
    check(f"{nm}: K* = 3, Z* = 3, gap = {gap}", "prop:noclutter (l.1513-1522)",
          (3, 3, gap), (pi["K"], pi["Z"], pi["Htrue"] - pi["Z"]))

print("\n[7] The K* = 4 positive-gap witness at b = 3")
K4 = [{0, 2, 5}, {0, 3, 6}, {1, 2}, {1, 4}, {1, 6}]
pk4 = profile(K4, 3)
check("witness (K*, Z*, H) = (4, 4, 5), ratio 5/4", "l.1399-1400",
      (4, 4, 5), (pk4["K"], pk4["Z"], pk4["Htrue"]))

print("\n[8] Propositions 3.12 and 3.13, the structural side")
star = [{0, 1}, {0, 2}, {0, 3}]
check("star: conflict graph has no edge, yet K* = 2", "prop:chromK (l.1443-1445)",
      (0, 2), (sum(1 for i, j in combinations(range(3), 2) if len(star[i] | star[j]) > 3),
               Kstar(star, 3)))
nm = [{1}, {2}, {3, 4}]
check("group complex is not a matroid on the stated instance",
      "prop:nonmatroid (l.1502)", (True, True, False, False),
      (len(nm[2]) <= 2, len(nm[0] | nm[1]) <= 2,
       len(nm[2] | nm[0]) <= 2, len(nm[2] | nm[1]) <= 2))

print("\n[9] Proposition 3.15, the JGP covering relaxation on k-rings")
from scipy.optimize import linprog
def frac_cover(T, b):
    n = len(T)
    gs = feasible_groups(T, b)
    maximal = [g for g in gs if not any(set(g) < set(h) for h in gs)]
    A = [[-1.0 if j in g else 0.0 for g in maximal] for j in range(n)]
    r = linprog([1.0] * len(maximal), A_ub=A, b_ub=[-1.0] * n,
                bounds=[(0, None)] * len(maximal), method="highs")
    return round(r.fun, 6)
for k in range(3, 9):
    check(f"{k}-ring: fractional cover k/2, K* = ceil(k/2)", "prop:oddring (l.1558)",
          (k / 2, -(-k // 2)), (frac_cover(ring(k), 3), Kstar(ring(k), 3)))

print("\n[10] Proposition 2.9, the convention identity")
random.seed(5)
bad = 0
for _ in range(60):
    n, m = random.randint(2, 5), random.randint(3, 6)
    b = random.randint(2, 4)
    T = [set(random.sample(range(m), random.randint(1, min(b, m)))) for _ in range(n)]
    if Z_empty(T, b) != Zstar(T, b) + min(b, len(U_of(T))):
        bad += 1
check("cost_empty = cost_free + min(b, |U|) on every tested instance",
      "prop:conv (l.736)", 0, bad)

print("\n[11] The general bounds on a random census")
viol = dict(lb=0, uncond=0, zero2=0, zeroU=0, smallZ=0, z3=0, transcap=0, k3=0, genk=0)
tested = 0
random.seed(2026)
while tested < 200:
    n, m = random.randint(3, 5), random.randint(4, 7)
    b = random.randint(2, 5)
    T = [set(random.sample(range(m), random.randint(1, min(b, m)))) for _ in range(n)]
    U = U_of(T)
    if len(U) <= b:
        continue
    p = profile(T, b)
    if p["Hwalk"] is None:
        continue
    tested += 1
    K, Z, H, q, R, Hw = p["K"], p["Z"], p["Htrue"], p["q"], p["R"], p["Hwalk"]
    if Z < max(K - 1, q):                                       viol["lb"] += 1
    if K >= 2 and Z > 0 and H / Z > min(b, K - 1, q):           viol["uncond"] += 1
    if K == 2 and H != Z:                                       viol["zero2"] += 1
    if p["U"] <= b + 1 and H != Z:                              viol["zeroU"] += 1
    if Z <= 2 and H != Z:                                       viol["smallZ"] += 1
    if Z <= 3 and H - Z > 1:                                    viol["z3"] += 1
    if Hw > (K - 1) * min(b, q):                                viol["transcap"] += 1
    if K == 3 and Hw - Z > max(0, min(q, (2 * b - q) // 3) - R): viol["k3"] += 1
    if K >= 2 and Hw - Z > max(0, (q * (b * (K - 1) - q)) // (b + q) - R):
        viol["genk"] += 1
for nm_, where in (("lb", "cor:lb (l.709)"), ("uncond", "thm:uncond (l.1163)"),
                   ("zero2", "cor:zerogap(i) (l.1181)"), ("zeroU", "cor:zerogap(ii)"),
                   ("smallZ", "cor:smallZ (l.1314)"), ("z3", "cor:z3 (l.1326)"),
                   ("transcap", "lem:transcap (l.1144)"), ("k3", "prop:k3 (l.1256)"),
                   ("genk", "prop:genk (l.1286)")):
    check(f"{nm_}: no violation on {tested} random instances", where, 0, viol[nm_])

print("\n[12] Proposition 3.7, the closed form for the walk cost at K* = 3")
random.seed(77)
bad = seen = 0
while seen < 45:
    n, m = random.randint(3, 5), random.randint(4, 7)
    b = random.randint(3, 5)
    T = [set(random.sample(range(m), random.randint(1, min(b, m)))) for _ in range(n)]
    U = U_of(T)
    if len(U) <= b or Kstar(T, b) != 3:
        continue
    seen += 1
    best = None
    for part in partitions_into(T, b, 3):
        ch = [configs_for(g, T, b, U) for g in part]
        if any(not c for c in ch):
            continue
        for A in ch[0]:
            for B in ch[1]:
                for C in ch[2]:
                    v = min(len((A & B) - C), len((B & C) - A), len((C & A) - B))
                    if best is None or v < best:
                        best = v
    if (len(U) - b) + best != H_walk(T, b, 3):
        bad += 1
check(f"H_walk = q + min over 3-groupings of min(x_ab, x_bc, x_ca) on {seen} instances",
      "prop:hk3 (l.1219)", 0, bad)

print("\n[13] Theorem 3.16, the setup-cost collapse")
def augmented(T, b, rho):
    U = U_of(T)
    best, sizes = None, []
    for K in range(1, len(T) + 1):
        for part in partitions_into(T, b, K):
            ch = [configs_for(g, T, b, U) for g in part]
            if any(not c for c in ch):
                continue
            def rec(i, chosen):
                nonlocal best, sizes
                if i == len(ch):
                    for o in permutations(chosen):
                        c = sum(len(o[l + 1] - o[l]) for l in range(len(o) - 1)) \
                            + rho * (len(part) - 1)
                        if best is None or c < best - 1e-9:
                            best, sizes = c, [len(part)]
                        elif abs(c - best) < 1e-9:
                            sizes.append(len(part))
                    return
                for cfg in ch[i]:
                    rec(i + 1, chosen + [cfg])
            rec(0, [])
    return best, sizes
bad_walk = bad_true = 0
for inst, b in ((ring(6), 3), (I1, 4), (K4, 3)):
    p = profile(inst, b)
    _, sw = augmented(inst, b, (p["Hwalk"] - p["Z"]) + 0.5)   # threshold from H_walk
    _, st = augmented(inst, b, (p["Htrue"] - p["Z"]) + 0.5)   # threshold from H
    if set(sw) != {p["K"]}:
        bad_walk += 1
    if set(st) != {p["K"]}:
        bad_true += 1
check("collapse holds when the threshold is read in the WALK frame (rho > H_walk - Z*)",
      "thm:collapse (l.1588)", 0, bad_walk)
check("collapse FAILS when the threshold is read in the heuristic frame (rho > H - Z*) "
      "-- the theorem is frame-dependent and the report does not say which frame",
      "thm:collapse (l.1588)", 0, bad_true)

print("\n[14] Proposition 4.4, the PCF linear relaxation")
def pcf_lp(T, b, with_T):
    U = U_of(T)
    n = len(T)
    cfgs = [frozenset(c) for c in combinations(U, b)]
    nc, nt = len(cfgs), len(U)
    y = {(c, k): c * n + k for c in range(nc) for k in range(n)}
    base = nc * n
    w = {(t, k): base + i * n + k for i, t in enumerate(U) for k in range(n)}
    N = base + nt * n
    obj = [0.0] * N
    for col in w.values():
        obj[col] = 1.0
    Aeq, beq, Aub, bub = [], [], [], []
    for k in range(n):
        r = [0.0] * N
        for c in range(nc):
            r[y[(c, k)]] = 1.0
        Aeq.append(r); beq.append(1.0)
    for j in range(n):
        r = [0.0] * N
        for c, C in enumerate(cfgs):
            if T[j] <= C:
                for k in range(n):
                    r[y[(c, k)]] -= 1.0
        Aub.append(r); bub.append(-1.0)
    for t in U:
        for k in range(1, n):
            r = [0.0] * N
            r[w[(t, k)]] = -1.0
            for c, C in enumerate(cfgs):
                if t in C:
                    r[y[(c, k)]] += 1.0
                    r[y[(c, k - 1)]] -= 1.0
            Aub.append(r); bub.append(0.0)
    if with_T:
        for t in U:
            r = [0.0] * N
            for k in range(1, n):
                r[w[(t, k)]] = -1.0
            for c, C in enumerate(cfgs):
                if t in C:
                    r[y[(c, 0)]] = -1.0
            Aub.append(r); bub.append(-1.0)
    res = linprog(obj, A_ub=Aub, b_ub=bub, A_eq=Aeq, b_eq=beq,
                  bounds=[(0, None)] * N, method="highs")
    return round(res.fun, 4)
check("PCF without the counting rows (T) has LP value 0",
      "prop:pcf (l.2055)", 0.0, pcf_lp(r6, 3, False))
check("PCF with (T) equals |U| - b on the 6-ring", "prop:pcf (l.2057)",
      3.0, pcf_lp(r6, 3, True))
sm = [{0, 1}, {1, 2}, {2, 3}]
check("PCF with (T) equals |U| - b on a second instance", "prop:pcf (l.2057)",
      1.0, pcf_lp(sm, 3, True))

print("\n[15] Frame audit: the k-ring family under the two readings of H")
for k in range(3, 10):
    r, K = ring(k), Kstar(ring(k), 3)
    Z, hw, ht = Zstar(r, 3), H_walk(r, 3, K), H_true(r, 3, K)
    print(f"      {k}-ring: Z*={Z}  H_walk={hw} (walk gap {hw-Z})  H={ht} (heuristic gap {ht-Z})")
check("every k-ring, k=3..9, has gap 0 for the heuristic AS DEFINED "
      "(so tab:rings and Example 2.3 are walk-frame values labelled H)",
      "tab:rings (l.1085), ex:ring-group (l.573)", [0] * 7,
      [H_true(ring(k), 3, Kstar(ring(k), 3)) - Zstar(ring(k), 3) for k in range(3, 10)])

print("\n[16] Can Proposition 3.2 be REPAIRED? g tool-disjoint copies of a true-gap seed")
seed = I1                                        # n=4, b=4, |U|=7, heuristic gap 1
obs = []
for g in (1, 2):
    T, off = [], 0
    for _ in range(g):
        T += [set(t + off for t in s) for s in seed]
        off += 7
    K = Kstar(T, 4)
    Z, ht = Zstar(T, 4), H_true(T, 4, K)
    obs.append((len(U_of(T)) - 4, Z, ht - Z))
    print(f"      g={g}: |U|={len(U_of(T))}  K*={K}  Z*={Z} (=|U|-b)  H={ht}  gap={ht-Z}")
check("copies of I1 give heuristic gap = g, so unboundedness survives with a "
      "different witness family (the 6-ring seed does not work)",
      "prop:unbounded (l.1096)", [1, 2], [o[2] for o in obs])

print("\n[17] The smallest instance with a positive gap for the heuristic as defined")
tiny = [{0, 1}, {2, 3}, {0, 2, 4, 5}, {1, 4, 5, 6}]
pt = profile(tiny, 4)
print(f"      n=4, b=4, |U|=7, T={[sorted(s) for s in tiny]}: "
      f"K*={pt['K']} Z*={pt['Z']} H={pt['Htrue']} gap={pt['Htrue']-pt['Z']}")
check("a 4-job instance has heuristic gap 1 while the 6-ring has gap 0, so the "
      "6-ring is not the smallest sub-optimal instance",
      "l.451", (1, 0), (pt["Htrue"] - pt["Z"],
                        H_true(ring(6), 3, 3) - Zstar(ring(6), 3)))
check("prop:oddring fails at k=3 (K* = 1, not ceil(3/2) = 2); it needs k >= 4",
      "prop:oddring (l.1558)", 2, Kstar(ring(3), 3))

print("\n" + "=" * 78)
npass = sum(1 for *_, ok in RESULTS if ok)
print(f"RESULT: {npass} passed, {len(RESULTS) - npass} failed, {len(RESULTS)} checks")
print("=" * 78)
if npass != len(RESULTS):
    print("\nFAILURES")
    for claim, where, exp, got, ok in RESULTS:
        if not ok:
            print(f"  {where}: {claim}\n      expected {exp}, got {got}")
sys.exit(0 if npass == len(RESULTS) else 1)
