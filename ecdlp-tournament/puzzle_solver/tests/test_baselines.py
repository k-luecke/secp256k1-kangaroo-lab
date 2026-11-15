"""
Unit tests for puzzle solver baseline scanner and registry.
"""
import unittest
from puzzle_solver.targets.puzzle_registry import get_puzzle_spec, get_quarantined_truth
from puzzle_solver.baselines.sequential_scan import SequentialScanner
from puzzle_solver.verification.address import privkey_to_address

class TestBaselineSequentialScanner(unittest.TestCase):
    def test_solve_puzzles_1_to_5(self):
        for i in range(1, 6):
            pid = f"btc_2015_{i:03d}"
            spec = get_puzzle_spec(pid)
            scanner = SequentialScanner(spec)
            result = scanner.run()
            
            # 1. Search must succeed
            self.assertTrue(result.success, f"Failed on {pid}")
            
            # 2. Recovered address must strictly match target address
            self.assertEqual(result.recovered_address, spec.target.target_value)
            
            # 3. Post-hoc verification against quarantined truth
            truth = get_quarantined_truth(pid)
            self.assertEqual(result.recovered_key_int, truth)
            
            # 4. Independent crypto verification
            independent_addr = privkey_to_address(result.recovered_key_int, compressed=True)
            self.assertEqual(independent_addr, spec.target.target_value)

class TestPollardLambdaScanner(unittest.TestCase):
    def test_kangaroo_basic(self):
        from puzzle_solver.baselines.pollard_lambda import PollardLambdaScanner
        from puzzle_solver.verification.secp256k1 import scalar_mult
        
        scanner = PollardLambdaScanner()
        # Test on several intervals
        cases = [
            (100, 200, 142),
            (1000, 2000, 1876),
            (50000, 60000, 54321),
            (100000, 110000, 100001), # near boundary
            (100000, 110000, 109999), # near boundary
        ]
        for L, R, k in cases:
            P_tgt = scalar_mult(k)
            res = scanner.solve(L, R, P_tgt)
            self.assertTrue(res.success, f"Failed on L={L}, R={R}, k={k}")
            self.assertEqual(res.recovered_key, k)
            self.assertTrue(res.distinguished_points_stored > 0)
            self.assertTrue(res.distinguished_points_stored < 200)

if __name__ == "__main__":
    unittest.main()

