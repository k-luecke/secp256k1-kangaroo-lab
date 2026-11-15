"""
Published Bitcoin Transaction Puzzle Registry (Historical 2015 Challenge)
Source: Bitcoin Transaction 08389f34c98c606322740c0be6a7114d2d277787f16548b0825da76d9229724f
Public specifications are strictly quarantined from ground-truth solutions.
"""
from typing import Dict, Any, Optional
from puzzle_solver.specs.schema import PuzzleSpec, TargetSpec, CandidateSpaceSpec, ConstraintSpec, VerificationSpec

# Quarantined ground truth table (used exclusively by test harnesses for post-hoc validation)
_QUARANTINED_TRUTH = {
    "btc_2015_001": 0x1,
    "btc_2015_002": 0x3,
    "btc_2015_003": 0x7,
    "btc_2015_004": 0x8,
    "btc_2015_005": 0x15,
    "btc_2015_006": 0x31,
    "btc_2015_007": 0x4c,
    "btc_2015_008": 0xe0,
    "btc_2015_009": 0x1d3,
    "btc_2015_010": 0x202,
    "btc_2015_011": 0x483,
    "btc_2015_012": 0xa7b,
    "btc_2015_013": 0x1460,
    "btc_2015_014": 0x2930,
    "btc_2015_015": 0x68f3,
    "btc_2015_016": 0xc936,
}

# Public specifications (consumed by the solver algorithm - NO private keys)
_PUBLIC_SPECS = {
    "btc_2015_001": {
        "title": "Bitcoin 2015 Challenge - Puzzle #1",
        "target_addr": "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH",
        "bits": 1,
        "lower": 1,
        "upper": 1,
    },
    "btc_2015_002": {
        "title": "Bitcoin 2015 Challenge - Puzzle #2",
        "target_addr": "1CUNEBjYrCn2y1SdiUMohaKUi4wpP326Lb",
        "bits": 2,
        "lower": 2,
        "upper": 3,
    },
    "btc_2015_003": {
        "title": "Bitcoin 2015 Challenge - Puzzle #3",
        "target_addr": "19ZewH8Kk1PDbSNdJ97FP4EiCjTRaZMZQA",
        "bits": 3,
        "lower": 4,
        "upper": 7,
    },
    "btc_2015_004": {
        "title": "Bitcoin 2015 Challenge - Puzzle #4",
        "target_addr": "1EhqbyUMvvs7BfL8goY6qcPbD6YKfPqb7e",
        "bits": 4,
        "lower": 8,
        "upper": 15,
    },
    "btc_2015_005": {
        "title": "Bitcoin 2015 Challenge - Puzzle #5",
        "target_addr": "1E6NuFjCi27W5zoXg8TRdcSRq84zJeBW3k",
        "bits": 5,
        "lower": 16,
        "upper": 31,
    },
    "btc_2015_006": {
        "title": "Bitcoin 2015 Challenge - Puzzle #6",
        "target_addr": "1PitScNLyp2HCygzadCh7FveTnfmpPbfp8",
        "bits": 6,
        "lower": 32,
        "upper": 63,
    },
    "btc_2015_007": {
        "title": "Bitcoin 2015 Challenge - Puzzle #7",
        "target_addr": "1McVt1vMtCC7yn5b9wgX1833yCcLXzueeC",
        "bits": 7,
        "lower": 64,
        "upper": 127,
    },
    "btc_2015_008": {
        "title": "Bitcoin 2015 Challenge - Puzzle #8",
        "target_addr": "1M92tSqNmQLYw33fuBvjmeadirh1ysMBxK",
        "bits": 8,
        "lower": 128,
        "upper": 255,
    },
    "btc_2015_009": {
        "title": "Bitcoin 2015 Challenge - Puzzle #9",
        "target_addr": "1CQFwcjw1dwhtkVWBttNLDtqL7ivBonGPV",
        "bits": 9,
        "lower": 256,
        "upper": 511,
    },
    "btc_2015_010": {
        "title": "Bitcoin 2015 Challenge - Puzzle #10",
        "target_addr": "1LeBZP5QCwwgXRtmVUvTVrraqPUokyLHqe",
        "bits": 10,
        "lower": 512,
        "upper": 1023,
    },
    "btc_2015_011": {
        "title": "Bitcoin 2015 Challenge - Puzzle #11",
        "target_addr": "1PgQVLmst3Z314JrQn5TNiys8Hc38TcXJu",
        "bits": 11,
        "lower": 1024,
        "upper": 2047,
    },
    "btc_2015_012": {
        "title": "Bitcoin 2015 Challenge - Puzzle #12",
        "target_addr": "1DBaumZxUkM4qMQRt2LVWyFJq5kDtSZQot",
        "bits": 12,
        "lower": 2048,
        "upper": 4095,
    },
    "btc_2015_013": {
        "title": "Bitcoin 2015 Challenge - Puzzle #13",
        "target_addr": "1Pie8JkxBT6MGPz9Nvi3fsPkr2D8q3GBc1",
        "bits": 13,
        "lower": 4096,
        "upper": 8191,
    },
    "btc_2015_014": {
        "title": "Bitcoin 2015 Challenge - Puzzle #14",
        "target_addr": "1ErZWg5cFCe4Vw5BzgfzB74VNLaXEiEkhk",
        "bits": 14,
        "lower": 8192,
        "upper": 16383,
    },
    "btc_2015_015": {
        "title": "Bitcoin 2015 Challenge - Puzzle #15",
        "target_addr": "1QCbW9HWnwQWiQqVo5exhAnmfqKRrCRsvW",
        "bits": 15,
        "lower": 16384,
        "upper": 32767,
    },
    "btc_2015_016": {
        "title": "Bitcoin 2015 Challenge - Puzzle #16",
        "target_addr": "1BDyrQ6WoF8VN3g9SAS1iKZcPzFfnDVieY",
        "bits": 16,
        "lower": 32768,
        "upper": 65535,
    },
}

def get_puzzle_spec(puzzle_id: str) -> PuzzleSpec:
    """Return public specification for puzzle_id without private key."""
    if puzzle_id not in _PUBLIC_SPECS:
        raise KeyError(f"Unknown puzzle ID: {puzzle_id}")
    raw = _PUBLIC_SPECS[puzzle_id]
    return PuzzleSpec(
        puzzle_id=puzzle_id,
        title=raw["title"],
        provenance="tx:08389f34c98c606322740c0be6a7114d2d277787f16548b0825da76d9229724f",
        target=TargetSpec(
            target_type="bitcoin_address_p2pkh_compressed",
            target_value=raw["target_addr"]
        ),
        candidate_space=CandidateSpaceSpec(
            space_type="bounded_integer_private_key",
            lower_bound=raw["lower"],
            upper_bound=raw["upper"],
            bits=raw["bits"]
        ),
        constraints=[
            ConstraintSpec(
                constraint_type="range",
                parameters={"min": raw["lower"], "max": raw["upper"]}
            )
        ],
        verification=VerificationSpec(
            curve="secp256k1",
            transform_chain=["scalar_mult_G", "serialize_pubkey_compressed", "hash160", "base58check"]
        ),
        allowed_operators=["range_filter", "address_match"],
        benchmark_baseline="sequential_scan"
    )

def get_quarantined_truth(puzzle_id: str) -> int:
    """
    Return ground truth private key for puzzle_id.
    RESTRICTED: Test harnesses only for post-hoc validation.
    """
    if puzzle_id not in _QUARANTINED_TRUTH:
        raise KeyError(f"No quarantined truth for puzzle ID: {puzzle_id}")
    return _QUARANTINED_TRUTH[puzzle_id]
