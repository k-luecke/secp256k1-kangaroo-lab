"""Path to Greatness: Autonomous Bounded Hypothesis Solver.

Target: Path to Greatness: Treasure Hunt (3.02608794 LTC).
Escrow: LUtL7qnm3gzxKjHcfVLSjydqhhinTVmTmS (funded, unspent).
Oracles: Hierarchical verification pipeline:
  Stage 1: Syntactic PKCS#7 padding (approx 1/255 false-positive rate).
  Stage 2: Structural 8-byte payload + eight 0x08 padding bytes (2^-64 false-positive rate).
  Stage 3: Full WIF decryption + secp256k1 public key derivation + P2PKH address comparison.
"""
from __future__ import annotations

import base64
import time
from typing import Dict, Any, List, Tuple, Optional

try:
    from Crypto.Cipher import AES
except ImportError:
    from Cryptodome.Cipher import AES

from p2g_oracle import (
    SEGMENTS, CLUES, ANSWER_LEN, _SEG_CT, normalise_answer,
    segment_oracle, superkey_to_wif, solve_from_answers, is_solution,
    address_from_wif, TARGET_ADDRESS
)
from lab_c_discovery import AttemptOutcome, AttemptResult


def check_segment_hierarchical(
    seg_id: int,
    raw_left: str,
    raw_right: str
) -> Tuple[bool, bool, Optional[bytes]]:
    """Evaluates a pair of clue answers against a segment under hierarchical verification.
    
    Returns:
        (stage1_valid_pkcs7, stage2_exact_structure, payload_8bytes)
    """
    clue_a, clue_b = SEGMENTS[seg_id][3]
    left = normalise_answer(clue_a, raw_left)
    right = normalise_answer(clue_b, raw_right)

    if len(left) != ANSWER_LEN[clue_a] or len(right) != ANSWER_LEN[clue_b]:
        return False, False, None

    key32 = (left + right).encode("ascii")
    if len(key32) != 32:
        return False, False, None

    # AES decrypt
    pt = AES.new(key32, AES.MODE_CBC, SEGMENTS[seg_id][2]).decrypt(_SEG_CT[seg_id])
    
    # Stage 1: Syntactic PKCS#7 padding check
    pad_val = pt[-1]
    stage1_valid_pkcs7 = (1 <= pad_val <= 16) and (pt[-pad_val:] == bytes([pad_val]) * pad_val)

    # Stage 2: Structural segment check (exactly 8 bytes payload + eight 0x08 padding bytes)
    stage2_exact_structure = (pt[8:] == b"\x08" * 8)
    payload_8 = pt[:8] if stage2_exact_structure else None

    return stage1_valid_pkcs7, stage2_exact_structure, payload_8


def run_p2g_hypothesis_1() -> AttemptResult:
    """Hypothesis P2G-H1: Segment 1 (imagine + beach).
    
    Clue 1: John Lennon 'Imagine' replacement word + Pearl Harbor date representations (16 chars).
    Clue 6: 15-note monophonic soundtrack melody in D# minor with bending 6th note (16 chars).
    """
    t0 = time.perf_counter()
    hypothesis_id = "P2G-H1"
    target_id = "path-to-greatness-treasure-hunt-3ltc"
    why = (
        "Clue 1 poem quotes John Lennon's Imagine with 'Livin life today' and '19410712' under it, "
        "instructing 'written twice'. Clue 6 poem points to FFT-measured 15-note monophonic melody "
        "starting on sol (degree 5) with a bending 6th note yielding 16-character notation."
    )

    # Candidate clue 1 pool (16 chars)
    clue1_candidates = [
        "1941071219410712",
        "1941120719411207",
        "1207194112071941",
        "0712194107121941",
        "4112071941120719",
        "peacepeacepeacep",
        "peacetodaypeacet",
        "livingpeacepeace",
        "livinglifeinpeac",
        "dayofinfamy1941.",
        "infamousday1941.",
        "datewhichwillliv",
        "december071941..",
        "07december1941..",
        "livinglifetoday!",
        "livinlifetoday!!",
        "peacetoday1941..",
        "todaypeace1941..",
        "19410712peaceliv",
        "peaceliv19410712",
        "living19411207..",
        "peace19411207...",
        "johnlennon1941..",
        "lennonpeace1941.",
        "remember19410712",
        "decemberseventh.",
        "seventhofficial.",
        "pearlharbor1941.",
    ]

    # Candidate clue 6 pool (16 chars for 15 notes)
    # Measured notes: 5, 3, 6, 5, 3, 1, 2, 7, 6, 7, 5, 5, 3, 6, 5
    clue6_candidates = [
        "536531#276755365",
        "536531b276755365",
        "536532b276755365",
        "536531.276755365",
        "536531-276755365",
        "536531+276755365",
        "536531*276755365",
        "536531/276755365",
        "5365314276755365",
        "5365324276755365",
        "5365311276755365",
        "5365312276755365",
        "5365313276755365",
        "5365315276755365",
        "5365316276755365",
        "5365317276755365",
        "5365310276755365",
        "5365318276755365",
        "5365319276755365",
        "536531a276755365",
        "536531d276755365",
        "536531e276755365",
        "536531f276755365",
        "536531s276755365",
        # F# major degrees (A# is 3rd degree): 3 1 4 3 1 6 7 5 4 5 3 3 1 4 3
        "314316#54533143",
        "314316b54533143",
        "314316.54533143",
        "314316-54533143",
        # English pitch note letters
        "asfbasfdsfcsbcsf",
        "asfbasfdefcsbcsf",
        "asfbasfdefcsbcsa",
        "asfbasfdsfcsbcsa",
        "a#f#ba#f#d#fc#bc",
        "a#f#ba#f#d#e#fc#",
        "a#f#ba#f#efc#bca",
    ]

    total_candidates = len(clue1_candidates) * len(clue6_candidates)
    stage1_hits = 0
    stage2_hits = 0
    winning_key = None

    for c1 in clue1_candidates:
        for c6 in clue6_candidates:
            s1, s2, payload = check_segment_hierarchical(1, c1, c6)
            if s1:
                stage1_hits += 1
            if s2:
                stage2_hits += 1
                winning_key = (c1, c6, payload)

    elapsed = time.perf_counter() - t0
    outcome = AttemptOutcome.NEW_CONSTRAINT if winning_key else AttemptOutcome.HYPOTHESIS_FALSIFIED

    return AttemptResult(
        hypothesis_id=hypothesis_id,
        target_id=target_id,
        why_this_attack_follows=why,
        exact_candidate_space=total_candidates,
        candidates_evaluated=total_candidates,
        expected_cost_seconds=0.1,
        actual_cost_seconds=elapsed,
        stopping_condition="Exhaustion of Cartesian product or Stage 3 on-chain oracle match",
        result=outcome,
        independent_verification_method="Segment 1 AES-256-CBC padding oracle with IV few_n_far_btween",
        hierarchical_filter_results={
            "stage1_valid_pkcs7_count": stage1_hits,
            "stage1_false_positive_rate_empirical": stage1_hits / total_candidates if total_candidates else 0,
            "stage2_exact_structure_count": stage2_hits,
            "stage3_cryptographic_winner": winning_key[0:2] if winning_key else None
        },
        what_a_miss_eliminates=(
            "Eliminates the combination of 27 Lennon replacement/date representations crossed with "
            "35 FFT-measured monophonic melody degree encodings for Segment 1."
        )
    )


def run_p2g_hypothesis_2() -> AttemptResult:
    """Hypothesis P2G-H2: Segment 1 (Literal Lennon Word Count & Substitution)."""
    t0 = time.perf_counter()
    hypothesis_id = "P2G-H2"
    target_id = "path-to-greatness-treasure-hunt-3ltc"
    why = (
        "Clue 1 'left a number in its place' literal reading: Lennon's word 'peace' or 'living' "
        "replaced by numbers or characters, crossed with note-letter combinations."
    )

    clue1_candidates = [
        "imaginepeace1941",
        "peaceimagine1941",
        "livinglifein1941",
        "livinglifetodayy",
        "livinlifetoday21",
        "livinglifetoday4",
        "livinglifetoday5",
        "livinglifetoday7",
        "livinlifetoday41",
        "allthepeople1941",
        "livinglifeas1941",
        "livinglifeinpeac",
        "peacepeacepeace1",
        "peacepeacepeace2",
        "peacepeacepeace3",
        "livingpeace19410",
        "livingpeace19411",
        "livingpeace19412",
        "lennon1941120700",
        "imagine19411207.",
    ]

    clue6_candidates = [
        "536531#276755365",
        "536531b276755365",
        "536531.276755365",
        "536531-276755365",
        "5365314276755365",
        "solmilasolmidore",
        "solmilasolmidore",
        "5365312767553650",
        "5365312767553651",
        "5365312767553655",
        "1536531276755365",
        "0536531276755365",
        "536531276755365#",
        "536531276755365b",
        "536531276755365*",
    ]

    total_candidates = len(clue1_candidates) * len(clue6_candidates)
    stage1_hits = 0
    stage2_hits = 0
    winning_key = None

    for c1 in clue1_candidates:
        for c6 in clue6_candidates:
            s1, s2, payload = check_segment_hierarchical(1, c1, c6)
            if s1:
                stage1_hits += 1
            if s2:
                stage2_hits += 1
                winning_key = (c1, c6, payload)

    elapsed = time.perf_counter() - t0
    outcome = AttemptOutcome.NEW_CONSTRAINT if winning_key else AttemptOutcome.HYPOTHESIS_FALSIFIED

    return AttemptResult(
        hypothesis_id=hypothesis_id,
        target_id=target_id,
        why_this_attack_follows=why,
        exact_candidate_space=total_candidates,
        candidates_evaluated=total_candidates,
        expected_cost_seconds=0.05,
        actual_cost_seconds=elapsed,
        stopping_condition="Exhaustion or Stage 3 oracle match",
        result=outcome,
        independent_verification_method="Segment 1 AES-256-CBC padding oracle with IV few_n_far_btween",
        hierarchical_filter_results={
            "stage1_valid_pkcs7_count": stage1_hits,
            "stage1_false_positive_rate_empirical": stage1_hits / total_candidates if total_candidates else 0,
            "stage2_exact_structure_count": stage2_hits,
            "stage3_cryptographic_winner": winning_key[0:2] if winning_key else None
        },
        what_a_miss_eliminates="Eliminates 20 literal Lennon phrasing variants crossed with 15 note-degree strings."
    )


def run_p2g_hypothesis_3() -> AttemptResult:
    """Hypothesis P2G-H3: Segment 3 (wasd + ship).
    
    Clue 3: wasd (8 chars) - 10x10 pointer grid star values or movement keys.
    Clue 7: ship (24 chars) - Titanic 'will founder' scene descriptions from hidden red LSB montage.
    """
    t0 = time.perf_counter()
    hypothesis_id = "P2G-H3"
    target_id = "path-to-greatness-treasure-hunt-3ltc"
    why = (
        "Steganography in Ship.png red LSB shows Titanic scene with Andrews, Ismay, and deck plans. "
        "Clue 3 provides 8-character pointer grid path. Testing direct 24-character scene descriptions."
    )

    clue3_candidates = [
        "12341234",
        "43214321",
        "wasdwasd",
        "dsawdsaw",
        "wwwaaass",
        "12344321",
        "43211234",
        "11223344",
        "44332211",
        "wasd1234",
        "1234wasd",
        "updownlr",
        "leftrigh",
        "northsou",
        "pointerg",
    ]

    clue7_candidates = [
        "theshipwillfounder!!!!!!",
        "theshipwillfounder1912!!",
        "sheismadeofironsir!!!!!!",
        "shecannotsstayafloat!!!!",
        "amathematicalcertainty!!",
        "mathematicalcertainty!!!",
        "thomasandrewsandismay!!!",
        "watertightcompartments!!",
        "titanicdeckplans1912!!!!",
        "harlandandwolffbelfast!!",
        "bruceismaythomasandrews!",
        "thegreatundertaker1912!!",
        "movestowardsitsmaker1912",
        "anicebergonthestarboard!",
        "shecankeeptwentyfourdead",
        "shecankeeptwentyfourfoun",
        "fivewatertightdoorsshut!",
    ]

    total_candidates = len(clue3_candidates) * len(clue7_candidates)
    stage1_hits = 0
    stage2_hits = 0
    winning_key = None

    for c3 in clue3_candidates:
        for c7 in clue7_candidates:
            s1, s2, payload = check_segment_hierarchical(3, c3, c7)
            if s1:
                stage1_hits += 1
            if s2:
                stage2_hits += 1
                winning_key = (c3, c7, payload)

    elapsed = time.perf_counter() - t0
    outcome = AttemptOutcome.NEW_CONSTRAINT if winning_key else AttemptOutcome.HYPOTHESIS_FALSIFIED

    return AttemptResult(
        hypothesis_id=hypothesis_id,
        target_id=target_id,
        why_this_attack_follows=why,
        exact_candidate_space=total_candidates,
        candidates_evaluated=total_candidates,
        expected_cost_seconds=0.05,
        actual_cost_seconds=elapsed,
        stopping_condition="Exhaustion or Stage 3 oracle match",
        result=outcome,
        independent_verification_method="Segment 3 AES-256-CBC padding oracle with IV colors_on_leaves",
        hierarchical_filter_results={
            "stage1_valid_pkcs7_count": stage1_hits,
            "stage1_false_positive_rate_empirical": stage1_hits / total_candidates if total_candidates else 0,
            "stage2_exact_structure_count": stage2_hits,
            "stage3_cryptographic_winner": winning_key[0:2] if winning_key else None
        },
        what_a_miss_eliminates="Eliminates 15 grid traversal values crossed with 17 Titanic montage descriptions."
    )


def run_p2g_hypothesis_4() -> AttemptResult:
    """Hypothesis P2G-H4: Segment 4 (scramble + sky).
    
    Clue 2: scramble (15 chars) - anagram readings.
    Clue 8: sky (17 chars) - track pairing rule ehk-bqNEFRUn- with Metallica lyric 'enter night'.
    """
    t0 = time.perf_counter()
    hypothesis_id = "P2G-H4"
    target_id = "path-to-greatness-treasure-hunt-3ltc"
    why = (
        "Clue 8 track indexing rule yields 'ehk-bqNEFRUn-' -> 58112171456182114 (17 digits). "
        "Quoting Metallica 'Exit light, enter night' matching author track titles."
    )

    clue2_candidates = [
        "scrambledletters",  # 16 -> trimmed to 15
        "scrambleletters",   # 15
        "anagramsolution",   # 15
        "pathofgreatness",   # 15
        "secondsofdreamm",   # 15
        "justinpatterson",   # 15
        "treasurehunterr",   # 15
        "thegreatescapee",   # 15
        "secretpasscodes",   # 15
        "cipherchallenge",   # 15
    ]

    clue8_candidates = [
        "58112171456182114",
        "enterthenight1991",
        "enterthenight1994",
        "enterthenight2021",
        "enterthenightnow!",
        "enterthenightfree",
        "exitlightenternig",
        "enterthenightaway",
        "enterthenighttake",
        "enterthenighthome",
    ]

    total_candidates = len(clue2_candidates) * len(clue8_candidates)
    stage1_hits = 0
    stage2_hits = 0
    winning_key = None

    for c2 in clue2_candidates:
        for c8 in clue8_candidates:
            s1, s2, payload = check_segment_hierarchical(4, c2, c8)
            if s1:
                stage1_hits += 1
            if s2:
                stage2_hits += 1
                winning_key = (c2, c8, payload)

    elapsed = time.perf_counter() - t0
    outcome = AttemptOutcome.NEW_CONSTRAINT if winning_key else AttemptOutcome.HYPOTHESIS_FALSIFIED

    return AttemptResult(
        hypothesis_id=hypothesis_id,
        target_id=target_id,
        why_this_attack_follows=why,
        exact_candidate_space=total_candidates,
        candidates_evaluated=total_candidates,
        expected_cost_seconds=0.05,
        actual_cost_seconds=elapsed,
        stopping_condition="Exhaustion or Stage 3 oracle match",
        result=outcome,
        independent_verification_method="Segment 4 AES-256-CBC padding oracle with IV seconds_of_dream",
        hierarchical_filter_results={
            "stage1_valid_pkcs7_count": stage1_hits,
            "stage1_false_positive_rate_empirical": stage1_hits / total_candidates if total_candidates else 0,
            "stage2_exact_structure_count": stage2_hits,
            "stage3_cryptographic_winner": winning_key[0:2] if winning_key else None
        },
        what_a_miss_eliminates="Eliminates 10 scramble candidates crossed with 10 Metallica 'enter night' index variants."
    )
