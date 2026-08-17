"""
Conflict-graph structural cuts for the BBC master (SSP).
=======================================================

Motivation (advisor's suggestion, tied to report Section 3).  The BBC master's
lower bound on the switch cost theta is pairwise (w_ij) + coverage (|U|).  On
*bound-loose* instances the optimum exceeds |U|, and the missing information is
combinatorial:

  * The **conflict graph** G has a node per job and an edge (i,j) iff
    |T_i u T_j| > b, i.e. jobs i and j cannot share a magazine configuration.
    A feasible group is an *independent set* of G with union <= b, so any
    grouping into K groups is a proper K-colouring of G; hence
        chi(G) <= K*        (report Prop. "K* is a hypergraph chromatic number")
    and Z* >= K* - 1 (free-initial).  A lower bound on chi(G) — the clique
    number omega(G), bumped to 3 when G is non-bipartite (contains an odd
    hole) — is therefore a valid lower bound on the number of configurations,
    and feeds a constant lower bound on theta.

  * **Window / coverage inequalities** (a strict generalisation of the repo's
    triplet bounds w_ijk): if a set S of jobs is scheduled consecutively, the
    switches inside that block are at least |U(S)| - b, because all |U(S)|
    tools of the block must pass through a magazine of size b.  Guiding the
    search for such windows by dense subsets of the conflict graph is exactly
    the "conflict-graph based" lifting the advisor asked for.

Every cut produced here is returned in a solver-agnostic form and is
**brute-force validated** (see test_conflict_cuts / validate_cut_family): a
valid inequality must hold for *every* feasible sequence, not merely the
optimum.  A wrong cut would silently remove the optimum.

Cut representation
------------------
A cut is a dict:
    {"theta": 1.0, "arcs": {(i, j): coeff, ...}, "rhs": r, "sense": "G",
     "kind": "...", "viol": v}
meaning     1.0 * theta + sum coeff * x_ij   >=   r     (sense "G").
The BBC wiring turns this into a CPLEX SparsePair.

All costs are EMPTY-START (theta counts every insertion incl. the first load),
matching the BBC master and compute_ktns.
"""
from itertools import combinations


# ---------------------------------------------------------------------------
# Conflict graph
# ---------------------------------------------------------------------------
def build_conflict_graph(tool_req, n, b):
    """Return (adj, T) where adj[i] is the set of conflict-neighbours of i and
    T[i] is the tool set of job i.  Edge iff |T_i u T_j| > b."""
    T = [set(tool_req.get(i, ())) for i in range(n)]
    adj = {i: set() for i in range(n)}
    for i in range(n):
        for j in range(i + 1, n):
            if len(T[i] | T[j]) > b:
                adj[i].add(j)
                adj[j].add(i)
    return adj, T


# ---------------------------------------------------------------------------
# Clique number (exact Bron-Kerbosch for small n, greedy fallback otherwise)
# ---------------------------------------------------------------------------
def _bron_kerbosch(R, P, X, adj, best):
    if not P and not X:
        if len(R) > best[0]:
            best[0] = len(R)
            best[1] = set(R)
        return
    # pivot: vertex in P u X with most neighbours in P
    pivot = max(P | X, key=lambda u: len(adj[u] & P)) if (P | X) else None
    cand = P - adj[pivot] if pivot is not None else set(P)
    for v in list(cand):
        _bron_kerbosch(R | {v}, P & adj[v], X & adj[v], adj, best)
        P = P - {v}
        X = X | {v}


def max_clique(adj, n, exact_limit=28):
    """Return a maximum clique (exact for n<=exact_limit, else greedy)."""
    if n == 0:
        return set()
    if n <= exact_limit:
        best = [0, set()]
        _bron_kerbosch(set(), set(range(n)), set(), adj, best)
        return best[1]
    # greedy from each seed
    best = set()
    order = sorted(range(n), key=lambda u: len(adj[u]), reverse=True)
    for s in order:
        C = {s}
        cand = set(adj[s])
        while cand:
            u = max(cand, key=lambda x: len(adj[x] & cand))
            C.add(u)
            cand &= adj[u]
        if len(C) > len(best):
            best = C
    return best


def _is_bipartite(adj, n):
    colour = {}
    for s in range(n):
        if s in colour:
            continue
        colour[s] = 0
        stack = [s]
        while stack:
            u = stack.pop()
            for v in adj[u]:
                if v not in colour:
                    colour[v] = colour[u] ^ 1
                    stack.append(v)
                elif colour[v] == colour[u]:
                    return False
    return True


def chromatic_lower_bound(adj, n):
    """Valid lower bound on chi(G) (hence on K*).  Uses omega(G), bumped to 3
    when G is non-bipartite (i.e. contains an odd hole / odd cycle)."""
    if n == 0:
        return 0
    omega = len(max_clique(adj, n))
    has_edge = any(adj[i] for i in range(n))
    lb = max(omega, 2 if has_edge else 1)
    if lb < 3 and has_edge and not _is_bipartite(adj, n):
        lb = 3   # odd cycle => chi >= 3 (this is the odd-hole contribution)
    return lb


# ---------------------------------------------------------------------------
# Constant root lower bound on theta (empty-start)
# ---------------------------------------------------------------------------
def root_theta_lower_bound(tool_req, n, b):
    """A valid constant lower bound on the empty-start optimum Z*:
        max( |U|,  (K*_lb - 1) + min(b, |U|) )
    where K*_lb = chromatic_lower_bound(conflict graph) <= K*.
    Returns (lb, detail_dict)."""
    U = set()
    for i in range(n):
        U |= set(tool_req.get(i, ()))
    Usz = len(U)
    adj, _ = build_conflict_graph(tool_req, n, b)
    kstar_lb = chromatic_lower_bound(adj, n)
    grouping = (kstar_lb - 1) + min(b, Usz) if Usz else 0
    coverage = Usz                       # every used tool inserted >= once
    lb = max(coverage, grouping)
    return lb, {"U": Usz, "kstar_lb": kstar_lb, "coverage": coverage,
                "grouping": grouping, "b": b}


def root_bound_cut(tool_req, n, b, theta_bar=None):
    """Constant cut theta >= root_theta_lower_bound.  Returned only if it can
    improve on the plain coverage bound (grouping term strictly larger), so we
    never add a redundant row."""
    lb, det = root_theta_lower_bound(tool_req, n, b)
    if det["grouping"] <= det["coverage"]:
        return None                       # dominated by coverage row already in master
    viol = (lb - theta_bar) if theta_bar is not None else None
    return {"theta": 1.0, "arcs": {}, "rhs": float(lb), "sense": "G",
            "kind": "conflict-root", "viol": viol, "detail": det}


# ---------------------------------------------------------------------------
# Window / coverage inequalities  (generalise the triplet bounds)
# ---------------------------------------------------------------------------
def window_cut_for_path(path, T, b):
    """Window inequality for a directed path P = (p_0 -> ... -> p_{m-1}):

        theta  >=  c * ( sum_{t} x_{p_t, p_{t+1}}  -  (m - 2) ),
        c = |U(P)| - b   (only interesting when c > 0).

    Valid: if all m-1 arcs are active the m jobs are consecutive, so the block
    inserts at least |U(P)| - b tools (all |U(P)| tools pass a size-b
    magazine); theta counts those insertions.  When fewer arcs are active the
    right-hand side is <= 0 <= theta.  Returns the cut dict or None."""
    m = len(path)
    if m < 3:
        return None
    U = set()
    for p in path:
        U |= T[p]
    c = len(U) - b
    if c <= 0:
        return None
    arcs = {}
    for t in range(m - 1):
        arcs[(path[t], path[t + 1])] = arcs.get((path[t], path[t + 1]), 0.0) - float(c)
    rhs = -float(c) * (m - 2)
    return {"theta": 1.0, "arcs": arcs, "rhs": rhs, "sense": "G",
            "kind": f"window-{m}", "viol": None, "U": len(U), "c": c}


def _cut_lhs(cut, theta_bar, x_bar):
    v = cut["theta"] * theta_bar
    for (i, j), c in cut["arcs"].items():
        v += c * x_bar.get((i, j), 0.0)
    return v


def separate_window_cuts(x_bar, theta_bar, tool_req, n, b,
                         max_len=6, max_cuts=32, min_viol=1e-4,
                         arc_thresh=1e-3):
    """Greedily grow high-x_bar paths through conflict-dense jobs and emit the
    violated window inequalities.  x_bar maps (i,j)->value (job arcs; depot
    arcs ignored).  Returns a list of cut dicts, most-violated first."""
    adj, T = build_conflict_graph(tool_req, n, b)
    # candidate directed arcs: real jobs, positive x_bar
    arcs = [(i, j) for (i, j) in x_bar
            if i < n and j < n and i != j and x_bar[(i, j)] > arc_thresh]
    # successors sorted by x_bar for greedy extension
    succ = {}
    for (i, j) in arcs:
        succ.setdefault(i, []).append(j)
    for i in succ:
        succ[i].sort(key=lambda j: x_bar[(i, j)], reverse=True)

    found = {}
    # seed each conflicting arc, extend forward greedily while union grows
    for (i, j) in arcs:
        if len(T[i] | T[j]) <= b:
            continue                       # non-conflicting seed: skip
        path = [i, j]
        used = {i, j}
        while len(path) < max_len:
            last = path[-1]
            nxt = None
            for k in succ.get(last, []):
                if k not in used:
                    nxt = k
                    break
            if nxt is None:
                break
            path.append(nxt)
            used.add(nxt)
            cut = window_cut_for_path(path, T, b)
            if cut is None:
                continue
            lhs = _cut_lhs(cut, theta_bar, x_bar)
            viol = cut["rhs"] - lhs
            if viol > min_viol:
                key = tuple(path)
                cut["viol"] = viol
                if key not in found or found[key]["viol"] < viol:
                    found[key] = cut
    cuts = sorted(found.values(), key=lambda c: c["viol"], reverse=True)
    return cuts[:max_cuts]


# ---------------------------------------------------------------------------
# Atamturk-style sequential up-lifting of a window cut's constant term
# ---------------------------------------------------------------------------
def lift_window_cut(cut, path_jobs, T, b, n):
    """Sequential lifting: try to *increase* the coefficient magnitude on the
    path arcs by testing whether the tighter cut is still valid against the
    single-arc worst case.  Conservative: only strengthens when provably safe.
    (The base window cut is already valid; this is an optional tightening.)

    Currently a no-op placeholder that returns the (valid) input cut unchanged
    unless a strictly stronger coverage constant is certifiable.  Kept explicit
    so the lifting step is a named, testable component rather than hidden."""
    # A safe strengthening: if EVERY job on the path pairwise-conflicts (the
    # path is a clique in G), the block cannot borrow tools from outside, so the
    # constant may be lifted from |U|-b toward the grouping term.  We only apply
    # it when it passes the same validity contract, so we leave the base cut as
    # the guaranteed-valid object and expose the clique flag for the caller.
    is_clique = all(len(T[a] | T[c]) > b for a, c in combinations(path_jobs, 2))
    cut = dict(cut)
    cut["clique_path"] = is_clique
    return cut
