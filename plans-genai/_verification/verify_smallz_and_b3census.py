import itertools, random
def ktns_empty(seq, Tj, b):
    # empty-start KTNS cost; evict tool with furthest next use
    n=len(seq); cost=0; mag=set()
    for i,j in enumerate(seq):
        need=Tj[j]-mag
        for t in need:
            if len(mag)>=b:
                # evict furthest next use among mag - Tj[j] (never evict currently needed)
                cand=mag-Tj[j]
                def nxt(u):
                    for k in range(i+1,n):
                        if u in Tj[seq[k]]: return k
                    return 10**9
                mag.remove(max(cand,key=nxt))
            mag.add(t); cost+=1
    return cost
def partitions(items):
    if not items: yield []; return
    first,rest=items[0],items[1:]
    for p in partitions(rest):
        for i in range(len(p)): yield p[:i]+[[first]+p[i]]+p[i+1:]
        yield p+[[first]]
def analyze(Tj_list,b):
    n=len(Tj_list); Tj={i:frozenset(Tj_list[i]) for i in range(n)}
    U=frozenset().union(*Tj.values())
    if len(U)<=b: return None
    q=len(U)-b
    Zs=min(ktns_empty(p,Tj,b) for p in itertools.permutations(range(n)))-min(b,len(U))
    feas=[]
    for P in partitions(list(range(n))):
        if all(len(frozenset().union(*(Tj[j] for j in g)))<=b for g in P): feas.append(P)
    Ks=min(len(P) for P in feas)
    minP=[P for P in feas if len(P)==Ks]
    Ul=lambda g: frozenset().union(*(Tj[j] for j in g))
    def configs(g):
        u=Ul(g); extra=sorted(U-u)
        return [u|frozenset(c) for c in itertools.combinations(extra,b-len(u))]
    def gamma(P):
        best=10**9
        for order in itertools.permutations(range(len(P))):
            for cs in itertools.product(*(configs(P[i]) for i in order)):
                c=sum(len(cs[k+1]-cs[k]) for k in range(len(cs)-1))
                best=min(best,c)
        return best
    H=min(gamma(P) for P in minP)
    res=dict(n=n,q=q,Z=Zs,K=Ks,H=H,gap=H-Zs,R=Zs-q)
    if Ks==3:
        # H formula: q + min wrap
        best=10**9
        for P in minP:
            for cs in itertools.product(*(configs(g) for g in P)):
                a,bb,c=cs
                w=min(len((a&c)-bb),len((a&bb)-c),len((bb&c)-a))
                best=min(best,w)
        res['Hf']=q+best
    return res
def rand_inst(n,m,szs):
    return [set(random.sample(range(m),random.choice(szs))) for _ in range(n)]

# (A) small-optimum: Z*<=2 => gap 0 ; (B) census: b=3 positive-gap by K*
import random
random.seed(3)
smallZ_bad=[]; census={}
def scan(instances,b):
    for Tj_list in instances:
        r=analyze(Tj_list,b)
        if r is None: continue
        if r['Z']<=2 and r['gap']!=0: smallZ_bad.append((Tj_list,r))
        if b==3 and r['gap']>0: census[r['K']]=census.get(r['K'],0)+1
for m in (4,5):
    edges=list(itertools.combinations(range(m),2))
    scan([[set(e) for e in es] for sz in range(1,6) for es in itertools.combinations(edges,sz)],3)
scan([rand_inst(random.choice([3,4,5]),6,[2,3]) for _ in range(400)],3)
scan([rand_inst(random.choice([4,5]),7,[2,3]) for _ in range(300)],3)
scan([rand_inst(random.choice([4,5]),8,[2,3]) for _ in range(250)],3)
scan([rand_inst(random.choice([4,5,6]),9,[2]) for _ in range(200)],3)
scan([rand_inst(random.choice([3,4,5]),7,[2,3,4]) for _ in range(250)],4)
print("Z*<=2 with gap>0:",len(smallZ_bad))
print("b=3 positive-gap census by K*:",census)

# ratios of b=3 positive-gap K*>=4 instances; hunt for ratio > 4/3
from fractions import Fraction
random.seed(3)
wit=[]
def scan2(instances,b):
    for Tj_list in instances:
        r=analyze(Tj_list,b)
        if r is None: continue
        if b==3 and r['gap']>0 and r['K']>=4:
            rat=Fraction(r['H'],r['Z'])
            wit.append((rat,sorted(sorted(t) for t in Tj_list),r))
for m in (4,5):
    edges=list(itertools.combinations(range(m),2))
    scan2([[set(e) for e in es] for sz in range(1,6) for es in itertools.combinations(edges,sz)],3)
scan2([rand_inst(random.choice([3,4,5]),6,[2,3]) for _ in range(400)],3)
scan2([rand_inst(random.choice([4,5]),7,[2,3]) for _ in range(300)],3)
scan2([rand_inst(random.choice([4,5]),8,[2,3]) for _ in range(250)],3)
scan2([rand_inst(random.choice([4,5,6]),9,[2]) for _ in range(200)],3)
wit.sort(key=lambda w:-w[0])
print("K*>=4 positive-gap b=3 instances:",len(wit),"max ratio:",wit[0][0] if wit else None)
for rat,tl,r in wit[:5]:
    print(" ratio=%s gap=%d Z=%d H=%d K=%d q=%d  T=%s"%(rat,r['gap'],r['Z'],r['H'],r['K'],r['q'],tl))
viol=[w for w in wit if w[0]>Fraction(4,3)]
print("VIOLATIONS of 4/3:",len(viol))

# (C) padding-reduction: K*=3 => H <= q + min over min-card groupings/orderings of |Va&Vc \ Vb|
# (D) corner hunt: K*=3, R=0, b=5, q in {3,4}: any gap >= 2?  (E) K*=4: any gap > 2?
def Ul(Tj,g): return frozenset().union(*(Tj[j] for j in g))
red_bad=[]; corner_max=0; corner_n=0; k4_max=(0,None)
def scan3(instances,b):
    global corner_max,corner_n,k4_max
    for Tj_list in instances:
        r=analyze(Tj_list,b)
        if r is None: continue
        Tj={i:frozenset(t) for i,t in enumerate(Tj_list)}
        if r['K']==3:
            best=10**9
            for P in [p for p in partitions(list(range(r['n']))) if len(p)==3 and all(len(Ul(Tj,g))<=b for g in p)]:
                V=[Ul(Tj,g) for g in P]
                for a,bb,c in itertools.permutations(range(3)):
                    best=min(best,len((V[a]&V[c])-V[bb]))
            if r['H']>r['q']+best: red_bad.append((Tj_list,r,best))
            if r['R']==0 and b==5 and r['q']>=3:
                corner_n+=1; corner_max=max(corner_max,r['gap'])
        if r['K']==4 and r['gap']>k4_max[0]: k4_max=(r['gap'],(Tj_list,r))
random.seed(99)
scan3([rand_inst(random.choice([3,4,5]),6,[2,3]) for _ in range(250)],3)
scan3([rand_inst(random.choice([3,4,5]),7,[2,3,4]) for _ in range(200)],4)
scan3([rand_inst(random.choice([4,5]),8,[2,3,4,5]) for _ in range(350)],5)
scan3([rand_inst(random.choice([4,5,6]),9,[2,3,4,5]) for _ in range(250)],5)
print("reduction H<=q+minx' violations:",len(red_bad))
print("CORNER (K*=3,R=0,b=5,q>=3): instances:",corner_n," max gap:",corner_max)
print("max K*=4 gap seen:",k4_max[0],"(conjecture allows 2)")
