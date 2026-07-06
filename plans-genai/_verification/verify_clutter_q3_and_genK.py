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

# ---- Q3: does (b,|U|,n, circuit clutter up to iso) determine the gap? ----
def circuits(Tj_list,b):
    n=len(Tj_list); Tj=[frozenset(t) for t in Tj_list]
    circ=[]
    for r in range(2,n+1):
        for S in itertools.combinations(range(n),r):
            u=frozenset().union(*(Tj[j] for j in S))
            if len(u)>b and all(len(frozenset().union(*(Tj[j] for j in T)))<=b
                                 for T in itertools.combinations(S,r-1)):
                circ.append(frozenset(S))
    return circ
def canon(n,circ):
    best=None
    for p in itertools.permutations(range(n)):
        img=frozenset(frozenset(p[j] for j in S) for S in circ)
        key=tuple(sorted(tuple(sorted(s)) for s in img))
        if best is None or key<best: best=key
    return best
groups={}
def collect(instances,b,tag):
    for Tj_list in instances:
        r=analyze(Tj_list,b)
        if r is None: continue
        key=(b,len(frozenset().union(*(frozenset(t) for t in Tj_list))),r['n'],
             canon(r['n'],circuits(Tj_list,b)))
        groups.setdefault(key,set()).add(r['gap'])
random.seed(11)
edges5=list(itertools.combinations(range(5),2))
inst=[[set(e) for e in es] for sz in range(2,6) for es in itertools.combinations(edges5,sz)]
collect(inst,3,'edge5')
collect([rand_inst(random.choice([3,4]),6,[2,3]) for _ in range(250)],3,'mix6')
collect([rand_inst(random.choice([3,4]),7,[2,3,4]) for _ in range(150)],4,'mix7')
multi=[(k,v) for k,v in groups.items() if len(v)>1]
print("Q3: clutter classes:",len(groups)," classes with DIFFERENT gaps:",len(multi))
for k,v in multi[:4]:
    print("  counterexample class: b=%d |U|=%d n=%d gaps=%s circuits=%s"%(k[0],k[1],k[2],sorted(v),str(k[3])))

# ---- general-K* probabilistic bound ----
def run_gen(instances,b,tag):
    cnt=0; bad=[]
    for Tj_list in instances:
        r=analyze(Tj_list,b)
        if r is None or r['K']<2: continue
        cnt+=1
        k=r['K']; q=r['q']
        bound=max(0,(q*(b*(k-1)-q))//(b+q) - r['R'])
        if r['gap']>bound: bad.append((Tj_list,r,bound))
    print(tag,'K*>=2 instances:',cnt,'violations:',len(bad))
    for x in bad[:3]: print(x)
random.seed(13)
for m in (4,5):
    edges=list(itertools.combinations(range(m),2))
    inst=[[set(e) for e in es] for sz in range(1,6) for es in itertools.combinations(edges,sz)]
    run_gen(inst,3,f'edge m={m} b=3')
run_gen([rand_inst(random.choice([3,4,5]),6,[2,3]) for _ in range(300)],3,'mixed b=3 m=6')
run_gen([rand_inst(random.choice([4,5]),8,[2]) for _ in range(200)],3,'b=3 m=8')
run_gen([rand_inst(random.choice([3,4,5]),7,[2,3,4]) for _ in range(250)],4,'b=4 m=7')
run_gen([rand_inst(random.choice([4,5]),9,[2,3]) for _ in range(120)],4,'b=4 m=9')

# extract explicit witnesses for the Q3 counterexample class
target=None
for k,v in multi:
    if len(v)>1: target=k; break
random.seed(11)
seen={}
def hunt(instances,b):
    global seen
    for Tj_list in instances:
        r=analyze(Tj_list,b)
        if r is None: continue
        key=(b,len(frozenset().union(*(frozenset(t) for t in Tj_list))),r['n'],
             canon(r['n'],circuits(Tj_list,b)))
        if key==target and r['gap'] not in seen:
            seen[r['gap']]=(sorted(sorted(t) for t in Tj_list),r)
random.seed(11)
hunt([rand_inst(random.choice([3,4]),7,[2,3,4]) for _ in range(150)],4)
random.seed(11)
hunt([rand_inst(random.choice([3,4]),7,[2,3,4]) for _ in range(600)],4)
for g,(tl,r) in sorted(seen.items()):
    print("gap=%d  T_j=%s  Z*=%d H=%d K*=%d q=%d"%(g,tl,r['Z'],r['H'],r['K'],r['q']))
