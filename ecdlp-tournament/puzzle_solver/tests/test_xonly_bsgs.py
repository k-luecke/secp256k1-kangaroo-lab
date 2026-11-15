"""
Unit tests for XOnlyBSGSSolver (Negation-Quotient x-only BSGS).
Tests boundary conditions, small ranges, positive and negative offsets, and equivalence with standard BSGS.
"""
import unittest
from puzzle_solver.verification.secp256k1 import scalar_mult
from puzzle_solver.representations.bsgs import BSGSSolver
from puzzle_solver.representations.xonly_bsgs import XOnlyBSGSSolver, XOnlyBabyStepTable

class TestXOnlyBSGS(unittest.TestCase):
    def setUp(self):
        self.solver = XOnlyBSGSSolver()
        self.ref_solver = BSGSSolver()

    def test_boundaries(self):
        L, R = 100, 300
        for k_target in [L, R, (L + R) // 2]:
            P_target = scalar_mult(k_target)
            res = self.solver.solve(L, R, P_target)
            self.assertTrue(res.success)
            self.assertEqual(res.recovered_key, k_target)

    def test_small_ranges(self):
        for N in [1, 2, 3, 5, 8, 16]:
            L = 200
            R = L + N - 1
            for k_target in range(L, R + 1):
                P_target = scalar_mult(k_target)
                res = self.solver.solve(L, R, P_target)
                self.assertTrue(res.success, f"Failed on N={N}, k={k_target}")
                self.assertEqual(res.recovered_key, k_target)

    def test_table_reduction(self):
        # Verify table size is approximately half of standard BSGS
        N = 10000 # sqrt(N) = 100
        L = 1000
        R = L + N - 1
        k_target = L + 5432
        P_target = scalar_mult(k_target)
        
        res_std = self.ref_solver.solve(L, R, P_target)
        res_xonly = self.solver.solve(L, R, P_target)
        
        self.assertEqual(res_xonly.recovered_key, k_target)
        self.assertLessEqual(res_xonly.baby_entries, (res_std.baby_entries // 2) + 2)
        print(f"Table reduction for N={N}: standard={res_std.baby_entries} entries, xonly={res_xonly.baby_entries} entries")

    def test_reusable_table(self):
        table = XOnlyBabyStepTable.build(m_b=30)
        L, R = 5000, 8000 # N = 3001, m_b ~ 28 <= 30
        for offset in [0, 500, 1000, 1500, 2000, 2500, 3000]:
            k_target = L + offset
            P_target = scalar_mult(k_target)
            res = self.solver.solve(L, R, P_target, baby_table=table)
            self.assertTrue(res.success)
            self.assertEqual(res.recovered_key, k_target)

if __name__ == "__main__":
    unittest.main()
