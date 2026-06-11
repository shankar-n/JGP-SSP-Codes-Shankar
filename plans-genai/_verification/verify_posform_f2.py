"""F2 (position-transition, diagonal-free, absorbing bottom) LP/IP test."""
import sys, itertools
import numpy as np
from scipy.optimize import milp, LinearConstraint, Bounds
sys.path.insert(0, "/sessions/peaceful-happy-lovelace/mnt/JGP-SSP-Codes-Shankar/plans-genai/_verification")
from ssp_verify import ssp_opt, jgp_kstar, ring
import random

def build_f2(js, b, T, counting=True):
    n = len(js); Tl = sorted(T)
    V = [frozenset(c) for c in itertools.combinations(Tl, b)]
    BOT = len(V)  # absorbing dummy
    pairs = [(i,j) for i in range(len(V)) for j in range(len(V)) if i!=j]
    pairs += [(i,BOT) for i in range(len(V))] + [(BOT,BOT)]
    S = n-1  # steps
    zi = {}; cnt=0
    for k in range(S):
        for pi,_ in enumerate(pairs): zi[pi,k]=cnt; cnt+=1
    nv=cnt; c=np.zeros(nv)
    for k in range(S):
        for pi,(i,j) in enumerate(pairs):
            c[zi[pi,k]] = 0.0 if (j==BOT or i==BOT) else len(V[j]-V[i])
    Aeq,beq,Aub,bub=[],[],[],[]
    for k in range(S):                                  # one pair per step
        r=np.zeros(nv)
        for pi in range(len(pairs)): r[zi[pi,k]]=1
        Aeq.append(r); beq.append(1.0)
    for k in range(S-1):                                # consistency head(k)=tail(k+1), per tool; + BOT absorption
        for t in Tl:
            r=np.zeros(nv)
            for pi,(i,j) in enumerate(pairs):
                if j!=BOT and t in V[j]: r[zi[pi,k]] += 1
                if i!=BOT and t in V[i]: r[zi[pi,k+1]] -= 1
            Aeq.append(r); beq.append(0.0)
        # absorption: BOT-head mass at k <= BOT-tail mass at k+1
        r=np.zeros(nv)
        for pi,(i,j) in enumerate(pairs):
            if j==BOT: r[zi[pi,k]] += 1
            if i==BOT: r[zi[pi,k+1]] -= 1
        Aub.append(r); bub.append(0.0)
    for jb,Tj in enumerate(js):                         # coverage: tail of step1 + heads
        r=np.zeros(nv)
        for pi,(i,j) in enumerate(pairs):
            if i!=BOT and Tj <= V[i]: r[zi[pi,0]] -= 1
        for k in range(S):
            for pi,(i,j) in enumerate(pairs):
                if j!=BOT and Tj <= V[j]: r[zi[pi,k]] -= 1
        Aub.append(r); bub.append(-1.0)
    if counting:                                        # per-tool counting rows
        for t in Tl:
            r=np.zeros(nv)
            for k in range(S):
                for pi,(i,j) in enumerate(pairs):
                    if j!=BOT and t in V[j] and (i==BOT or t not in V[i]):
                        r[zi[pi,k]] -= 1                # insertions of t
            for pi,(i,j) in enumerate(pairs):
                if i!=BOT and t in V[i]: r[zi[pi,0]] -= 1   # tail-of-step-1
            Aub.append(r); bub.append(-1.0)
    return c,Aeq,beq,Aub,bub,nv

def solve(bo, integer):
    c,Aeq,beq,Aub,bub,nv=bo
    cons=[LinearConstraint(np.array(Aeq),beq,beq),LinearConstraint(np.array(Aub),-np.inf,bub)]
    r=milp(c,constraints=cons,integrality=np.full(nv,1 if integer else 0),bounds=Bounds(0,np.inf))
    assert r.status==0, r.message
    return r.fun

# find an instance with Z* > max(K*-1, |U|-b)
random.seed(9); viol=None
for _ in range(400):
    js=[frozenset(random.sample(range(5),random.randint(2,3))) for _ in range(random.randint(4,5))]
    U=set().union(*js)
    if len(U)<=3: continue
    Z=ssp_opt(js,3,U); K,_=jgp_kstar(js,3)
    if Z > max(K-1,len(U)-3): viol=("above-bounds",js,3,Z); break
cases=[("6-ring",ring(6),3,3)]
if viol: cases.append(viol)
print(f"{'inst':12} {'Z*':>3} {'IP(F2)':>6} {'LP(F2+cnt)':>10} {'LP(F2-cnt)':>10} {'|U|-b':>5}")
for name,js,b,Z in cases:
    U=sorted(set().union(*js))
    bo=build_f2(js,b,U,True); bo0=build_f2(js,b,U,False)
    ip=solve(bo,True); lp=solve(bo,False); lp0=solve(bo0,False)
    print(f"{name:12} {Z:>3} {ip:>6.1f} {lp:>10.2f} {lp0:>10.2f} {len(U)-b:>5}")
