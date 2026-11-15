"""
Unit Tests for Cryptographic Verification Pipeline
Tests secp256k1 curve arithmetic and Bitcoin P2PKH address derivation against known vectors.
"""
import unittest
from puzzle_solver.verification.secp256k1 import (
    GX, GY, P, ORDER, is_on_curve, scalar_mult, jacobian_double, jacobian_add, to_affine
)
from puzzle_solver.verification.address import (
    pubkey_to_bytes, hash160, base58check_encode, base58check_decode,
    pubkey_to_address, privkey_to_address, address_to_hash160
)

class TestVerificationPipeline(unittest.TestCase):
    def test_generator_on_curve(self):
        self.assertTrue(is_on_curve(GX, GY), "Generator G must satisfy curve equation")

    def test_scalar_mult_one(self):
        p1 = scalar_mult(1)
        self.assertEqual(p1, (GX, GY), "1 * G must equal G")

    def test_scalar_mult_two(self):
        p2 = scalar_mult(2)
        p2_add = to_affine(jacobian_add((GX, GY, 1), (GX, GY, 1)))
        self.assertEqual(p2, p2_add, "2 * G must equal G + G")
        self.assertTrue(is_on_curve(p2[0], p2[1]), "2 * G must satisfy curve equation")

    def test_puzzle_1_vector(self):
        """Historical Bitcoin Puzzle #1: k = 1 -> 1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH (compressed)."""
        addr_comp = privkey_to_address(1, compressed=True)
        self.assertEqual(addr_comp, "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH")
        
        # Verify roundtrip decode
        v_byte, h160 = base58check_decode(addr_comp)
        self.assertEqual(v_byte, b'\x00')
        self.assertEqual(len(h160), 20)
        self.assertEqual(base58check_encode(h160), addr_comp)

    def test_address_to_hash160(self):
        addr = "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"
        h160 = address_to_hash160(addr)
        self.assertEqual(len(h160), 20)
        re_encoded = base58check_encode(h160)
        self.assertEqual(re_encoded, addr)

if __name__ == "__main__":
    unittest.main()
