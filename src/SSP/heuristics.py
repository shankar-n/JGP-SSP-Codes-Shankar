"""
SSP Heuristics and Upper-Bound Computations
============================================

Provides construction heuristics and local-search improvements for the
Job Sequencing and Tool Switching Problem (SSP).

All methods produce *upper bounds* on the optimum (feasible solutions).
The true optimum is obtained by the exact solvers in BBC/, LSS, SSPMF.

References
----------
Crama et al. (1994) describe the KTNS policy as the optimal tooling
strategy for a *fixed* sequence.  Given KTNS, any permutation heuristic
that produces a good job ordering yields a valid upper bound.

Methods implemented
-------------------
warmstart_from_jgp   – flatten JGP batches into a sequence (ordering jobs
                       within each batch by decreasing |T_j| to promote
                       tool reuse), then evaluate via KTNS.
greedy_ffd           – First-Fit Decreasing: sort jobs by |T_j| descending,
                       evaluate via KTNS.  Simple but often effective.
adjacent_swap_ls     – Adjacent-swap local search starting from any seed
                       sequence: at each iteration try swapping every pair of
                       neighbours (i, i+1); keep the swap iff it strictly
                       decreases KTNS cost.  Repeat until no improvement.
                       NOTE: this is NOT classical 2-opt (which reverses a
                       sub-segment).  It is a 1-exchange neighbourhood search
                       on adjacent pairs, also called "bubble-sort LS".

Helper
------
ktns_magazine_states – run KTNS and return per-step magazine membership
                       as a boolean (n_tools × n_steps) matrix, along with
                       switch costs per step.  Used by viz.py.
"""

import numpy as np
from utils import compute_ktns


# ─────────────────────────────────────────────────────────────────────────────
# KTNS helper that returns structured magazine states
# ─────────────────────────────────────────────────────────────────────────────

def ktns_magazine_states(sequence, tool_req, cap):
    """
    Run the KTNS policy and return structured data for visualisation.

    Parameters
    ----------
    sequence : list[int]   – job indices (0-based)
    tool_req : dict        – {job: [tools]}  (tools 0-based)
    cap      : int         – magazine capacity

    Returns
    -------
    total_cost  : int
    in_magazine : ndarray bool (n_tools × n_steps)
                  in_magazine[t, k] = True iff tool t is in magazine at step k
    switches    : list[int]  – number of tools loaded at each step (Δk)
    required    : ndarray bool (n_tools × n_steps)
                  required[t, k] = True iff tool t is *required* by job sequence[k]
    """
    n_tools = max(t for tools in tool_req.values() for t in tools) + 1
    n_steps = len(sequence)

    magazine    = set()
    in_mag      = np.zeros((n_tools, n_steps), dtype=bool)
    req_mat     = np.zeros((n_tools, n_steps), dtype=bool)
    switches    = []
    total_cost  = 0

    for pos, job in enumerate(sequence):
        needed = set(tool_req[job])

        # Mark required tools
        for t in needed:
            req_mat[t, pos] = True

        # Tools to load
        to_add = needed - magazine

        # Evict tools using KTNS (furthest-future-use)
        while len(magazine) + len(to_add) > cap:
            candidates = magazine - needed

            def next_use(t, cur=pos, seq=sequence, tr=tool_req):
                for k in range(cur + 1, len(seq)):
                    if t in tr[seq[k]]:
                        return k
                return len(seq)   # never needed → evict first

            evict = max(candidates, key=next_use)
            magazine.discard(evict)

        magazine.update(to_add)

        for t in magazine:
            in_mag[t, pos] = True

        switches.append(len(to_add))
        total_cost += len(to_add)

    return total_cost, in_mag, switches, req_mat


# ─────────────────────────────────────────────────────────────────────────────
# Upper-bound heuristics
# ─────────────────────────────────────────────────────────────────────────────

def warmstart_from_jgp(jgp_batches, tool_req, cap):
    """
    Flatten JGP batches into a job sequence and evaluate with KTNS.

    Within each JGP batch the jobs are ordered by decreasing |T_j|
    (most tool-demanding first) to maximise tool carry-over within the batch.

    Parameters
    ----------
    jgp_batches : list of (jobs, tools)  – output of solve_jgp_arf
    tool_req    : dict {job: [tools]}
    cap         : int

    Returns
    -------
    cost     : int    – KTNS switch cost (upper bound on OPT)
    sequence : list   – job sequence used
    """
    if not jgp_batches:
        return float('inf'), []

    sequence = []
    for (jobs, _tools) in jgp_batches:
        sequence.extend(
            sorted(jobs, key=lambda j: len(tool_req[j]), reverse=True)
        )
    cost, _ = compute_ktns(sequence, tool_req, cap)
    return cost, sequence


def greedy_ffd(n_jobs, tool_req, cap):
    """
    First-Fit Decreasing (FFD) heuristic: sort jobs by |T_j| descending.

    Rationale: placing the most tool-demanding jobs first tends to reduce
    switches because the large tool sets are serviced while the magazine
    is most flexible, and smaller tool sets later benefit from carry-over.

    Returns
    -------
    cost     : int
    sequence : list
    """
    order = sorted(range(n_jobs), key=lambda j: len(tool_req[j]), reverse=True)
    cost, _ = compute_ktns(order, tool_req, cap)
    return cost, order


def nearest_neighbor(n_jobs, tool_req, cap, start=0):
    """
    Nearest-neighbour greedy heuristic based on pairwise switch cost.

    Greedily appends the unscheduled job with the smallest KTNS incremental
    cost (i.e., fewest new tools loaded from the current magazine state).

    Returns
    -------
    cost     : int
    sequence : list
    """
    unvisited = set(range(n_jobs))
    sequence  = [start]
    unvisited.discard(start)
    magazine  = set(tool_req[start])
    # AUDIT-FIX(2026-06-10): removed an INFINITE LOOP here.
    # The old code was:
    #     needed_first = set(tool_req[start])
    #     while len(magazine) < cap and needed_first:
    #         magazine = needed_first.copy()
    # The loop body never changes len(magazine) or needed_first, so it spins
    # forever whenever |T_start| < cap.  The magazine is already initialised
    # to the first job's tools above; no padding is needed (the greedy delta
    # below only ever subtracts the magazine).

    while unvisited:
        best_j, best_delta = None, float('inf')
        for j in unvisited:
            delta = len(set(tool_req[j]) - magazine)
            if delta < best_delta:
                best_delta, best_j = delta, j
        sequence.append(best_j)
        unvisited.discard(best_j)
        # Update magazine (simplified – full KTNS only at evaluation)
        magazine = (magazine | set(tool_req[best_j]))
        if len(magazine) > cap:
            needed_now = set(tool_req[best_j])
            excess = magazine - needed_now
            # Evict arbitrarily (proper KTNS happens during evaluation)
            while len(magazine) > cap:
                magazine.discard(next(iter(excess)))
                excess = magazine - needed_now

    cost, _ = compute_ktns(sequence, tool_req, cap)
    return cost, sequence


def adjacent_swap_ls(sequence, tool_req, cap, max_iter=500):
    """
    Adjacent-swap local search (1-exchange on neighbouring pairs).

    At each iteration, scan all adjacent pairs (i, i+1).  If swapping
    them decreases the KTNS cost, accept and continue.  Stop when no
    improving swap is found or max_iter is exceeded.

    Note: this is *not* classical 2-opt (which reverses a sub-segment).
    It is equivalent to bubble-sort with a cost function, and converges
    in O(n²) iterations in the worst case.

    Parameters
    ----------
    sequence : list   – initial job sequence (not modified in place)
    tool_req : dict
    cap      : int
    max_iter : int    – iteration limit

    Returns
    -------
    improved_seq  : list
    cost          : int
    n_improvements : int  – number of accepting swaps made
    """
    seq          = list(sequence)
    current_cost, _ = compute_ktns(seq, tool_req, cap)
    n_improvements   = 0

    for _ in range(max_iter):
        improved = False
        for k in range(len(seq) - 1):
            seq[k], seq[k + 1] = seq[k + 1], seq[k]
            new_cost, _ = compute_ktns(seq, tool_req, cap)
            if new_cost < current_cost:
                current_cost = new_cost
                improved     = True
                n_improvements += 1
            else:
                seq[k], seq[k + 1] = seq[k + 1], seq[k]   # revert
        if not improved:
            break

    return seq, current_cost, n_improvements
