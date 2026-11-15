"""
Unit tests for Baby-Step Giant-Step (BSGS) solver.
Tests boundaries, small ranges, table reusability, and equivalence with linear stepping.
"""
import unittest
from puzzle_solver.verification.secp256k1 import scalar_mult
from puzzle_solver.representations.bsgs import BSGSSolver, BabyStepTable, LinearDlogScanner

class TestBSGS(unittest.TestCase):
    def setUp(self):
        self.solver = BSGSSolver()

    def test_boundary_lower(self):
        # Target at exact lower bound
        L, R = 100, 200
        k_target = 100
        P_target = scalar_mult(k_target)
        res = self.solver.solve(L, R, P_target)
        self.assertTrue(res.success)
        self.assertEqual(res.recovered_key, k_target)

    def test_boundary_upper(self):
        # Target at exact upper bound
        L, R = 100, 200
        k_target = 200
        P_target = scalar_mult(k_target)
        res = self.solver.solve(L, R, P_target)
        self.assertTrue(res.success)
        self.assertEqual(res.recovered_key, k_target)

    def test_tiny_ranges(self):
        # Test N=1, 2, 3, 4
        for N in [1, 2, 3, 4]:
            L = 50
            R = L + N - 1
            for k_target in range(L, R + 1):
                P_target = scalar_mult(k_target)
                res = self.solver.solve(L, R, P_target)
                self.assertTrue(res.success, f"Failed on N={N}, k={k_target}")
                self.assertEqual(res.recovered_key, k_target)

    def test_table_reusability(self):
        # Build table for m=50 and reuse across multiple queries
        table = BabyStepTable.build(m=50)
        L, R = 1000, 2000 # N = 1001, sqrt(N) ~ 32 <= 50
        for offset in [0, 250, 500, 750, 1000]:
            k_target = L + offset
            P_target = scalar_mult(k_target)
            res = self.solver.solve(L, R, P_target, baby_table=table)
            self.assertTrue(res.success)
            self.assertEqual(res.recovered_key, k_target)

    def test_equivalence_with_linear(self):
        L, R = 500, 650
        for k_target in [500, 550, 600, 650]:
            P_target = scalar_mult(k_target)
            res_lin = LinearDlogScanner.solve(L, R, P_target)
            res_bsgs = self.solver.solve(L, R, P_target)
            self.assertEqual(res_lin.recovered_key, res_bsgs.recovered_key)
            self.assertEqual(res_lin.recovered_key, k_target)

if __name__ == "__main__":
    unittest.main()
