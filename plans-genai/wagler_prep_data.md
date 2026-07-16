# Data for the polyhedral session (Prof. Wagler) — 2026-07-16

1. Ring covering LP (proved + verified): k-ring, b=3 → tau* = k/2, K* = ceil(k/2).
   Dual pair: weight 1/2 per adjacent-pair group / packing y_j = 1/2. Gap 1/2 iff k odd.
2. Non-integrality is NOT confined to rings. Scan (CBC, exact LPs):
   edge family b=3 (m<=5, exhaustive): 152/627 non-integral (24.2%)
   mixed sizes b=3 (m=6 random):        5/300  (1.7%)
   mixed sizes b=4 (m=7 random):       15/250  (6.0%)
   Off-ring witness: T = ({0,1,3},{2,3},{2,4},{2,5},{3,4,5}), b=3: tau*=3.5, K*=4.
3. Open (Q1): does every non-integral instance contain an odd-ring-like minor, or is
   the obstruction landscape genuinely larger (the witness above is the test case)?
4. Related proved items in the report: circuit-blocker identity; K* = chromatic number
   of the circuit hypergraph; the clutter does NOT determine the SSP gap (I0/I1).
Script: _verification/verify_extremal_hunt.py (scan section); regenerate with seed 3.
