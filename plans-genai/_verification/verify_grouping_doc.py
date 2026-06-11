"""Verification for plans-genai/06_grouping_selection.tex (Claude-Fable, 2026-06-10).

Check A (sliding-window family, cor:sliding): jobs = one per window of width r,
shift r-ov.  Verifies K* = K, Z* = |U| - b, and records H (full GTSP over the
K*-grouping) vs the one-directional MWHP value (K-1)(r-ov).
Finding: H == Z* on all tested members -- the MWHP excess (b-r) is a policy
artifact, not a heuristic gap (see the new remark after cor:sliding).

Check B (Lagrangian section): the OLD claim "L(lambda) <= Z*_SSP by weak
duality" is FALSE -- on the 6-ring L(0.5)=3.5, L(1)=4 > Z*=3.  Correct facts:
L(0) = Z* exactly (grouping exactness) and L(lambda) <= H for all lambda >= 0.
"""
import sys
sys.path.insert(0, "/sessions/peaceful-happy-lovelace/mnt/JGP-SSP-Codes-Shankar/plans-genai/_verification")
from ssp_verify import ssp_opt, jgp_kstar, heuristic_H, ring


def sw(K, r, ov):
    """Sliding-window instance: one job per window."""
    return [frozenset(range(k * (r - ov), k * (r - ov) + r)) for k in range(K)]


def main():
    for (K, r, ov, b) in [(3, 3, 1, 4), (4, 3, 1, 4), (3, 4, 2, 5), (4, 4, 1, 5)]:
        assert 0 <= ov <= r / 2 and r <= b and 2 * r - ov > b, "outside family params"
        js = sw(K, r, ov)
        U = set().union(*js)
        m = len(U)
        Ks, parts = jgp_kstar(js, b)
        Z = ssp_opt(js, b, U)
        H = heuristic_H(js, b, Ks, U, parts)[0]
        mwhp = (K - 1) * (r - ov)
        print(f"K={K},r={r},ov={ov},b={b}: m={m} K*={Ks} Z*={Z} (claim {m-b}) "
              f"H={H} MWHP={mwhp}")
        assert Ks == K and Z == m - b, "cor:sliding violated"
        assert H == Z, "H == Z* finding violated (update the remark if this fires)"
        assert mwhp == Z + (b - r), "MWHP excess formula violated"

    js = ring(6)
    U = set().union(*js)
    zK = {3: 4, 4: 3, 5: 3, 6: 3}   # verified in verify_gap_doc.py
    Z = ssp_opt(js, 3, U)
    assert Z == 3
    for lam in [0, 0.5, 1, 2]:
        L = min(z + lam * (K - 3) for K, z in zK.items())
        print(f"L({lam}) = {L}   (Z*=3, H=4)")
        assert L <= 4 + 1e-9, "L <= H violated"
    assert min(z for z in zK.values()) == Z, "L(0) = Z* (grouping exactness) violated"
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
