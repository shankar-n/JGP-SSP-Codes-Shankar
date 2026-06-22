#!/usr/bin/env python3
"""
PCF' branch-and-price (PySCIPOpt) -- SKELETON / P1 starting point.

Status: scaffold only. The VERIFIED pricing reduced cost is implemented below
(beta/rho); the RMP build and the PySCIPOpt Pricer plugin are TODO (P1).
Reuses common code from src/SSP/. See src/BNP/README_RESUME.md for the plan.

P1 goal: build the PCF' restricted master, implement the pricer using
`pcf_prime_pricing()` and assert the CG root LP equals the compact LP (= |U|-b
on the 6-ring). That equality is the in-code re-confirmation of the signs below.
"""
import os
import sys
from itertools import combinations

# --- reuse common SSP code (no duplication) ---
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "SSP"))
# from utils import load_ssp_instance, compute_ktns
#   load_ssp_instance(path) -> (J, T, C, A, T_j)   [C is the magazine capacity b]
#   compute_ktns(sequence, ...) -> switch cost (use to validate integral leaves)


# =====================================================================
# VERIFIED PCF' pricing reduced cost  (eq:rc-pcf / eq:rho in 10b...tex)
# Checked against CBC ground truth in _verification/verify_pricing.py.
# Positions are 0-indexed: p = 0..n-1.  DO NOT change signs without re-running
# that check (an earlier draft had rho's three per-tool signs flipped).
# duals: alpha=[P'], gamma=[G], pi=coverage, mu=(W) (defined for p>=1), lam=(T) (t in U)
# =====================================================================
def beta(p, n, alpha, gamma):
    v = -alpha[p]
    if p >= 1:      v -= gamma[p - 1]
    if p <= n - 2:  v += gamma[p]
    return v


def rho(t, p, n, mu, lam, U):
    v = 0.0
    if p >= 1:      v -= mu[(t, p)]
    if p <= n - 2:  v += mu[(t, p + 1)]
    if p == 0 and t in U:
        v += lam.get(t, 0.0)
    return v


def pcf_prime_pricing(p, n, T, Tj, U, alpha, gamma, pi, mu, lam, b):
    """Best column at position p: pick a b-subset C maximizing
       sum_{t in C} rho[t,p] + sum_{j: Tj[j]<=C} pi[j].
    Returns (best_C, reduced_cost). Column prices in iff reduced_cost < -eps.
    Enumeration over C(|T|, b) -- fine for small b (P1 instances); swap for the
    coverage-bonus MILP at larger sizes (see 10b...tex Sec. 'Pricing for PCF'').
    """
    rw = {t: rho(t, p, n, mu, lam, U) for t in range(T)}
    best_C, best_val = None, -float("inf")
    for C in combinations(range(T), b):
        Cs = frozenset(C)
        val = sum(rw[t] for t in C) + sum(pi[j] for j in range(len(Tj)) if Tj[j] <= Cs)
        if val > best_val:
            best_val, best_C = val, Cs
    return best_C, beta(p, n, alpha, gamma) - best_val


# =====================================================================
# TODO P1 -- PySCIPOpt restricted master + Pricer
# =====================================================================
# 1. Build RMP rows: [P'] sum_C y_{C,p} <= 1 ; [G] sum_C y_{C,p+1} <= sum_C y_{C,p};
#    (C) coverage>=1 ; (W) w_{t,p} >= a_{t,p}-a_{t,p-1} ; (T) sum_p w_{t,p} >= 1-a_{t,0}.
#    Keep w_{t,p} structural; generate y_{C,p} columns. Seed from a feasible schedule
#    (SSP/heuristics warmstart -> sequence -> per-position configs) for valid duals.
# 2. class PCFPricer(pyscipopt.Pricer):
#        def pricerredcost(self):
#            read duals alpha,gamma,pi,mu,lam from the rows;
#            for p in range(n): C, rc = pcf_prime_pricing(p, ...);
#            if rc < -1e-6: add column y_{C,p} (cost 0; coeffs into the rows above);
#        def pricerfarkas(self): ... (or guarantee initial feasibility)
# 3. Assert: CG root LP == compact LP from verify_pcf_prime.py (== |U|-b on 6-ring).
# TODO P2: branch on a_{t,p} = sum_{C ni t} y_{C,p} (robust; only shifts rho[t,p]).

if __name__ == "__main__":
    print("PCF' B&P skeleton. Verified pricing formula is ready (beta/rho/pcf_prime_pricing).")
    print("Next: implement the PySCIPOpt RMP + Pricer (P1). See src/BNP/README_RESUME.md.")
