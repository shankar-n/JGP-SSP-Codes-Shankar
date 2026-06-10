#!/usr/bin/env python3
"""Driver: verifies documented claims and runs the gap/ratio search. ASCII only.
Run: python3 -u run_study.py"""
import itertools, sys, random
from collections import Counter
from ssp_verify import (tooling_cost, ktns_cost, ssp_opt, conflict_graph,
                        chromatic_number, heuristic_H, analyse, ring, components)

def out(*a): print(*a); sys.stdout.flush()

# ---------------------------------------------------------------- PART A
out("="*78); out("PART A -- Re-verify documented examples (exact DP)"); out("="*78)
r6 = analyse(ring(6), 3, "6-ring"); out(r6)
assert (r6['Z'],r6['H'],r6['Kstar'],r6['gap'])==(3,4,3,1), "6-ring mismatch"
r5 = analyse(ring(5), 3, "5-ring"); out(r5)
assert (r5['Z'],r5['H'],r5['Kstar'],r5['gap'])==(2,2,3,0), "5-ring mismatch"
rce = analyse([frozenset("abc"),frozenset("abd"),frozenset("cde")], 3, "ABC/ABD/CDE"); out(rce)
assert r6['Z']==r6['lb_tools'] and r5['Z']==r5['lb_tools'], "LB |U|-b not tight on rings"
out("  rings: Z* == |U|-b  (tool lower bound is TIGHT on both)")

# ---------------------------------------------------------------- PART A2  KTNS == DP
out(""); out("="*78); out("PART A2 -- Validate fast KTNS == exact DP (random fuzz)"); out("="*78)
random.seed(7); bad=0; tested=0
for _ in range(4000):
    m=random.randint(3,7); bb=random.randint(2,4); nj=random.randint(2,6)
    Uall=list(range(m))
    js=[frozenset(random.sample(Uall, random.randint(1,min(bb,m)))) for _ in range(nj)]
    Uu=set().union(*js)
    seq=list(js)
    for _ in range(2):
        random.shuffle(seq)
        if tooling_cost(seq,Uu,bb)!=ktns_cost(seq,bb): bad+=1
        tested+=1
out(f"  {tested} random sequences, {bad} KTNS-vs-DP disagreements")
assert bad==0, "KTNS disagrees with exact DP!"
out("  KTNS VALIDATED -> safe to use for the larger search")

# ---------------------------------------------------------------- PART B  copy-paste
out(""); out("="*78); out("PART B -- Copy-paste family: gap unbounded; Z*=6g-3=|U|-b; H=7g-3"); out("="*78)
def copies(g):
    js=[]
    for ell in range(g):
        base=6*ell; js+=[frozenset({base+i, base+(i%6)+1}) for i in range(1,7)]
    return js
r1=analyse(copies(1),3); out(f"g=1 (exact): Z*={r1['Z']} H={r1['H']} K*={r1['Kstar']} gap={r1['gap']}")
assert (r1['Z'],r1['H'],r1['gap'])==(3,4,1)
for g in (2,3,4):
    js=copies(g); U=set().union(*js)
    lb=len(U)-3
    zsched=tooling_cost(list(js),U,3)              # contiguous blocks => achievable schedule
    comp=components(js); Hsum=sum(heuristic_H([js[i] for i in c],3)[0] for c in comp)
    Htot=Hsum+3*(len(comp)-1)
    out(f"g={g}: |U|-b={lb} (pred 6g-3={6*g-3}); schedule achieves Z*<= {zsched}; "
        f"=> Z*={lb}; H={Htot} (pred 7g-3={7*g-3}); gap={Htot-lb} (pred {g}); ratio={Htot/lb:.4f}")
    assert lb==6*g-3 and zsched==lb and Htot==7*g-3 and (Htot-lb)==g, f"copy-paste g={g} FAIL"
out("Copy-paste VERIFIED (g=1 exact; g=2..4 via tight LB + explicit schedule + decomposition).")
out("  ratio (7g-3)/(6g-3) is strictly decreasing -> 7/6 as g->inf; max at g=1 = 4/3.")

# ---------------------------------------------------------------- PART C  exhaustive b=3 search
out(""); out("="*78)
out("PART C -- Exhaustive b=3 search: tools=vertices, jobs=edges (|T_j|=2)")
out("           Question: can ratio H/Z* exceed 4/3 ? can gap exceed 1 ?")
out("="*78)
def edge_instances(m, max_edges):
    edges=list(itertools.combinations(range(m),2))
    for ne in range(2, max_edges+1):
        for E in itertools.combinations(edges, ne):
            yield [frozenset(e) for e in E]
best_ratio=(1.0,None); best_gap=(0,None); seen=0; over43=[]
gap_by_kstar=Counter(); zero=0; nonzero=0
for m in (4,5,6):
    for js in edge_instances(m,6):
        U=set().union(*js)
        if len(U)<3: continue
        Z=ssp_opt(js,3,U,method="ktns")
        if Z==0: continue
        H,Kstar,_,_=heuristic_H(js,3,U=U)
        seen+=1; gap=H-Z; ratio=H/Z
        if ratio>best_ratio[0]+1e-9: best_ratio=(ratio,(m,[tuple(sorted(s)) for s in js],Z,H,Kstar))
        if gap>best_gap[0]: best_gap=(gap,(m,[tuple(sorted(s)) for s in js],Z,H,Kstar))
        if ratio>4/3+1e-9: over43.append((m,[tuple(sorted(s)) for s in js],Z,H,Kstar))
        if gap==0: zero+=1
        else: nonzero+=1; gap_by_kstar[Kstar]+=1
out(f"  instances analysed: {seen}")
out(f"  MAX ratio H/Z* = {best_ratio[0]:.5f}")
out(f"     witness (m, edges, Z*, H, K*) = {best_ratio[1]}")
out(f"  MAX gap  H-Z*  = {best_gap[0]}")
out(f"     witness (m, edges, Z*, H, K*) = {best_gap[1]}")
out(f"  # instances with ratio > 4/3 : {len(over43)}")
if over43: out("   !!! 4/3 EXCEEDED:", over43[:5])
out(f"  zero-gap: {zero}   nonzero-gap: {nonzero}   (nonzero by K*: {dict(gap_by_kstar)})")
out("  4/3 CONJECTURE on edge family (m<=6,|E|<=6): " + ("HOLDS" if not over43 else "REFUTED"))

# ---------------------------------------------------------------- PART D  zero-gap structure
out(""); out("="*78)
out("PART D -- Zero-gap structure. Z* >= max(K*-1, |U|-b). Test a sufficient condition:")
out("  CONJECTURE: gap=0 whenever the conflict graph has an ODD HOLE structure that lets")
out("  Z* dip to K*-2, OR more simply test: gap>0  =>  what is K*?")
out("="*78)
# For each nonzero-gap instance, record (K*, Z*, H, |U|, gap) and whether Z*==K*-1
buckets=Counter(); pos_examples=[]
ring_like=[]
for m in (4,5,6):
    for js in edge_instances(m,6):
        U=set().union(*js)
        if len(U)<3: continue
        Z=ssp_opt(js,3,U,method="ktns")
        if Z==0: continue
        H,Kstar,_,_=heuristic_H(js,3,U=U)
        gap=H-Z
        key=('gap0' if gap==0 else 'gap+', f"Z*={'K*-1' if Z==Kstar-1 else ('|U|-b' if Z==len(U)-3 else 'other')}")
        buckets[key]+=1
        if gap>0 and len(pos_examples)<12:
            pos_examples.append(([tuple(sorted(s)) for s in js],dict(Z=Z,H=H,Kstar=Kstar,nU=len(U),gap=gap)))
out("  buckets (gap-class, where-Z*-sits):")
for k,v in sorted(buckets.items()): out(f"    {k}: {v}")
out("  sample positive-gap instances:")
for e in pos_examples[:12]: out("    "+str(e))

# Targeted: rings 3..8
out(""); out("  Rings k=3..8 (b=3):")
for k in range(3,9):
    rk=analyse(ring(k),3,f"{k}-ring")
    out(f"    {k}-ring: Z*={rk['Z']} H={rk['H']} K*={rk['Kstar']} gap={rk['gap']} ratio={rk['ratio']:.4f}")
out(""); out("Done.")
