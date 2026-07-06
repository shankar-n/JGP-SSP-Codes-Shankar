import itertools
# LEMMA test: for any three b-subsets of a (b+q)-set covering it,
# min over orderings of |(Cu & Cv) - Cw| is at most floor((2b-q)/3).
def lemma(b,q):
    U=range(b+q); worst=-1
    subs=list(itertools.combinations(U,b))
    for A in subs:
        for B in subs:
            for C in subs:
                sA,sB,sC=set(A),set(B),set(C)
                if sA|sB|sC!=set(U): continue
                m=min(len((sA&sB)-sC),len((sB&sC)-sA),len((sA&sC)-sB))
                worst=max(worst,m)
    return worst
for b,q in [(3,1),(3,2),(3,3),(3,4),(3,5),(3,6),(4,2),(4,3),(4,4),(4,5),(5,2),(5,3),(5,4),(6,3)]:
    w=lemma(b,q); bound=(2*b-q)//3
    print(f"b={b} q={q}: max min-overlap = {w}, bound floor((2b-q)/3) = {bound}, {'OK' if w<=bound else 'VIOLATION'}")
