"""
Unit tests for Projective Differential X-Only BSGS Solver.
Verifies:
1. Montgomery batch inversion correctness.
2. Exact scalar recovery across boundaries and interior points.
3. Multiple interval sizes and batch sizes.
"""
import unittest
from puzzle_solver.verification.secp256k1 import P, scalar_mult
from puzzle_solver.representations.diff_xonly_bsgs import DiffXOnlyBSGSSolver, montgomery_batch_invert

class TestDiffXOnlyBSGS(unittest.TestCase):
    def test_montgomery_batch_invert(self):
        cases = [13, 999999, P - 5, 2]
        invs = montgomery_batch_invert(cases)
        for c, inv in zip(cases, invs):
            self.assertEqual((c * inv) % P, 1)

    def test_diff_xonly_solver_small_range(self):
        solver = DiffXOnlyBSGSSolver(batch_size=8)
        L = 1000
        R = 2000
        for k in [1000, 1001, 1002, 1450, 1899, 2000]:
            P_tgt = scalar_mult(k)
            res = solver.solve(L, R, P_tgt)
            self.assertTrue(res.success, f"Failed on k={k}")
            self.assertEqual(res.recovered_key, k)

    def test_diff_xonly_various_batch_sizes(self):
        L = 50000
        R = 60000
        k = 54321
        P_tgt = scalar_mult(k)
        for bs in [4, 16, 32, 64]:
            solver = DiffXOnlyBSGSSolver(batch_size=bs)
            res = solver.solve(L, R, P_tgt)
            self.assertTrue(res.success)
            self.assertEqual(res.recovered_key, k)

if __name__ == "__main__":
    unittest.main()
