import sys, os
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from pyscipopt import Model, quicksum, SCIP_PARAMSETTING
from pcf_prime_bp import branch_and_price
import pcf_prime_bp as M

def read(path):
    tok=open(path).read().split(); n,T,b=int(tok[0]),int(tok[1]),int(tok[2])
    v=list(map(int,tok[3:3+T*n]))
    return n,T,b,[set(t for t in range(T) if v[t*n+j]) for j in range(n)]

n,T,b,Tj = read('loose/L1-1.txt')
U=sorted({t for s in Tj for t in s})
print(f"L1-1  n={n} |T|={T} |U|={len(U)} b={b}   q_free=|U|-b={len(U)-b}")

# rebuild the master exactly as branch_and_price does, but keep handles so we can read the LP
import itertools, math
from pyscipopt import Model
m=Model(); m.setPresolve(SCIP_PARAMSETTING.OFF); m.setIntParam("presolving/maxrounds",0)
m.hideOutput(); m.setParam("limits/time",60)
w={(t,p):m.addVar(f"w_{t}_{p}",vtype="C",lb=0,obj=1.0) for t in range(T) for p in range(1,n)}
a={(t,p):m.addVar(f"a_{t}_{p}",vtype="C",lb=0,ub=1,obj=0) for t in range(T) for p in range(n)}
Vall=[frozenset(c) for c in itertools.combinations(range(T),b)]
print(f"configurations enumerated: {len(Vall)}")
y={C:{} for C in Vall}
yv={}
for C in Vall:
    for p in range(n):
        yv[(C,p)]=m.addVar(f"y_{hash(C)%10**6}_{p}",vtype="C",lb=0,ub=1,obj=0)
for p in range(n):
    m.addCons(quicksum(yv[(C,p)] for C in Vall)<=1)
for j in range(n):
    m.addCons(quicksum(yv[(C,p)] for C in Vall for p in range(n) if Tj[j]<=C)>=1)
for t in range(T):
    for p in range(n):
        m.addCons(a[(t,p)]-quicksum(yv[(C,p)] for C in Vall if t in C)==0)
for t in range(T):
    for p in range(1,n):
        m.addCons(w[(t,p)]-a[(t,p)]+a[(t,p-1)]>=0)
for t in U:
    m.addCons(quicksum(w[(t,p)] for p in range(1,n))+a[(t,0)]>=1)
m.setParam("limits/nodes",1); m.optimize()
print(f"\nfull-enumeration PCF' LP value = {m.getObjVal():.4f}   (q_free = {len(U)-b})")
av={(t,p):m.getVal(a[(t,p)]) for t in range(T) for p in range(n)}
print("\na[t,p] for the first 6 tools (rows) across positions (cols):")
for t in range(min(6,T)):
    print("  t=%-2d "%t + " ".join(f"{av[(t,p)]:.3f}" for p in range(n)))
print("\nis a[t,p] constant across p for each tool?")
flat=sum(1 for t in range(T) if max(av[(t,p)] for p in range(n))-min(av[(t,p)] for p in range(n))<1e-6)
print(f"  {flat} of {T} tools have a[t,.] identical at every position")
print("\nwindow row activity, W=[p,r], length 2..4:")
for length in (2,3,4):
    for p in range(1,n-length+1):
        r=p+length-1
        lhs=sum(m.getVal(w[(t,k)]) for t in U for k in range(p,r+1))
        zsum=sum(max(av[(t,k)] for k in range(p,r+1)) for t in U)
        prev=sum(av[(t,p-1)] for t in U)
        print(f"  W=[{p},{r}]  sum w = {lhs:7.3f}   sum max_k a = {zsum:7.3f}   "
              f"sum a[.,p-1] = {prev:7.3f}   ->  row = {lhs - zsum + prev:7.3f}  "
              f"{'BINDING' if abs(lhs-zsum+prev)<1e-6 else 'slack'}")
        if length==2 and p>=3: break
