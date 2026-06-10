#!/usr/bin/env python3
"""Theorem-candidate probes. ASCII only."""
import itertools, sys
from ssp_verify import ssp_opt, jgp_kstar, heuristic_H, analyse, ring
def out(*a): print(*a); sys.stdout.flush()

def edge_instances(m, max_e):
    edges=list(itertools.combinations(range(m),2))
    for ne in range(2,max_e+1):
        for E in itertools.combinations(edges,ne):
            yield [frozenset(e) for e in E]

def subset_instances(m, sizes, n_max):
    """jobs = distinct subsets of [m] with size in 'sizes'; up to n_max jobs."""
    pool=[]
    for k in sizes:
        pool+=[frozenset(c) for c in itertools.combinations(range(m),k)]
    for ne in range(2,n_max+1):
        for E in itertools.combinations(pool,ne):
            yield list(E)

out("="*78); out("PROBE 1 (b=3 edge family m<=6,|E|<=6): is  Z* == max(K*-1, |U|-b) ?"); out("="*78)
viol=0; tot=0; gt_both=0; maxratio=1.0; argmax=None
for m in (4,5,6):
    for js in edge_instances(m,6):
        U=set().union(*js)
        if len(U)<3: continue
        Z=ssp_opt(js,3,U,method="ktns")
        if Z==0: continue
        K,_=jgp_kstar(js,3)
        lb=max(K-1, len(U)-3)
        tot+=1
        if Z!=lb: viol+=1
        if Z>K-1 and Z>len(U)-3: gt_both+=1   # both bounds strict
        H,_,_,_=heuristic_H(js,3,U=U)
        r=H/Z
        if r>maxratio+1e-12: maxratio=r; argmax=[tuple(sorted(s)) for s in js]
out(f"  instances={tot}  violations of Z*==max(K*-1,|U|-b): {viol}")
out(f"  instances where BOTH lower bounds are strict (Z* > each): {gt_both}")
out(f"  -> conjecture Z* = max(K*-1, |U|-b): {'HOLDS' if viol==0 else 'FAILS'} on this family")
out(f"  max ratio={maxratio:.5f}")

out(""); out("="*78); out("PROBE 2 (b=3, jobs = subsets size in {2,3}, m<=5, n<=5): max ratio, Z* formula"); out("="*78)
viol2=0; tot2=0; maxr2=1.0; arg2=None; maxgap=0; arggap=None
for js in subset_instances(5,(2,3),5):
    U=set().union(*js)
    if len(U)<3: continue
    Z=ssp_opt(js,3,U,method="dp")
    if Z==0: continue
    K,_=jgp_kstar(js,3)
    lb=max(K-1,len(U)-3); tot2+=1
    if Z!=lb: viol2+=1
    H,_,_,_=heuristic_H(js,3,U=U)
    r=H/Z; g=H-Z
    if r>maxr2+1e-12: maxr2=r; arg2=([tuple(sorted(s)) for s in js],Z,H,K,len(U))
    if g>maxgap: maxgap=g; arggap=([tuple(sorted(s)) for s in js],Z,H,K,len(U))
out(f"  instances={tot2}  Z*==max(K*-1,|U|-b) violations: {viol2}")
out(f"  max ratio={maxr2:.5f}  witness={arg2}")
out(f"  max gap={maxgap}  witness={arggap}")

out(""); out("="*78); out("PROBE 3 (b=4): max ratio on edge family (|T_j|=2) and triple family (|T_j|=3)"); out("="*78)
for fam,gen in [("edges m<=7,|E|<=7", edge_instances(7,7)),
                ("size{2,3} m<=6,n<=6", subset_instances(6,(2,3),6))]:
    maxr=1.0; arg=None; maxg=0; argg=None; cnt=0; viol4=0
    for js in gen:
        U=set().union(*js)
        if len(U)<4: continue
        Z=ssp_opt(js,4,U,method="ktns")
        if Z==0: continue
        K,_=jgp_kstar(js,4)
        if Z!=max(K-1,len(U)-4): viol4+=1
        H,_,_,_=heuristic_H(js,4,U=U)
        cnt+=1; r=H/Z; g=H-Z
        if r>maxr+1e-12: maxr=r; arg=([tuple(sorted(s)) for s in js],Z,H,K,len(U))
        if g>maxg: maxg=g; argg=([tuple(sorted(s)) for s in js],Z,H,K,len(U))
    out(f"  b=4 {fam}: n={cnt} maxratio={maxr:.5f} (5/4={5/4}) maxgap={maxg}")
    out(f"     Z*=max(K*-1,|U|-b) violations: {viol4}")
    out(f"     ratio witness={arg}")
out(""); out("Done probes.")
