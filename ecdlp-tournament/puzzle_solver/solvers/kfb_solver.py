"""Keir Finlow-Bates: Move Over Brokers Treasure Hunt Autonomous Solver.

Target: keir-finlow-bates-blockchain-book-600ksats (3 open lots, 600,000 sats total).
Escrows:
  EN_medium:   17Y9czcbcCz433QXsy1SGQjwLb27BBtLLZ (200,000 sats)
  EN_veryhard: 1DZ5NbUwDgxeJkKhQLgYcUUX36PtYso1pm (200,000 sats)
  IT_veryhard: 19kkawFcg2U2s6vq368MXD7FJU9JZvRrjA (200,000 sats)

Mechanism: sha256x3 -> uncompressed secp256k1 -> P2PKH address.
Certified against:
  EN_easy_1: '221B Baker Street' -> 14aFhno96fkt7knLWMDQ4j8yh8v5hBF4n1
  EN_easy_2: '9781688289970'     -> 14utGQn5GdfPvUrHNLAwTmmP99QpXm9mg6
  IT_hard:   'Genova Firenze Bologna Brindisi' -> 1QExGvuieS9MvuKC3R1qjp6jGTVcqisTDj
"""
from __future__ import annotations

import hashlib
import itertools
import time
from typing import Dict, Any, List, Optional, Tuple

from puzzle_solver.verification.secp256k1 import scalar_mult
from puzzle_solver.verification.address import pubkey_to_bytes, hash160, base58check_encode
from lab_c_discovery import AttemptOutcome, AttemptResult

LOT_ESCROWS = {
    "EN_medium": "17Y9czcbcCz433QXsy1SGQjwLb27BBtLLZ",
    "EN_veryhard": "1DZ5NbUwDgxeJkKhQLgYcUUX36PtYso1pm",
    "IT_veryhard": "19kkawFcg2U2s6vq368MXD7FJU9JZvRrjA",
}


def derive_kfb_address(raw_string: str) -> str:
    """Computes sha256x3 -> uncompressed secp256k1 -> P2PKH address."""
    d1 = hashlib.sha256(raw_string.encode("utf-8")).digest()
    d2 = hashlib.sha256(d1).digest()
    d3 = hashlib.sha256(d2).digest()
    scalar = int.from_bytes(d3, "big")
    pt = scalar_mult(scalar)
    pub = pubkey_to_bytes(pt, compressed=False)
    return base58check_encode(hash160(pub), version_byte=b"\x00")


def run_kfb_hypothesis_1() -> AttemptResult:
    """Hypothesis KFB-H1: EN_medium (4-City Travel Routing Hypothesis).
    
    IT_hard was solved with 4 Italian cities ('Genova Firenze Bologna Brindisi').
    In the English edition, testing prominent UK conference and blockchain cities.
    """
    t0 = time.perf_counter()
    hypothesis_id = "KFB-H1"
    target_id = "keir-finlow-bates-blockchain-book-600ksats"
    target_addr = LOT_ESCROWS["EN_medium"]
    why = (
        "Solved sibling lot IT_hard used four space-separated Italian cities ('Genova Firenze Bologna Brindisi'). "
        "English edition clues in chapter 7 discuss travel routes across UK blockchain conference centers."
    )

    uk_cities = [
        "London", "Oxford", "Cambridge", "Manchester", "Edinburgh",
        "Bristol", "Birmingham", "Leeds", "Glasgow", "Newcastle",
        "Southampton", "Bath", "York", "Cardiff", "Belfast"
    ]

    candidates = []
    # Permutations of 4 cities
    for combo in itertools.permutations(uk_cities[:8], 4):
        candidates.append(" ".join(combo))

    total = len(candidates)
    winning_answer = None

    for cand in candidates:
        addr = derive_kfb_address(cand)
        if addr == target_addr:
            winning_answer = cand
            break

    elapsed = time.perf_counter() - t0
    outcome = AttemptOutcome.VERIFIED_WIN_PENDING_CLAIM if winning_answer else AttemptOutcome.HYPOTHESIS_FALSIFIED

    return AttemptResult(
        hypothesis_id=hypothesis_id,
        target_id=target_id,
        why_this_attack_follows=why,
        exact_candidate_space=total,
        candidates_evaluated=total,
        expected_cost_seconds=0.2,
        actual_cost_seconds=elapsed,
        stopping_condition="On-chain escrow match against 17Y9czcbcCz433QXsy1SGQjwLb27BBtLLZ or exhaustion",
        result=outcome,
        independent_verification_method="sha256x3 uncompressed P2PKH address derivation matching on-chain escrow",
        hierarchical_filter_results={
            "stage1_format_check": total,
            "stage2_onchain_match": bool(winning_answer),
            "winner": winning_answer
        },
        what_a_miss_eliminates="Eliminates all 1,680 4-city permutations across the top 8 UK blockchain conference hubs."
    )


def run_kfb_hypothesis_2() -> AttemptResult:
    """Hypothesis KFB-H2: EN_veryhard (Hardcover/Kindle ISBN and Barcode Formats).
    
    EN_easy_2 was solved with paperback ISBN '9781688289970'.
    Testing Hardcover ISBN (9781688289987), Kindle ASIN, barcode price add-ons, and ISBN-10 forms.
    """
    t0 = time.perf_counter()
    hypothesis_id = "KFB-H2"
    target_id = "keir-finlow-bates-blockchain-book-600ksats"
    target_addr = LOT_ESCROWS["EN_veryhard"]
    why = (
        "Solved sibling lot EN_easy_2 was solved with paperback ISBN ('9781688289970'). "
        "The hardcover, Kindle ASIN, and audio editions carry distinct bibliographic identifiers."
    )

    base_isbns = [
        "9781688289970",  # paperback (solved EN_easy_2)
        "9781688289987",  # hardcover candidate
        "9781688289994",  # sequential candidate
        "9781688289963",
        "9781688289956",
        "1688289972",     # ISBN-10 paperback
        "1688289980",     # ISBN-10 hardcover
        "1688289999",
        "B07X87D38R",     # Kindle ASIN candidate
        "B07WNV7S7F",
    ]

    suffixes = ["", " 90000", " 51999", " 52499", " 00001", "-90000", "\n", ""]
    separators = ["", "-", " "]

    candidates = []
    for base in base_isbns:
        for sfx in suffixes:
            candidates.append(base + sfx)
            # Hyphenated ISBN-13: 978-1-68828-998-7
            if len(base) == 13 and base.startswith("978"):
                hyphenated = f"{base[:3]}-{base[3]}-{base[4:9]}-{base[9:12]}-{base[12]}"
                candidates.append(hyphenated + sfx)

    total = len(candidates)
    winning_answer = None

    for cand in candidates:
        addr = derive_kfb_address(cand)
        if addr == target_addr:
            winning_answer = cand
            break

    elapsed = time.perf_counter() - t0
    outcome = AttemptOutcome.VERIFIED_WIN_PENDING_CLAIM if winning_answer else AttemptOutcome.HYPOTHESIS_FALSIFIED

    return AttemptResult(
        hypothesis_id=hypothesis_id,
        target_id=target_id,
        why_this_attack_follows=why,
        exact_candidate_space=total,
        candidates_evaluated=total,
        expected_cost_seconds=0.1,
        actual_cost_seconds=elapsed,
        stopping_condition="On-chain escrow match against 1DZ5NbUwDgxeJkKhQLgYcUUX36PtYso1pm or exhaustion",
        result=outcome,
        independent_verification_method="sha256x3 uncompressed P2PKH address derivation matching on-chain escrow",
        hierarchical_filter_results={
            "stage1_format_check": total,
            "stage2_onchain_match": bool(winning_answer),
            "winner": winning_answer
        },
        what_a_miss_eliminates="Eliminates 120 hardcover, Kindle ASIN, and barcode add-on variants for EN_veryhard."
    )
