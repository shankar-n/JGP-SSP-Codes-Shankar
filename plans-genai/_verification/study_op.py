#!/usr/bin/env python3
"""Research on the open problems. Run a section: python3 study_op.py [op4|op1|op2|op6]."""
import itertools, sys, random
from ssp_verify import (tooling_cost, ssp_opt, jgp_kstar, heuristic_H, group_clusters,
                        gtsp_opt_for_partition, ring, analyse, conflict_graph, chromatic_number)
def out(*a): print(*a); sys.stdout.flush()

def all_feasible_partitions(job_sets, b):
    n=len(job_sets); res=[]; a=[0]*n
    def rec(i,k):
        if i==n:
            g={}
            for idx,c in enumerate(a): g.setdefault(c,[]).append(idx)
            for c in g.values():
                u=set()
                for x in c: u|=job_sets[x]
                if len(u)>b: return
            res.append([frozenset(c) for c in g.values()]); return
        for c in range(k+1):
            a[i]=c; rec(i+1, max(k,c+1))
    rec(0,0); return res

def opt_via_any_grouping(job_sets,b,U):
    best=None
    for part in all_feasible_partitions(job_sets,b):
        c=gtsp_opt_for_partition(part, job_sets, U, b)
        if best is None or (c is not None and c<best): best=c
    return best

def edge_instances(m,me):
    E=list(itertools.combinations(range(m),2))
    for ne in range(2,me+1):
        for S in itertools.combinations(E,ne): yield [frozenset(e) for e in S]

def subset_instances(m,sizes,nmax):
    pool=[]
    for k in sizes: pool+=[frozenset(c) for c in itertools.combinations(range(m),k)]
    for ne in range(2,nmax+1):
        for S in itertools.combinations(pool,ne): yield list(S)

def op4():
    out("="*78); out("OP4 -- Z*_SSP == min over ALL feasible groupings of GTSP cost ?"); out("="*78)
    viol=0; tot=0; ex=[]; random.seed(1)
    for m in (4,5):
        for js in edge_instances(m,5):
            U=set().union(*js)
            if len(U)<3: continue
            Z=ssp_opt(js,3,U,method="ktns"); G=opt_via_any_grouping(js,3,U); tot+=1
            if Z!=G:
                viol+=1
                if len(ex)<5: ex.append(([tuple(sorted(s)) for s in js],Z,G))
    for _ in range(800):
        bb=random.choice([3,4]); m=random.randint(3,6); nj=random.randint(2,5)
        js=[frozenset(random.sample(range(m),random.randint(1,min(bb,m)))) for _ in range(nj)]
        U=set().union(*js)
        if len(U)<bb: continue
        Z=ssp_opt(js,bb,U,method="ktns"); G=opt_via_any_grouping(js,bb,U); tot+=1
        if Z!=G:
            viol+=1
            if len(ex)<5: ex.append(([tuple(sorted(s)) for s in js],Z,G,bb))
    out(f"  instances tested: {tot}   violations: {viol}")
    out("  examples: "+str(ex) if ex else "  NO violations -> Z* = min over ALL groupings (theorem confirmed)")
    # corollary: among positive-gap (vs JGP-optimal heuristic), does ANY grouping reach Z*?
    pos=0; closed=0
    for m in (4,5):
        for js in edge_instances(m,5):
            U=set().union(*js)
            if len(U)<3: continue
            Z=ssp_opt(js,3,U,method="ktns"); H,_,_,_=heuristic_H(js,3,U=U)
            if H-Z>0:
                pos+=1
                if opt_via_any_grouping(js,3,U)==Z: closed+=1
    out(f"  positive-gap instances: {pos}; gap fully closed by some (sub-optimal) grouping: {closed}")

def op1():
    out("="*78); out("OP1 -- widen 4/3 search for b=3 (size-3 jobs, larger m)"); out("="*78)
    maxr=1.0; arg=None; over=0; cnt=0
    for js in subset_instances(6,(2,3),5):
        U=set().union(*js)
        if len(U)<3: continue
        Z=ssp_opt(js,3,U,method="ktns")
        if Z==0: continue
        H,_,_,_=heuristic_H(js,3,U=U); cnt+=1; r=H/Z
        if r>maxr+1e-12: maxr=r; arg=([tuple(sorted(s)) for s in js],Z,H)
        if r>4/3+1e-9: over+=1
    out(f"  instances={cnt}  max ratio={maxr:.5f}  (#>4/3={over})  witness={arg}")

def op2():
    out("="*78); out("OP2 -- extremal ratio vs b (small searches + constructed rings)"); out("="*78)
    # b=3,4,5 edge family small; plus constructed sliding rings
    for bb in (3,4,5):
        mr=1.0; arg=None
        for js in edge_instances(min(2*bb,6), min(2*bb,6)):
            U=set().union(*js)
            if len(U)<bb: continue
            Z=ssp_opt(js,bb,U,method="ktns")
            if Z==0: continue
            H,_,_,_=heuristic_H(js,bb,U=U); r=H/Z
            if r>mr+1e-12: mr=r; arg=(len(U),Z,H)
        out(f"  b={bb} 2-tool edge family: max ratio={mr:.4f} (|U|,Z,H)={arg}")
    # constructed: tools 1..2b, jobs = b-1 sliding windows? try 'w-window ring'
    out("  constructed sliding rings (n jobs of size w=b-1 mod 2b):")
    for bb in (3,4,5):
        L=2*bb; w=bb-1
        js=[frozenset((i+t)%L+1 for t in range(w)) for i in range(L)]
        r=analyse(js,bb)
        out(f"    b={bb}: |U|={r['nT']} Z*={r['Z']} H={r['H']} K*={r['Kstar']} ratio={r['ratio']:.4f}")

if __name__=="__main__":
    sec=sys.argv[1] if len(sys.argv)>1 else "op4"
    {"op4":op4,"op1":op1,"op2":op2}[sec]()
