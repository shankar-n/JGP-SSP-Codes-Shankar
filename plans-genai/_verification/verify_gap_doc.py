"""Verification of claims in plans-genai/05_jgp_ssp_gap_analysis.tex (Claude-Fable, 2026-06-10)."""
import sys, itertools
sys.path.insert(0, "/sessions/peaceful-happy-lovelace/mnt/JGP-SSP-Codes-Shankar/plans-genai/_verification")
from ssp_verify import ring, ssp_opt, jgp_kstar, heuristic_H, gtsp_opt_for_partition

# --- Check A: rings table k=3..8 (Z*, H, K*) ---
expect = {3: (0, 0, 1), 4: (1, 1, 2), 5: (2, 2, 3), 6: (3, 4, 3), 7: (4, 5, 4), 8: (5, 6, 4)}
for k, (ez, eh, ek) in expect.items():
    js = ring(k); U = set().union(*js)
    z = ssp_opt(js, 3, U); K, parts = jgp_kstar(js, 3); h = heuristic_H(js, 3, K, U, parts)[0]
    ok = (z, h, K) == (ez, eh, ek)
    print(f"ring k={k}: Z*={z} H={h} K*={K}  {'OK' if ok else 'MISMATCH expect ' + str((ez, eh, ek))}")
    assert ok

# --- Check B: 6-ring, all feasible partitions; counts and min GTSP per K ---
js = ring(6); U = set().union(*js); b = 3
def feasible(G): return len(set().union(*[js[j] for j in G])) <= b
def partitions(items):
    if not items: yield []; return
    first, rest = items[0], items[1:]
    for sub in partitions(rest):
        for i, G in enumerate(sub):
            if feasible(G | {first}):
                yield sub[:i] + [G | {first}] + sub[i+1:]
        if feasible({first}): yield [{first}] + sub
all_parts = [p for p in partitions(list(range(6)))]
print(f"6-ring: {len(all_parts)} feasible partitions (doc: 18)")
assert len(all_parts) == 18
byK = {}
for p in all_parts:
    part = [frozenset(g) for g in p]
    cost = gtsp_opt_for_partition(part, js, U, b)
    byK.setdefault(len(p), []).append(cost)
for K in sorted(byK): print(f"  K={K}: {len(byK[K])} groupings, min GTSP = {min(byK[K])}")
assert min(byK[3]) == 4 and min(byK[4]) == 3 and min(min(v) for v in byK.values()) == 3

# --- Check C: thm:subopt explicit path (configs cover groups; cost 3) ---
cfgs = [{1,2,3},{1,3,6},{3,5,6},{3,4,5}]; grps = [{1,2,3},{6,1},{5,6},{3,4,5}]  # required sets
assert all(set(g) <= set(c) for g, c in zip(grps, cfgs))
cost = sum(len(set(b_) - set(a_)) for a_, b_ in zip(cfgs, cfgs[1:]))
print(f"thm:subopt path cost = {cost} (doc: 3)"); assert cost == 3

# --- Check D: retraction triple T1={1,2,3} T2={1,2,4} T3={3,4,5}, b=3 ---
js3 = [frozenset({1,2,3}), frozenset({1,2,4}), frozenset({3,4,5})]; U3 = {1,2,3,4,5}
z = ssp_opt(js3, 3, U3); K, parts = jgp_kstar(js3, 3); h = heuristic_H(js3, 3, K, U3, parts)[0]
print(f"retraction triple: Z*={z} H={h} K*={K} (doc: H=3, gap 0, K*=3)")
assert (z, h, K) == (3, 3, 3)
# R: in order T1->T2->T3, tool 3 in T1 and T3 but not T2 (zero slack -> evicted): R=1 > H/4
assert 3 in js3[0] and 3 in js3[2] and 3 not in js3[1]
print("R=1 > H/4 = 0.75 -> sum R_k <= H/4 refuted, as documented")

# --- Check E: thm:grouping_exact on 6-ring: min over ALL groupings == Z* ---
assert min(min(v) for v in byK.values()) == ssp_opt(js, 3, U) == 3
print("grouping exactness holds on 6-ring (min over all groupings = Z* = 3)")
print("ALL CHECKS PASSED")
