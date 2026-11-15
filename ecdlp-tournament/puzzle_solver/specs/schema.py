"""
Puzzle Target Specification Schema
Defines the machine-readable schema for intentionally published cryptographic puzzles.
Runtime specifications must NOT contain the known solution.
"""
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Tuple
import json

@dataclass(frozen=True)
class TargetSpec:
    target_type: str            # e.g., 'bitcoin_address_p2pkh_compressed', 'bitcoin_address_p2pkh_uncompressed'
    target_value: str           # e.g., '1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH'

@dataclass(frozen=True)
class CandidateSpaceSpec:
    space_type: str             # e.g., 'bounded_integer_private_key'
    lower_bound: int            # Inclusive lower bound
    upper_bound: int            # Inclusive upper bound
    bits: int                   # Key bit length (e.g. 1 to 160)

@dataclass(frozen=True)
class ConstraintSpec:
    constraint_type: str        # e.g., 'range', 'modular', 'prefix_bits', 'parity'
    parameters: Dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class VerificationSpec:
    curve: str                  # e.g., 'secp256k1'
    transform_chain: List[str]  # e.g., ['scalar_mult_G', 'serialize_pubkey', 'hash160', 'base58check']

@dataclass(frozen=True)
class PuzzleSpec:
    puzzle_id: str              # Unique identifier, e.g., 'btc_2015_challenge_001'
    title: str                  # Human-readable title
    provenance: str             # Transaction hash / publication source
    target: TargetSpec
    candidate_space: CandidateSpaceSpec
    constraints: List[ConstraintSpec] = field(default_factory=list)
    verification: VerificationSpec = field(
        default_factory=lambda: VerificationSpec(
            curve='secp256k1',
            transform_chain=['scalar_mult_G', 'serialize_pubkey', 'hash160', 'base58check']
        )
    )
    allowed_operators: List[str] = field(default_factory=list)
    benchmark_baseline: str = 'sequential_scan'
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PuzzleSpec':
        target = TargetSpec(**data['target'])
        candidate_space = CandidateSpaceSpec(**data['candidate_space'])
        constraints = [ConstraintSpec(**c) for c in data.get('constraints', [])]
        verif_data = data.get('verification', {
            'curve': 'secp256k1',
            'transform_chain': ['scalar_mult_G', 'serialize_pubkey', 'hash160', 'base58check']
        })
        verification = VerificationSpec(**verif_data)
        return cls(
            puzzle_id=data['puzzle_id'],
            title=data['title'],
            provenance=data['provenance'],
            target=target,
            candidate_space=candidate_space,
            constraints=constraints,
            verification=verification,
            allowed_operators=data.get('allowed_operators', []),
            benchmark_baseline=data.get('benchmark_baseline', 'sequential_scan'),
            metadata=data.get('metadata', {})
        )

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> 'PuzzleSpec':
        return cls.from_dict(json.loads(json_str))
