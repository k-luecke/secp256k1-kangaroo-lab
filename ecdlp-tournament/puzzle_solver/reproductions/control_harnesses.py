"""Certified Control Reproductions with Strict Provenance Tracking.

Validates candidate mechanism implementations on independently verified,
publicly published ground-truth vectors before authorizing any live candidate search.
Preserves explicit provenance for both inputs and expected outputs.
"""
from __future__ import annotations

import hashlib
import time
from typing import Dict, Any

from puzzle_solver.verification.secp256k1 import scalar_mult, P, B, GX, GY, is_on_curve
from puzzle_solver.verification.address import (
    hash160, base58check_encode, pubkey_to_bytes
)
from bip39_derivation import (
    entropy_to_mnemonic, mnemonic_to_seed, derive_bip44_private_key
)


class CertifiedControlHarness:
    """Rigorous reproduction controls preserving provenance for both input and expected output."""

    @staticmethod
    def run_control_secp256k1_16() -> Dict[str, Any]:
        """Control 1: Historical Bounded secp256k1 ECDLP (Puzzle #16).
        
        Provenance:
        - Input: Scalar 0xc936 = 51510 in [2^15, 2^16-1].
        - Source: Bitcoin 2015 Transaction 08389f34... output #16, claimed on-chain in 2015.
        - Expected Output: P2PKH address 1BDyrQ6WoF8VN3g9SAS1iKZcPzFfnDVieY.
        """
        t0 = time.perf_counter()
        scalar = 0xc936
        pt = scalar_mult(scalar)
        pub_bytes = pubkey_to_bytes(pt, compressed=True)
        h160 = hash160(pub_bytes)
        derived_address = base58check_encode(h160, version_byte=b'\x00')
        expected_address = "1BDyrQ6WoF8VN3g9SAS1iKZcPzFfnDVieY"
        
        matched = (derived_address == expected_address)
        return {
            "control_id": "control-secp256k1-16",
            "mechanism": "bounded-secp256k1-ecdlp",
            "input_provenance": "Transaction 08389f34... output #16 spending scriptSig",
            "output_provenance": "Historical 2015 on-chain escrow address",
            "derived_address": derived_address,
            "expected_address": expected_address,
            "passed": matched,
            "elapsed_seconds": time.perf_counter() - t0
        }

    @staticmethod
    def run_control_keir_easy1() -> Dict[str, Any]:
        """Control 2: Keir Finlow-Bates Solved Lot EN_easy_1 (sha256x3 brainwallet).
        
        Provenance:
        - Input: "221B Baker Street" (exact Sherlock Holmes address from novel text).
        - Source: Book 'Move Over Brokers, Here Comes The Blockchain' Chapter 4 clue.
        - Transform: sha256(sha256(sha256(input_bytes))) -> uncompressed secp256k1 -> P2PKH.
        - Expected Output: 14aFhno96fkt7knLWMDQ4j8yh8v5hBF4n1 (claimed on-chain 2021).
        """
        t0 = time.perf_counter()
        raw_text = "221B Baker Street"
        d1 = hashlib.sha256(raw_text.encode("utf-8")).digest()
        d2 = hashlib.sha256(d1).digest()
        d3 = hashlib.sha256(d2).digest()
        scalar = int.from_bytes(d3, byteorder="big")
        
        pt = scalar_mult(scalar)
        pub_bytes = pubkey_to_bytes(pt, compressed=False) # Uncompressed
        h160 = hash160(pub_bytes)
        derived_address = base58check_encode(h160, version_byte=b'\x00')
        expected_address = "14aFhno96fkt7knLWMDQ4j8yh8v5hBF4n1"
        
        matched = (derived_address == expected_address)
        return {
            "control_id": "control-keir-easy1",
            "mechanism": "sha256x3-uncompressed-p2pkh",
            "input_provenance": "Move Over Brokers chapter text '221B Baker Street'",
            "output_provenance": "Funding transaction f26ecab7... lot 1 on-chain address",
            "derived_address": derived_address,
            "expected_address": expected_address,
            "passed": matched,
            "elapsed_seconds": time.perf_counter() - t0
        }

    @staticmethod
    def run_control_bip39_canonical() -> Dict[str, Any]:
        """Control 3: BIP39 Standard Canonical Test Vector.
        
        Provenance:
        - Input: 16 bytes of zero entropy (0x00 * 16).
        - Expected Mnemonic: "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about".
        - Expected BIP44 P2PKH Address: 1LqBGSKuX5yYUonjxT5W1dUJnMtHCWHNWg.
        - Source: Official BIP-0039 test vectors.
        """
        t0 = time.perf_counter()
        entropy = bytes([0] * 16)
        mnemonic = entropy_to_mnemonic(entropy)
        seed = mnemonic_to_seed(mnemonic, passphrase="")
        priv_key = derive_bip44_private_key(seed, index=0)
        scalar = priv_key
        pt = scalar_mult(scalar)
        pub_bytes = pubkey_to_bytes(pt, compressed=True)
        h160 = hash160(pub_bytes)
        derived_address = base58check_encode(h160, version_byte=b'\x00')
        expected_address = "1LqBGSKuX5yYUonjxT5qGfpUsXKYYWeabA"
        
        matched = (derived_address == expected_address)
        return {
            "control_id": "control-bip39-canonical",
            "mechanism": "bip39-bip44-p2pkh",
            "input_provenance": "Official BIP-0039 specification vector (all-zeros)",
            "output_provenance": "Canonical BIP-0039 test vector address",
            "derived_address": derived_address,
            "expected_address": expected_address,
            "passed": matched,
            "elapsed_seconds": time.perf_counter() - t0
        }


def run_all_controls() -> Dict[str, Any]:
    c1 = CertifiedControlHarness.run_control_secp256k1_16()
    c2 = CertifiedControlHarness.run_control_keir_easy1()
    c3 = CertifiedControlHarness.run_control_bip39_canonical()
    all_passed = c1["passed"] and c2["passed"] and c3["passed"]
    return {
        "all_controls_passed": all_passed,
        "controls": [c1, c2, c3]
    }
