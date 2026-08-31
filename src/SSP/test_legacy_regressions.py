"""Focused regressions for repaired legacy SSP helpers and formulations."""

from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "SSP"))

from SCIP_formulation_solvers import (  # noqa: E402
    _is_hamiltonian_cycle,
    _route_from_depot_cycle,
    solve_ssp_catanzaro,
    solve_ssp_laporte,
)
from solution_validators import validate_jgp  # noqa: E402
from utils import compute_switch_cost, run_brute_force_TSP_on_configs  # noqa: E402


class LegacySSPRegressionTests(unittest.TestCase):
    def test_jgp_validator_rejects_duplicate_job_in_one_batch(self):
        with self.assertRaisesRegex(ValueError, "appears more than once"):
            validate_jgp(
                [([0, 0, 1], [0, 1])],
                n_jobs=2,
                cap=2,
                tool_req={0: [0], 1: [1]},
            )

    def test_jgp_validator_rejects_duplicate_job_across_batches(self):
        with self.assertRaisesRegex(ValueError, "appears more than once"):
            validate_jgp(
                [([0], [0]), ([0, 1], [0, 1])],
                n_jobs=2,
                cap=2,
                tool_req={0: [0], 1: [1]},
            )

    def test_dummy_configuration_has_zero_switch_cost(self):
        self.assertEqual(compute_switch_cost("DUMMY", (0, 1), 2), 0)
        self.assertEqual(compute_switch_cost((0, 1), "DUMMY", 2), 0)
        self.assertEqual(compute_switch_cost((0, 1), (1, 2), 2), 1)

    def test_brute_force_helper_explores_nonidentity_orders(self):
        configs = [(0, 1), (2, 3), (0, 2)]
        cost, routes = run_brute_force_TSP_on_configs(configs)
        self.assertEqual(cost, 2)
        self.assertIn((0, 2, 1), routes)
        self.assertNotIn((0, 1, 2), routes)

    def test_cycle_detection_and_reconstruction(self):
        self.assertTrue(_is_hamiltonian_cycle([[0, 2, 1]], 3))
        self.assertFalse(_is_hamiltonian_cycle([[0, 1], [2]], 3))
        self.assertEqual(
            _route_from_depot_cycle(
                [(0, 2), (2, 3), (3, 1), (1, 0)], num_jobs=3
            ),
            [1, 2, 0],
        )

    def test_laporte_and_catanzaro_accept_nonempty_requirements(self):
        tool_req = {0: [0], 1: [1], 2: [2]}
        for solver in (solve_ssp_laporte, solve_ssp_catanzaro):
            with self.subTest(solver=solver.__name__):
                objective, route = solver(3, 3, 2, None, tool_req)
                self.assertIsNotNone(objective)
                self.assertEqual(sorted(route), [0, 1, 2])


if __name__ == "__main__":
    unittest.main(verbosity=2)
