/*
 * secp256k1_arithmetic.cl
 * Phase 1: Verified, Independent OpenCL Field and Elliptic Curve Arithmetic
 * Platform: AMD OpenCL (gfx90c / RDNA / Vega)
 * Representation: 8 x 32-bit limbs (little-endian)
 * Curve: y^2 = x^3 + 7 (mod p), where p = 2^256 - 2^32 - 977
 */

typedef struct {
    uint v[8];
} fe256;

typedef struct {
    fe256 x;
    fe256 y;
    int is_infinity;
} pt_affine;

typedef struct {
    fe256 X;
    fe256 Y;
    fe256 Z;
    int is_infinity;
} pt_jacobian;

// Constant prime p = 2^256 - 2^32 - 977
// 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
__constant uint SECP256K1_P[8] = {
    0xFFFFFC2FU, 0xFFFFFFFEU, 0xFFFFFFFFU, 0xFFFFFFFFU,
    0xFFFFFFFFU, 0xFFFFFFFFU, 0xFFFFFFFFU, 0xFFFFFFFFU
};

// Generator point G in affine coordinates
__constant uint SECP256K1_GX[8] = {
    0x16F81798U, 0x59F2815BU, 0x2DCE28D9U, 0x029BFCDBU,
    0xCE870B07U, 0x55A06295U, 0xF9DCBBACU, 0x79BE667EU
};

__constant uint SECP256K1_GY[8] = {
    0xFB10D4B8U, 0x9C47D08FU, 0xA6855419U, 0xFD17B448U,
    0x0E1108A8U, 0x5DA4FBFCU, 0x26A3C465U, 0x483ADA77U
};

// -------------------------------------------------------------
// Field Primitive Functions
// -------------------------------------------------------------

inline void fe_set_zero(fe256 *r) {
    #pragma unroll
    for (int i = 0; i < 8; ++i) r->v[i] = 0;
}

inline void fe_set_one(fe256 *r) {
    r->v[0] = 1;
    #pragma unroll
    for (int i = 1; i < 8; ++i) r->v[i] = 0;
}

inline void fe_copy(fe256 *dst, const fe256 *src) {
    #pragma unroll
    for (int i = 0; i < 8; ++i) dst->v[i] = src->v[i];
}

inline void fe_copy_from_constant(fe256 *dst, __constant const fe256 *src) {
    #pragma unroll
    for (int i = 0; i < 8; ++i) dst->v[i] = src->v[i];
}

inline void fe_copy_from_global(fe256 *dst, __global const fe256 *src) {
    #pragma unroll
    for (int i = 0; i < 8; ++i) dst->v[i] = src->v[i];
}

inline void fe_copy_to_global(__global fe256 *dst, const fe256 *src) {
    #pragma unroll
    for (int i = 0; i < 8; ++i) dst->v[i] = src->v[i];
}

inline int fe_is_zero(const fe256 *a) {
    return (a->v[0] | a->v[1] | a->v[2] | a->v[3] | a->v[4] | a->v[5] | a->v[6] | a->v[7]) == 0;
}

inline int fe_eq(const fe256 *a, const fe256 *b) {
    return ((a->v[0] ^ b->v[0]) | (a->v[1] ^ b->v[1]) | (a->v[2] ^ b->v[2]) | (a->v[3] ^ b->v[3]) |
            (a->v[4] ^ b->v[4]) | (a->v[5] ^ b->v[5]) | (a->v[6] ^ b->v[6]) | (a->v[7] ^ b->v[7])) == 0;
}

// Compare a >= b in 256-bit unsigned
inline int fe_gte(const fe256 *a, const fe256 *b) {
    for (int i = 7; i >= 0; --i) {
        if (a->v[i] > b->v[i]) return 1;
        if (a->v[i] < b->v[i]) return 0;
    }
    return 1;
}

// 256-bit raw addition with carry
inline uint add256(fe256 *r, const fe256 *a, const fe256 *b) {
    ulong carry = 0;
    #pragma unroll
    for (int i = 0; i < 8; ++i) {
        ulong sum = (ulong)a->v[i] + (ulong)b->v[i] + carry;
        r->v[i] = (uint)sum;
        carry = sum >> 32;
    }
    return (uint)carry;
}

// 256-bit raw subtraction with borrow
inline uint sub256(fe256 *r, const fe256 *a, const fe256 *b) {
    long borrow = 0;
    #pragma unroll
    for (int i = 0; i < 8; ++i) {
        long diff = (long)(ulong)a->v[i] - (long)(ulong)b->v[i] - borrow;
        r->v[i] = (uint)diff;
        borrow = (diff < 0) ? 1 : 0;
    }
    return (uint)borrow;
}

// Modular addition: r = (a + b) mod p
inline void fe_add(fe256 *r, const fe256 *a, const fe256 *b) {
    fe256 sum;
    uint carry = add256(&sum, a, b);
    
    // Check if sum >= p (or carry occurred)
    fe256 const_p;
    #pragma unroll
    for (int i = 0; i < 8; ++i) const_p.v[i] = SECP256K1_P[i];

    if (carry || fe_gte(&sum, &const_p)) {
        sub256(r, &sum, &const_p);
    } else {
        fe_copy(r, &sum);
    }
}

// Modular subtraction: r = (a - b) mod p
inline void fe_sub(fe256 *r, const fe256 *a, const fe256 *b) {
    fe256 diff;
    uint borrow = sub256(&diff, a, b);

    if (borrow) {
        fe256 const_p;
        #pragma unroll
        for (int i = 0; i < 8; ++i) const_p.v[i] = SECP256K1_P[i];
        add256(r, &diff, &const_p);
    } else {
        fe_copy(r, &diff);
    }
}

// -------------------------------------------------------------
// 512-bit Multiplication & Pseudo-Mersenne Reduction
// -------------------------------------------------------------

// r = (a * b) mod p
void fe_mul(fe256 *r, const fe256 *a, const fe256 *b) {
    uint c[16];
    #pragma unroll
    for (int i = 0; i < 16; ++i) c[i] = 0;

    // Schoolbook 8x8 multiplication producing 16 32-bit limbs
    for (int i = 0; i < 8; ++i) {
        ulong carry = 0;
        ulong ai = (ulong)a->v[i];
        for (int j = 0; j < 8; ++j) {
            ulong prod = ai * (ulong)b->v[j] + (ulong)c[i + j] + carry;
            c[i + j] = (uint)prod;
            carry = prod >> 32;
        }
        c[i + 8] = (uint)carry;
    }

    // Pseudo-Mersenne reduction for secp256k1:
    // p = 2^256 - 0x1000003D1, meaning 2^256 = 0x1000003D1 mod p
    // Const K = 0x1000003D1 = 4294968273 = (1 << 32) + 977
    // Let 512-bit number be C = H * 2^256 + L.
    // C = H * 0x1000003D1 + L mod p
    
    ulong acc = 0;
    uint r_limbs[10]; // Intermediate limbs up to ~300 bits
    #pragma unroll
    for (int i = 0; i < 10; ++i) r_limbs[i] = 0;

    // First, copy lower 256 bits L into r_limbs
    #pragma unroll
    for (int i = 0; i < 8; ++i) r_limbs[i] = c[i];

    // Multiply H (c[8..15]) by 977 and add to r_limbs
    ulong carry977 = 0;
    for (int i = 0; i < 8; ++i) {
        ulong term = (ulong)c[i + 8] * 977ULL + (ulong)r_limbs[i] + carry977;
        r_limbs[i] = (uint)term;
        carry977 = term >> 32;
    }
    // Propagate carry977 into limb 8
    ulong sum8 = (ulong)r_limbs[8] + carry977;
    r_limbs[8] = (uint)sum8;
    r_limbs[9] = (uint)(sum8 >> 32);

    // Multiply H (c[8..15]) by 2^32 (shifted by 1 limb) and add to r_limbs
    ulong carry_shift = 0;
    for (int i = 0; i < 8; ++i) {
        ulong term = (ulong)c[i + 8] + (ulong)r_limbs[i + 1] + carry_shift;
        r_limbs[i + 1] = (uint)term;
        carry_shift = term >> 32;
    }
    ulong sum9 = (ulong)r_limbs[9] + carry_shift;
    r_limbs[9] = (uint)sum9;

    // Second fold: upper limbs (r_limbs[8] and r_limbs[9])
    // Upper value U = r_limbs[8] + (r_limbs[9] << 32)
    ulong U = ((ulong)r_limbs[9] << 32) | (ulong)r_limbs[8];
    if (U > 0) {
        // Add U * 977 to r_limbs[0..7]
        ulong term_u = U * 977ULL;
        ulong c_u = 0;
        ulong s0 = (ulong)r_limbs[0] + (uint)term_u;
        r_limbs[0] = (uint)s0;
        c_u = (s0 >> 32) + (term_u >> 32);
        for (int i = 1; i < 8; ++i) {
            ulong s = (ulong)r_limbs[i] + c_u;
            r_limbs[i] = (uint)s;
            c_u = s >> 32;
        }

        // Add U * 2^32 (shift by 1 limb)
        ulong c_s = 0;
        ulong s1 = (ulong)r_limbs[1] + (uint)U;
        r_limbs[1] = (uint)s1;
        c_s = (s1 >> 32) + (U >> 32);
        for (int i = 2; i < 8; ++i) {
            ulong s = (ulong)r_limbs[i] + c_s;
            r_limbs[i] = (uint)s;
            c_s = s >> 32;
        }

        // Any trailing carry is at most 1 or 2, add it folded
        ulong overflow = c_u + c_s;
        if (overflow > 0) {
            ulong s_ov = (ulong)r_limbs[0] + overflow * 977ULL;
            r_limbs[0] = (uint)s_ov;
            ulong c_ov = (s_ov >> 32);
            ulong s_ov1 = (ulong)r_limbs[1] + overflow + c_ov;
            r_limbs[1] = (uint)s_ov1;
            c_ov = s_ov1 >> 32;
            for (int i = 2; i < 8; ++i) {
                ulong s = (ulong)r_limbs[i] + c_ov;
                r_limbs[i] = (uint)s;
                c_ov = s >> 32;
            }
        }
    }

    // Final reduction modulo p: while r >= p, r -= p
    fe256 res;
    #pragma unroll
    for (int i = 0; i < 8; ++i) res.v[i] = r_limbs[i];

    fe256 const_p;
    #pragma unroll
    for (int i = 0; i < 8; ++i) const_p.v[i] = SECP256K1_P[i];

    // At most 2 subtractions needed
    if (fe_gte(&res, &const_p)) {
        sub256(&res, &res, &const_p);
    }
    if (fe_gte(&res, &const_p)) {
        sub256(&res, &res, &const_p);
    }

    fe_copy(r, &res);
}

inline void fe_sqr(fe256 *r, const fe256 *a) {
    fe_mul(r, a, a);
}

// Inversion via Fermat's Little Theorem: a^(p-2) mod p
// p - 2 = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2D
__attribute__((noinline)) void fe_inv(fe256 *r, const fe256 *a) {
    fe256 t, out;
    fe_set_one(&out);
    fe_copy(&t, a);

    // p-2 binary expansion: 256 bits
    // We compute square and multiply across all bits
    for (int i = 0; i < 8; ++i) {
        uint limb = SECP256K1_P[i];
        if (i == 0) limb -= 2; // p - 2
        for (int b = 0; b < 32; ++b) {
            if ((limb >> b) & 1) {
                fe_mul(&out, &out, &t);
            }
            fe_sqr(&t, &t);
        }
    }
    fe_copy(r, &out);
}

// -------------------------------------------------------------
// Elliptic Curve Group Operations (secp256k1: y^2 = x^3 + 7)
// -------------------------------------------------------------

// Jacobian Point Doubling: R = 2 * P (for a = 0)
// Input: P in Jacobian (X1 : Y1 : Z1)
// Output: R in Jacobian (X3 : Y3 : Z3)
// Cost: 3M + 4S
__attribute__((noinline)) void pt_double_jacobian(pt_jacobian *r, const pt_jacobian *p) {
    if (p->is_infinity || fe_is_zero(&p->Y)) {
        r->is_infinity = 1;
        fe_set_zero(&r->X);
        fe_set_zero(&r->Y);
        fe_set_zero(&r->Z);
    } else {
        fe256 A, B, C, D, X3, Y3, Z3;
        // A = X1^2
        fe_sqr(&A, &p->X);
        // B = Y1^2
        fe_sqr(&B, &p->Y);
        // C = B^2 = Y1^4
        fe_sqr(&C, &B);
        
        // D = 2 * ((X1 + B)^2 - A - C) = 4 * X1 * Y1^2
        fe256 t1;
        fe_add(&t1, &p->X, &B);
        fe_sqr(&t1, &t1);
        fe_sub(&t1, &t1, &A);
        fe_sub(&t1, &t1, &C);
        fe_add(&D, &t1, &t1);

        // E = 3 * A
        fe256 E;
        fe_add(&E, &A, &A);
        fe_add(&E, &E, &A);

        // X3 = E^2 - 2 * D
        fe_sqr(&X3, &E);
        fe_sub(&X3, &X3, &D);
        fe_sub(&X3, &X3, &D);

        // Z3 = 2 * Y1 * Z1
        fe_mul(&Z3, &p->Y, &p->Z);
        fe_add(&Z3, &Z3, &Z3);

        // Y3 = E * (D - X3) - 8 * C
        fe256 C8;
        fe_add(&C8, &C, &C); // 2C
        fe_add(&C8, &C8, &C8); // 4C
        fe_add(&C8, &C8, &C8); // 8C
        fe_sub(&t1, &D, &X3);
        fe_mul(&Y3, &E, &t1);
        fe_sub(&Y3, &Y3, &C8);

        r->X = X3;
        r->Y = Y3;
        r->Z = Z3;
        r->is_infinity = 0;
    }
}

// Mixed Affine-Jacobian Addition: R = P (Jacobian) + Q (Affine)
// Input: P = (X1 : Y1 : Z1), Q = (x2, y2)
// Output: R = (X3 : Y3 : Z3)
// Cost: 7M + 4S + 0I
__attribute__((noinline)) void pt_add_mixed(pt_jacobian *r, const pt_jacobian *p, const pt_affine *q) {
    if (q->is_infinity) {
        r->X = p->X;
        r->Y = p->Y;
        r->Z = p->Z;
        r->is_infinity = p->is_infinity;
    } else if (p->is_infinity) {
        r->X = q->x;
        r->Y = q->y;
        fe_set_one(&r->Z);
        r->is_infinity = 0;
    } else {
        fe256 Z1Z1, U2, S2, H, r_val;
        // Z1Z1 = Z1^2
        fe_sqr(&Z1Z1, &p->Z);
        // U2 = x2 * Z1Z1
        fe_mul(&U2, &q->x, &Z1Z1);
        // S2 = y2 * Z1 * Z1Z1 = y2 * Z1^3
        fe256 Z1_cubed;
        fe_mul(&Z1_cubed, &p->Z, &Z1Z1);
        fe_mul(&S2, &q->y, &Z1_cubed);

        // H = U2 - X1
        fe_sub(&H, &U2, &p->X);
        // r_val = 2 * (S2 - Y1)
        fe256 diff_s;
        fe_sub(&diff_s, &S2, &p->Y);
        fe_add(&r_val, &diff_s, &diff_s);

        int h_zero = fe_is_zero(&H);
        int r_zero = fe_is_zero(&r_val);
        if (h_zero) {
            if (r_zero) {
                pt_double_jacobian(r, p);
            } else {
                r->is_infinity = 1;
                fe_set_zero(&r->X);
                fe_set_zero(&r->Y);
                fe_set_zero(&r->Z);
            }
        } else {
            fe256 HH, I, J, V;
            // HH = H^2
            fe_sqr(&HH, &H);
            // I = 4 * HH
            fe256 I2;
            fe_add(&I2, &HH, &HH);
            fe_add(&I, &I2, &I2);
            // J = H * I
            fe_mul(&J, &H, &I);
            // V = X1 * I
            fe_mul(&V, &p->X, &I);

            // X3 = r_val^2 - J - 2 * V
            fe256 X3, V2;
            fe_sqr(&X3, &r_val);
            fe_sub(&X3, &X3, &J);
            fe_add(&V2, &V, &V);
            fe_sub(&X3, &X3, &V2);

            // Y3 = r_val * (V - X3) - 2 * Y1 * J
            fe256 Y3, t_v, Y1J2;
            fe_sub(&t_v, &V, &X3);
            fe_mul(&Y3, &r_val, &t_v);
            fe_mul(&Y1J2, &p->Y, &J);
            fe_add(&Y1J2, &Y1J2, &Y1J2);
            fe_sub(&Y3, &Y3, &Y1J2);

            // Z3 = (Z1 + H)^2 - Z1Z1 - HH
            fe256 Z3, t_zh;
            fe_add(&t_zh, &p->Z, &H);
            fe_sqr(&Z3, &t_zh);
            fe_sub(&Z3, &Z3, &Z1Z1);
            fe_sub(&Z3, &Z3, &HH);

            r->X = X3;
            r->Y = Y3;
            r->Z = Z3;
            r->is_infinity = 0;
        }
    }
}

// Convert Jacobian to Affine: (X : Y : Z) -> (x, y) = (X/Z^2, Y/Z^3)
__attribute__((noinline)) void pt_to_affine(pt_affine *out, const pt_jacobian *p) {
    if (p->is_infinity || fe_is_zero(&p->Z)) {
        out->is_infinity = 1;
        fe_set_zero(&out->x);
        fe_set_zero(&out->y);
    } else {
        fe256 z, px, py;
        fe_copy(&z, &p->Z);
        fe_copy(&px, &p->X);
        fe_copy(&py, &p->Y);

        fe256 z_inv, z_inv2, z_inv3;
        fe_inv(&z_inv, &z);
        fe_sqr(&z_inv2, &z_inv);
        fe_mul(&z_inv3, &z_inv2, &z_inv);

        fe256 ox, oy;
        fe_mul(&ox, &px, &z_inv2);
        fe_mul(&oy, &py, &z_inv3);

        out->x = ox;
        out->y = oy;
        out->is_infinity = 0;
    }
}

// -------------------------------------------------------------
// OpenCL Validation Kernels
// -------------------------------------------------------------

typedef struct {
    fe256 x;
    fe256 y;
    ulong distance;
    uint is_tame;
    uint walker_id;
} dp_record;

// Kernel 1: Pure Mixed Addition Step (7M + 4S)
// Canonical jump index determined strictly by previous affine x
__kernel void kangaroo_step_pure(
    __global pt_jacobian *walkers,
    __global const fe256 *walker_aff_x,
    __global ulong *walker_dist,
    __constant const pt_affine *jump_table,
    __constant const ulong *jump_distances,
    const uint num_walkers
) {
    uint gid = get_global_id(0);
    if (gid >= num_walkers) return;

    uint jump_idx = walker_aff_x[gid].v[0] & 31;
    pt_affine j;
    fe_copy_from_constant(&j.x, &jump_table[jump_idx].x);
    fe_copy_from_constant(&j.y, &jump_table[jump_idx].y);
    j.is_infinity = 0;

    walker_dist[gid] += jump_distances[jump_idx];

    pt_jacobian p;
    fe_copy_from_global(&p.X, &walkers[gid].X);
    fe_copy_from_global(&p.Y, &walkers[gid].Y);
    fe_copy_from_global(&p.Z, &walkers[gid].Z);
    p.is_infinity = walkers[gid].is_infinity;

    pt_jacobian next_p;
    pt_add_mixed(&next_p, &p, &j);

    fe_copy_to_global(&walkers[gid].X, &next_p.X);
    fe_copy_to_global(&walkers[gid].Y, &next_p.Y);
    fe_copy_to_global(&walkers[gid].Z, &next_p.Z);
    walkers[gid].is_infinity = next_p.is_infinity;
}

// Kernel 2: Decoupled Affine Normalization & Atomic DP Trapping
__kernel void kangaroo_norm_and_dp(
    __global const pt_jacobian *walkers,
    __global fe256 *walker_aff_x,
    __global const ulong *walker_dist,
    __global const uint *walker_tame,
    __global dp_record *dp_buffer,
    __global volatile uint *dp_count,
    const uint max_dps,
    const uint dp_mask,
    const uint num_walkers
) {
    uint gid = get_global_id(0);
    if (gid >= num_walkers) return;

    pt_jacobian p;
    fe_copy_from_global(&p.X, &walkers[gid].X);
    fe_copy_from_global(&p.Y, &walkers[gid].Y);
    fe_copy_from_global(&p.Z, &walkers[gid].Z);
    p.is_infinity = walkers[gid].is_infinity;

    pt_affine aff;
    pt_to_affine(&aff, &p);

    fe_copy_to_global(&walker_aff_x[gid], &aff.x);

    if ((aff.x.v[0] & dp_mask) == 0 && !aff.is_infinity) {
        uint slot = atomic_inc(dp_count);
        if (slot < max_dps) {
            fe_copy_to_global(&dp_buffer[slot].x, &aff.x);
            fe_copy_to_global(&dp_buffer[slot].y, &aff.y);
            dp_buffer[slot].distance = walker_dist[gid];
            dp_buffer[slot].is_tame = walker_tame[gid];
            dp_buffer[slot].walker_id = gid;
        }
    }
}

// Kernel 3: Fast GPU Wild Herd Initialization (Sub-millisecond setup)
__kernel void kangaroo_init_wild(
    __global pt_jacobian *walkers,
    __global fe256 *walker_aff_x,
    __global ulong *walker_dist,
    __global const pt_affine *wild_offsets,
    __global const ulong *wild_offset_dists,
    const fe256 target_x,
    const fe256 target_y,
    const uint num_tame,
    const uint num_wild
) {
    uint gid = get_global_id(0);
    if (gid >= num_wild) return;
    uint walker_idx = num_tame + gid;

    pt_jacobian q_jac;
    fe_copy(&q_jac.X, &target_x);
    fe_copy(&q_jac.Y, &target_y);
    fe_set_one(&q_jac.Z);
    q_jac.is_infinity = 0;

    if (gid == 0) {
        fe_copy_to_global(&walkers[walker_idx].X, &q_jac.X);
        fe_copy_to_global(&walkers[walker_idx].Y, &q_jac.Y);
        fe_copy_to_global(&walkers[walker_idx].Z, &q_jac.Z);
        walkers[walker_idx].is_infinity = 0;
        fe_copy_to_global(&walker_aff_x[walker_idx], &q_jac.X);
        walker_dist[walker_idx] = 0;
    } else {
        pt_affine off;
        fe_copy_from_global(&off.x, &wild_offsets[gid].x);
        fe_copy_from_global(&off.y, &wild_offsets[gid].y);
        off.is_infinity = 0;

        pt_jacobian p;
        pt_add_mixed(&p, &q_jac, &off);

        pt_affine aff;
        pt_to_affine(&aff, &p);

        fe_copy_to_global(&walkers[walker_idx].X, &p.X);
        fe_copy_to_global(&walkers[walker_idx].Y, &p.Y);
        fe_copy_to_global(&walkers[walker_idx].Z, &p.Z);
        walkers[walker_idx].is_infinity = p.is_infinity;
        fe_copy_to_global(&walker_aff_x[walker_idx], &aff.x);
        walker_dist[walker_idx] = wild_offset_dists[gid];
    }
}

