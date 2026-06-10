import itertools, sys
from ssp_verify import ssp_opt, jgp_kstar, heuristic_H, analyse
def out(*a): print(*a); sys.stdout.flush()
def edges(m,me):
    E=list(itertools.combinations(range(m),2))
    for ne in range(2,me+1):
        for S in itertools.combinations(E,ne): yield [frozenset(e) for e in S]
out("b=4 edge family (m<=6,|E|<=6): max ratio / gap")
mr=1.0; arg=None; mg=0; argg=None; cnt=0
for m in (5,6):
    for js in edges(m,6):
        U=set().union(*js)
        if len(U)<4: continue
        Z=ssp_opt(js,4,U,method="ktns")
        if Z==0: continue
        H,_,_,_=heuristic_H(js,4,U=U); cnt+=1
        if H/Z>mr+1e-12: mr=H/Z; arg=([tuple(sorted(s)) for s in js],Z,H)
        if H-Z>mg: mg=H-Z; argg=([tuple(sorted(s)) for s in js],Z,H,jgp_kstar(js,4)[0],len(U))
out(f"  n={cnt} max_ratio={mr:.5f} max_gap={mg}")
out(f"  gap witness (edges,Z,H,K*,|U|)={argg}")
# b=4 analog "ring": tools 1..8, jobs of size 3 sliding window? try jobs {i,i+1,i+2} mod 8
for L,desc in [(8,"8 jobs {i,i+1,i+2} mod 8, tools 1..8, b=4")]:
    js=[frozenset({(i)%L,(i+1)%L,(i+2)%L}) for i in range(L)]
    r=analyse(js,4,desc); out(f"  {desc}: Z*={r['Z']} H={r['H']} K*={r['Kstar']} gap={r['gap']} ratio={r['ratio']:.4f} |U|={r['nT']}")
# b=4 size-2 ring 1..2b
js=[frozenset({i%8+1,(i%8)+2 if (i%8)+2<=8 else 1}) for i in range(8)]
out("Done b4.")
