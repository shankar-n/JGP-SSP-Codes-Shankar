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

import random
def rand_inst_U(n, U, szs):
    return [set(random.sample(U, random.choice(szs))) for _ in range(n)]

def hunt(b, usize, szs, n_range, trials, seed, want_gap):
    random.seed(seed)
    U=list(range(usize)); best=(0,None); cnt=0
    for _ in range(trials):
        inst=rand_inst_U(random.choice(n_range), U, szs)
        if len(set().union(*inst))!=usize: continue
        r=analyze(inst,b)
        if r is None or r['K']!=3: continue
        cnt+=1
        if r['gap']>best[0]: best=(r['gap'], (sorted(sorted(t) for t in inst), r))
        if r['gap']>=want_gap: break
    print(f"b={b} |U|={usize}: K*=3 instances={cnt}, max gap={best[0]} (bound target {want_gap})")
    if best[1]: print("   witness:", best[1][0], {k:best[1][1][k] for k in ('Z','H','q','K')})
# (5,3): counting bound floor((10-3)/3)=2 -> gap 2 target
#done1
#done2
# (6,3): counting bound floor((12-3)/3)=3 -> would give ratio 2 at K*=3
hunt(6, 9, [2,3,4,5,6], [4,5], 260, 5, 3)
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

import random, collections
def rand_inst(n,m,szs):
    return [set(random.sample(range(m),random.choice(szs))) for _ in range(n)]
surface=collections.defaultdict(int); viol=[]
def scan(instances,b):
    for inst in instances:
        r=analyze(inst,b)
        if r is None or r['K']!=3: continue
        key=(b,r['q'],r['R'])
        surface[key]=max(surface[key],r['gap'])
        if r['gap']>max(0,r['q']-2-r['R']): viol.append((inst,r))
random.seed(42)
for m in (4,5):
    edges=list(__import__('itertools').combinations(range(m),2))
    scan([[set(e) for e in es] for sz in range(1,6) for es in __import__('itertools').combinations(edges,sz)],3)
scan([rand_inst(random.choice([3,4,5]),6,[2,3]) for _ in range(350)],3)
scan([rand_inst(random.choice([4,5]),7,[2,3]) for _ in range(250)],3)
scan([rand_inst(random.choice([3,4,5]),7,[2,3,4]) for _ in range(250)],4)
scan([rand_inst(random.choice([4,5]),8,[2,3]) for _ in range(200)],4)
scan([rand_inst(random.choice([4,5]),8,[2,3,4,5]) for _ in range(250)],5)
scan([rand_inst(random.choice([4,5]),9,[2,3,4,5]) for _ in range(150)],5)
print("violations of gap <= max(0, q-2-R):", len(viol))
print("max gap per (b,q,R) [only entries with gap>0]:")
for k in sorted(surface):
    if surface[k]>0: print(f"  b={k[0]} q={k[1]} R={k[2]}: max gap {surface[k]}  (q-2-R = {k[1]-2-k[2]})")
import itertools
def lemma(b,q):
    U=set(range(b+q)); worst=-1
    subs=[set(c) for c in itertools.combinations(range(b+q),b)]
    for A,B,C in itertools.combinations_with_replacement(subs,3):
        if A|B|C!=U: continue
        m=min(len((A&B)-C),len((B&C)-A),len((A&C)-B))
        if m>worst: worst=m
    return worst
print("lemma: b<=2q-2 => min-x <= q-2")
for b,q in [(3,3),(4,3),(4,4),(5,4),(6,4),(4,5),(5,5)]:
    w=lemma(b,q)
    print(f"  b={b} q={q} (in-regime: {b<=2*q-2}): max min-x={w}, q-2={q-2}, {'OK' if (b>2*q-2 or w<=q-2) else 'VIOLATION'}")
