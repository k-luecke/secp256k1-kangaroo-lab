"""
Bitcoin Address Generation and Verification
Implements public key serialization (compressed and uncompressed),
Hash160 (SHA-256 + RIPEMD-160), and Base58Check encoding/decoding.
"""
import hashlib
from typing import Tuple, Optional
from puzzle_solver.verification.secp256k1 import scalar_mult

# Standard Base58 alphabet (Bitcoin)
ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
ALPHABET_MAP = {c: i for i, c in enumerate(ALPHABET)}

def pubkey_to_bytes(point: Tuple[int, int], compressed: bool = True) -> bytes:
    """Serialize affine pubkey point (x, y) into SEC format bytes."""
    x, y = point
    x_bytes = x.to_bytes(32, byteorder='big')
    if compressed:
        prefix = b'\x02' if (y % 2 == 0) else b'\x03'
        return prefix + x_bytes
    else:
        y_bytes = y.to_bytes(32, byteorder='big')
        return b'\x04' + x_bytes + y_bytes

def hash160(data: bytes) -> bytes:
    """Compute RIPEMD-160(SHA-256(data))."""
    sha = hashlib.sha256(data).digest()
    return hashlib.new('ripemd160', sha).digest()

def base58_encode(b: bytes) -> str:
    """Encode bytes into Bitcoin Base58 string."""
    n = int.from_bytes(b, byteorder='big')
    chars = []
    while n > 0:
        n, r = divmod(n, 58)
        chars.append(ALPHABET[r])
    res = "".join(reversed(chars))
    
    # Handle leading zero bytes
    pad = 0
    for byte in b:
        if byte == 0:
            pad += 1
        else:
            break
    return (ALPHABET[0] * pad) + res

def base58_decode(s: str) -> bytes:
    """Decode Bitcoin Base58 string into bytes."""
    n = 0
    for c in s:
        n = n * 58 + ALPHABET_MAP[c]
    
    # Convert integer to bytes
    res = []
    while n > 0:
        n, r = divmod(n, 256)
        res.append(r)
    decoded = bytes(reversed(res))
    
    # Handle leading '1's
    pad = 0
    for c in s:
        if c == ALPHABET[0]:
            pad += 1
        else:
            break
    return (b'\x00' * pad) + decoded

def base58check_encode(payload: bytes, version_byte: bytes = b'\x00') -> str:
    """Compute Base58Check string from payload and version byte."""
    data = version_byte + payload
    checksum = hashlib.sha256(hashlib.sha256(data).digest()).digest()[:4]
    return base58_encode(data + checksum)

def base58check_decode(addr: str) -> Tuple[bytes, bytes]:
    """
    Decode Base58Check address.
    Returns (version_byte, payload).
    Raises ValueError if checksum is invalid.
    """
    decoded = base58_decode(addr)
    if len(decoded) < 5:
        raise ValueError(f"Base58Check payload too short: {len(decoded)} bytes")
    data, checksum = decoded[:-4], decoded[-4:]
    expected_checksum = hashlib.sha256(hashlib.sha256(data).digest()).digest()[:4]
    if checksum != expected_checksum:
        raise ValueError(f"Invalid Base58Check checksum for address: {addr}")
    version_byte = data[:1]
    payload = data[1:]
    return version_byte, payload

def pubkey_to_address(point: Tuple[int, int], compressed: bool = True) -> str:
    """Convert affine public key point (x, y) to Base58Check P2PKH address."""
    pub_bytes = pubkey_to_bytes(point, compressed=compressed)
    h160 = hash160(pub_bytes)
    return base58check_encode(h160, version_byte=b'\x00')

def privkey_to_address(k: int, compressed: bool = True) -> str:
    """Convert integer private key k to Base58Check P2PKH address."""
    point = scalar_mult(k)
    if point is None:
        raise ValueError("Invalid private key: point at infinity")
    return pubkey_to_address(point, compressed=compressed)

def address_to_hash160(addr: str) -> bytes:
    """Extract raw 20-byte Hash160 from Base58Check address."""
    _, payload = base58check_decode(addr)
    return payload
