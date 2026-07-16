#!/usr/bin/env python3
"""Verify lem:lowrho: for rho < 1/(n-1) every minimiser of switches + rho*changeovers
is switch-optimal. Brute force over (permutation, magazine-state sequence), n=4."""
import itertools, random
def brute_all(Tj,b,rho):
    n=len(Tj); U=sorted(set().union(*Tj.values()))
    cfgs=[frozenset(c) for c in itertools.combinations(U,b)]
    bestF=None; bestZ=None; argF=[]
    for perm in itertools.permutations(range(n)):
        cand=[[c for c in cfgs if Tj[j]<=c] for j in perm]
        for Ms in itertools.product(*cand):
            sw=len(Ms[0])+sum(len(Ms[i]-Ms[i-1]) for i in range(1,n))
            ch=sum(1 for i in range(1,n) if Ms[i]!=Ms[i-1])
            F=sw+rho*ch
            if bestZ is None or sw<bestZ: bestZ=sw
            if bestF is None or F<bestF-1e-12: bestF,argF=F,[(sw,ch)]
            elif abs(F-bestF)<1e-12: argF.append((sw,ch))
    return bestZ,argF
random.seed(5); bad=0
for _ in range(40):
    Tj={i:frozenset(random.sample(range(5),random.choice([1,2,3]))) for i in range(4)}
    Z,arg=brute_all(Tj,3,1.0/6)
    if any(sw!=Z for sw,ch in arg): bad+=1; print("VIOLATION",dict(Tj))
print("low-rho lemma: 40 instances, violations =",bad)
