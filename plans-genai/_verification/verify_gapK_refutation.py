import itertools, random
# INDEPENDENT re-verification (fresh implementations)
def ktns(seq,Tj,b):
    n=len(seq); mag=set(); cost=0
    for i,j in enumerate(seq):
        for t in sorted(Tj[j]-mag):
            if len(mag)>=b:
                cand=mag-Tj[j]
                def nxt(u):
                    for k in range(i+1,n):
                        if u in Tj[seq[k]]: return k
                    return 10**9
                mag.remove(max(cand,key=nxt))
            mag.add(t); cost+=1
    return cost
def parts(items):
    if not items: yield []; return
    f,rest=items[0],items[1:]
    for p in parts(rest):
        for i in range(len(p)): yield p[:i]+[[f]+p[i]]+p[i+1:]
        yield p+[[f]]
def full(Tj_list,b):
    n=len(Tj_list); Tj={i:frozenset(t) for i,t in enumerate(Tj_list)}
    U=frozenset().union(*Tj.values()); q=len(U)-b
    Z=min(ktns(p,Tj,b) for p in itertools.permutations(range(n)))-min(b,len(U))
    feas=[P for P in parts(list(range(n))) if all(len(frozenset().union(*(Tj[j] for j in g)))<=b for g in P)]
    K=min(len(P) for P in feas)
    Ucfg=sorted(U)
    def cfgs(g):
        u=frozenset().union(*(Tj[j] for j in g))
        return [u|frozenset(c) for c in itertools.combinations([t for t in Ucfg if t not in u],b-len(u))]
    H=10**9
    for P in [P for P in feas if len(P)==K]:
        for order in itertools.permutations(range(K)):
            for cs in itertools.product(*(cfgs(P[i]) for i in order)):
                H=min(H,sum(len(cs[k+1]-cs[k]) for k in range(K-1)))
    return dict(q=q,U=len(U),Z=Z,K=K,H=H,gap=H-Z)
# regenerate the hunt to locate witnesses
def rand_inst(n,m,szs): return [set(random.sample(range(m),random.choice(szs))) for _ in range(n)]
random.seed(99)
batches=[( [rand_inst(random.choice([3,4,5]),6,[2,3]) for _ in range(250)],3),
         ([rand_inst(random.choice([3,4,5]),7,[2,3,4]) for _ in range(200)],4),
         ([rand_inst(random.choice([4,5]),8,[2,3,4,5]) for _ in range(350)],5),
         ([rand_inst(random.choice([4,5,6]),9,[2,3,4,5]) for _ in range(250)],5)]
found=[]
for inst,b in batches:
    for Tj_list in inst:
        Tj={i:frozenset(t) for i,t in enumerate(Tj_list)}
        U=frozenset().union(*Tj.values())
        if len(U)<=b: continue
        r=full(Tj_list,b)
        if r['K']==3 and r['gap']>=2:
            found.append((sorted(sorted(t) for t in Tj_list),b,r))
for tl,b,r in found[:6]:
    print("WITNESS b=%d  T=%s"%(b,tl))
    print("   |U|=%d q=%d Z*=%d(free) H=%d gap=%d K*=%d  count-bound=%d ratio=%s"%(
        r['U'],r['q'],r['Z'],r['H'],r['gap'],r['K'],(2*b-r['q'])//3,f"{r['H']}/{r['Z']}"))
print("total gap>=2 K*=3 witnesses:",len(found))
