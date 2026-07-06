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
def run(instances,b,tag):
    cnt=0; bad=[]
    for Tj_list in instances:
        r=analyze(Tj_list,b)
        if r is None: continue
        cnt+=1
        if r['K']==3 and r['H']!=r.get('Hf'): bad.append(('A1',Tj_list,r))
        if r['Z']==r['q'] and r['q']<=r['K']-1 and r['gap']!=0: bad.append(('A2',Tj_list,r))
        if r['K']==3 and r['gap']>r['q']-r['R']: bad.append(('A3',Tj_list,r))
        if r['K']==3 and r['Z']==r['q']==3 and r['gap']>1: bad.append(('A4',Tj_list,r))
        if r['K']>=2 and r['gap']>r['K']-2: bad.append(('A5',Tj_list,r))
    print(tag,'instances:',cnt,'violations:',len(bad))
    for x in bad[:5]: print(x)
# edge family b=3, m=4 and m=5
for m in (4,5):
    edges=list(itertools.combinations(range(m),2))
    inst=[]
    for sz in range(1,6):
        for es in itertools.combinations(edges,sz): inst.append([set(e) for e in es])
    run(inst,3,f'edge m={m} b=3')

random.seed(42)
def rand_inst(n,m,szs):
    return [set(random.sample(range(m),random.choice(szs))) for _ in range(n)]
inst3=[rand_inst(random.choice([3,4,5]),6,[2,3]) for _ in range(400)]
run(inst3,3,'mixed b=3 m=6')
inst4=[rand_inst(random.choice([3,4,5]),7,[2,3,4]) for _ in range(300)]
run(inst4,4,'mixed b=4 m=7')
inst4b=[rand_inst(random.choice([4,5]),8,[2,3]) for _ in range(150)]
run(inst4b,4,'sparse b=4 m=8')

def run_count(instances,b,tag):
    cnt=0; bad=[]
    for Tj_list in instances:
        r=analyze(Tj_list,b)
        if r is None or r['K']!=3: continue
        cnt+=1
        bound=max(0,(2*b-r['q'])//3 - r['R'])
        if r['gap']>bound: bad.append((Tj_list,r,bound))
    print(tag,'K*=3 instances:',cnt,'violations:',len(bad))
    for x in bad[:3]: print(x)
random.seed(7)
for m in (4,5):
    edges=list(itertools.combinations(range(m),2))
    inst=[[set(e) for e in es] for sz in range(1,6) for es in itertools.combinations(edges,sz)]
    run_count(inst,3,f'edge m={m} b=3')
run_count([rand_inst(random.choice([3,4,5]),6,[2,3]) for _ in range(400)],3,'mixed b=3 m=6')
run_count([rand_inst(random.choice([4,5]),7,[2,3]) for _ in range(250)],3,'b=3 m=7 (q=4)')
run_count([rand_inst(random.choice([4,5]),8,[2]) for _ in range(200)],3,'b=3 m=8 (q=5)')
run_count([rand_inst(random.choice([3,4,5]),7,[2,3,4]) for _ in range(250)],4,'b=4 m=7')
run_count([rand_inst(random.choice([4,5]),9,[2,3]) for _ in range(150)],4,'b=4 m=9 (q=5)')
run_count([rand_inst(random.choice([3,4]),8,[2,3,4,5]) for _ in range(200)],5,'b=5 m=8')
