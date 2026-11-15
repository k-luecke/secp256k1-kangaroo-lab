"""
Pure-Python secp256k1 Elliptic Curve Implementation
Provides exact, zero-dependency Jacobian projective point arithmetic,
scalar multiplication (k * G), and point stepping (P + G).
"""
from typing import Tuple, Optional

# Curve parameters for secp256k1
P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
A = 0
B = 7
ORDER = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141

# Base point G
GX = 0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798
GY = 0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8

# Point at infinity representation in Jacobian: (1, 1, 0)
INFINITY_JACOBIAN = (1, 1, 0)

def is_on_curve(x: int, y: int) -> bool:
    """Verify affine point (x, y) satisfies y^2 = x^3 + 7 (mod P)."""
    return (y * y - (x * x * x + B)) % P == 0

def jacobian_double(p: Tuple[int, int, int]) -> Tuple[int, int, int]:
    """Point doubling in Jacobian coordinates on a=0 curve: 2 * (X1, Y1, Z1)."""
    X1, Y1, Z1 = p
    if Y1 == 0:
        return INFINITY_JACOBIAN
    
    A_val = (X1 * X1) % P
    B_val = (Y1 * Y1) % P
    C_val = (B_val * B_val) % P
    D_val = (2 * ((X1 + B_val)**2 - A_val - C_val)) % P
    E_val = (3 * A_val) % P
    F_val = (E_val * E_val) % P
    
    X3 = (F_val - 2 * D_val) % P
    Y3 = (E_val * (D_val - X3) - 8 * C_val) % P
    Z3 = (2 * Y1 * Z1) % P
    return (X3, Y3, Z3)

def jacobian_add(p1: Tuple[int, int, int], p2: Tuple[int, int, int]) -> Tuple[int, int, int]:
    """Point addition in Jacobian coordinates: (X1, Y1, Z1) + (X2, Y2, Z2)."""
    X1, Y1, Z1 = p1
    X2, Y2, Z2 = p2
    
    if Z1 == 0:
        return p2
    if Z2 == 0:
        return p1
        
    Z1_sq = (Z1 * Z1) % P
    Z2_sq = (Z2 * Z2) % P
    
    U1 = (X1 * Z2_sq) % P
    U2 = (X2 * Z1_sq) % P
    S1 = (Y1 * Z2 * Z2_sq) % P
    S2 = (Y2 * Z1 * Z1_sq) % P
    
    if U1 == U2:
        if S1 != S2:
            return INFINITY_JACOBIAN
        return jacobian_double(p1)
        
    H = (U2 - U1) % P
    R = (S2 - S1) % P
    H2 = (H * H) % P
    H3 = (H * H2) % P
    U1_H2 = (U1 * H2) % P
    
    X3 = (R * R - H3 - 2 * U1_H2) % P
    Y3 = (R * (U1_H2 - X3) - S1 * H3) % P
    Z3 = (Z1 * Z2 * H) % P
    return (X3, Y3, Z3)

def jacobian_add_affine(p1: Tuple[int, int, int], p2_affine: Tuple[int, int]) -> Tuple[int, int, int]:
    """Mixed addition: Jacobian p1 + Affine p2 (Z2 = 1). Faster than general addition."""
    X1, Y1, Z1 = p1
    X2, Y2 = p2_affine
    
    if Z1 == 0:
        return (X2, Y2, 1)
        
    Z1_sq = (Z1 * Z1) % P
    U1 = X1
    U2 = (X2 * Z1_sq) % P
    S1 = Y1
    S2 = (Y2 * Z1 * Z1_sq) % P
    
    if U1 == U2:
        if S1 != S2:
            return INFINITY_JACOBIAN
        return jacobian_double(p1)
        
    H = (U2 - U1) % P
    R = (S2 - S1) % P
    H2 = (H * H) % P
    H3 = (H * H2) % P
    U1_H2 = (U1 * H2) % P
    
    X3 = (R * R - H3 - 2 * U1_H2) % P
    Y3 = (R * (U1_H2 - X3) - S1 * H3) % P
    Z3 = (Z1 * H) % P
    return (X3, Y3, Z3)

def to_affine(p: Tuple[int, int, int]) -> Optional[Tuple[int, int]]:
    """Convert Jacobian (X, Y, Z) to affine (x, y). Returns None if point at infinity."""
    X, Y, Z = p
    if Z == 0:
        return None
    Z_inv = pow(Z, P - 2, P)
    Z_inv2 = (Z_inv * Z_inv) % P
    Z_inv3 = (Z_inv * Z_inv2) % P
    return ((X * Z_inv2) % P, (Y * Z_inv3) % P)

def scalar_mult(k: int, p_affine: Optional[Tuple[int, int]] = None) -> Optional[Tuple[int, int]]:
    """
    Compute Q = k * P on secp256k1.
    If p_affine is None, uses generator G.
    Returns affine coordinates (x, y) or None if k*P = infinity.
    """
    k = k % ORDER
    if k == 0:
        return None
        
    if p_affine is None:
        base_jac = (GX, GY, 1)
    else:
        base_jac = (p_affine[0], p_affine[1], 1)
        
    res = INFINITY_JACOBIAN
    addend = base_jac
    
    while k > 0:
        if k & 1:
            res = jacobian_add(res, addend)
        addend = jacobian_double(addend)
        k >>= 1
        
    return to_affine(res)
