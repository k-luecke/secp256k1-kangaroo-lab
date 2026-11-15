"""
Unit tests for Dual-End Projective Differential BSGS Solver.
Verifies:
1. DualDiffBabyTable zero-inversion construction and match with scalar_mult.
2. Boundary and interior key recoveries.
3. Asymmetric step allocation correctness.
"""
import unittest
from puzzle_solver.verification.secp256k1 import P, scalar_mult, GX
from puzzle_solver.representations.dual_diff_bsgs import DualDiffBSGSSolver, DualDiffBabyTable

class TestDualDiffBSGS(unittest.TestCase):
    def test_dual_diff_baby_table(self):
        m_b = 30
        tbl = DualDiffBabyTable.build(m_b)
        self.assertEqual(len(tbl.table), m_b)
        self.assertEqual(tbl.table[GX], 1)
        for j in [1, 2, 5, 10, 20, 30]:
            P_j = scalar_mult(j)
            self.assertIn(P_j[0], tbl.table)
            self.assertEqual(tbl.table[P_j[0]], j)

    def test_dual_diff_solver_small_range(self):
        solver = DualDiffBSGSSolver(batch_size=8)
        L = 5000
        R = 6000
        for k in [5000, 5001, 5002, 5450, 5899, 6000]:
            P_tgt = scalar_mult(k)
            res = solver.solve(L, R, P_tgt)
            self.assertTrue(res.success, f"Failed on k={k}")
            self.assertEqual(res.recovered_key, k)

    def test_dual_diff_solver_medium_range(self):
        solver = DualDiffBSGSSolver(batch_size=32)
        L = 100000
        R = 165536
        for k in [100000, 100001, 132768, 165535, 165536]:
            P_tgt = scalar_mult(k)
            res = solver.solve(L, R, P_tgt)
            self.assertTrue(res.success, f"Failed on k={k}")
            self.assertEqual(res.recovered_key, k)

if __name__ == "__main__":
    unittest.main()
