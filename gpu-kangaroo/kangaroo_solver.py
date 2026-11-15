"""
kangaroo_solver.py
Phase 3 & 4: Production GPU-Accelerated Bounded Discrete Logarithm Solver (Pollard's Kangaroo)
Native AMD OpenCL (gfx90c / RDNA / Vega) implementation featuring:
- Mixed Affine-Jacobian Addition Walks (7M + 4S)
- Canonical Affine-Mapped Jump Determinism (x & 31)
- Decoupled Per-Step Affine Normalization & Atomic DP Trapping
- Uniform Tame Partitioning across Search Intervals
- Host Collision Resolution Table with Instant Scalar Extraction & Curve Verification
"""
from __future__ import annotations
import ctypes
from ctypes import (
    c_uint32, c_uint64, c_int32, c_void_p, c_size_t, c_char_p,
    byref, POINTER, Structure, sizeof, create_string_buffer
)
import time, os, sys, random, math
from dataclasses import dataclass, field

@dataclass
class KangarooResult:
    recovered_scalar: int
    verified: bool
    total_steps: int
    num_dps: int
    num_rounds: int
    total_time: float
    throughput_kadds: float
    timing: dict[str, float] = field(default_factory=dict)


# ==========================================
# secp256k1 Curve Constants
# ==========================================
P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
Gx = 0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798
Gy = 0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8
G = (Gx, Gy)

def point_add_ref(p1: tuple[int, int] | None, p2: tuple[int, int] | None) -> tuple[int, int] | None:
    if p1 is None: return p2
    if p2 is None: return p1
    x1, y1 = p1
    x2, y2 = p2
    if x1 == x2:
        if (y1 + y2) % P == 0: return None
        lam = (3 * x1 * x1 * pow(2 * y1, -1, P)) % P
    else:
        lam = ((y2 - y1) * pow(x2 - x1, -1, P)) % P
    x3 = (lam * lam - x1 - x2) % P
    y3 = (lam * (x1 - x3) - y1) % P
    return (x3, y3)

def scalar_mult_ref(k: int, pt: tuple[int, int] = (Gx, Gy)) -> tuple[int, int] | None:
    if k == 0 or pt is None: return None
    res = None
    addend = pt
    while k > 0:
        if k & 1: res = point_add_ref(res, addend)
        addend = point_add_ref(addend, addend)
        k >>= 1
    return res

# ==========================================
# CTypes Structures for OpenCL
# ==========================================
class FE256(Structure):
    _fields_ = [("v", c_uint32 * 8)]

class PtAffine(Structure):
    _fields_ = [
        ("x", FE256),
        ("y", FE256),
        ("is_infinity", c_int32)
    ]

class PtJacobian(Structure):
    _fields_ = [
        ("X", FE256),
        ("Y", FE256),
        ("Z", FE256),
        ("is_infinity", c_int32)
    ]

class DPRecord(Structure):
    _fields_ = [
        ("x", FE256),
        ("y", FE256),
        ("distance", c_uint64),
        ("is_tame", c_uint32),
        ("walker_id", c_uint32)
    ]

def int_to_fe256(val: int) -> FE256:
    fe = FE256()
    for i in range(8):
        fe.v[i] = (val >> (i * 32)) & 0xFFFFFFFF
    return fe

def fe256_to_int(fe: FE256) -> int:
    val = 0
    for i in range(8):
        val |= (int(fe.v[i]) << (i * 32))
    return val

# ==========================================
# OpenCL Context & Engine Wrapper
# ==========================================
class OpenCLKangarooEngine:
    def __init__(self):
        self.cl = ctypes.windll.LoadLibrary("OpenCL.dll")
        self._init_signatures()

        num_plat = c_uint32()
        self.cl.clGetPlatformIDs(0, None, byref(num_plat))
        plats = (c_void_p * num_plat.value)()
        self.cl.clGetPlatformIDs(num_plat.value, plats, None)
        plat = plats[0]

        num_dev = c_uint32()
        self.cl.clGetDeviceIDs(plat, 0xFFFFFFFF, 0, None, byref(num_dev))
        devs = (c_void_p * num_dev.value)()
        self.cl.clGetDeviceIDs(plat, 0xFFFFFFFF, num_dev.value, devs, None)
        self.device = devs[0]

        err = c_int32()
        self.ctx = self.cl.clCreateContext(None, 1, devs, None, None, byref(err))
        self.queue = self.cl.clCreateCommandQueue(self.ctx, self.device, 0, byref(err))

        cl_path = os.path.join(os.path.dirname(__file__), "secp256k1_kangaroo.cl")
        with open(cl_path, "r") as f:
            src = f.read()

        src_bytes = src.encode("utf-8")
        src_len = c_size_t(len(src_bytes))
        src_ptr = c_char_p(src_bytes)

        prog = self.cl.clCreateProgramWithSource(self.ctx, 1, byref(src_ptr), byref(src_len), byref(err))
        build_err = self.cl.clBuildProgram(prog, 1, devs, b"-cl-std=CL2.0", None, None)
        if build_err != 0:
            log_size = c_size_t()
            self.cl.clGetProgramBuildInfo(prog, self.device, 0x1183, 0, None, byref(log_size))
            log_buf = create_string_buffer(log_size.value)
            self.cl.clGetProgramBuildInfo(prog, self.device, 0x1183, log_size.value, log_buf, None)
            raise RuntimeError(f"OpenCL build failed:\n{log_buf.value.decode()}")

        self.prog = prog
        self.k_step = self.cl.clCreateKernel(prog, b"kangaroo_step_pure", byref(err))
        if err.value != 0: raise RuntimeError(f"Failed to create step kernel: {err.value}")

        self.k_norm = self.cl.clCreateKernel(prog, b"kangaroo_norm_and_dp", byref(err))
        if err.value != 0: raise RuntimeError(f"Failed to create norm kernel: {err.value}")

        self.k_init_wild = self.cl.clCreateKernel(prog, b"kangaroo_init_wild", byref(err))
        if err.value != 0: raise RuntimeError(f"Failed to create init_wild kernel: {err.value}")

    def _init_signatures(self):
        self.cl.clGetPlatformIDs.argtypes = [c_uint32, POINTER(c_void_p), POINTER(c_uint32)]
        self.cl.clGetDeviceIDs.argtypes = [c_void_p, c_uint64, c_uint32, POINTER(c_void_p), POINTER(c_uint32)]
        self.cl.clCreateContext.argtypes = [POINTER(c_void_p), c_uint32, POINTER(c_void_p), c_void_p, c_void_p, POINTER(c_int32)]
        self.cl.clCreateContext.restype = c_void_p
        self.cl.clCreateCommandQueue.argtypes = [c_void_p, c_void_p, c_uint64, POINTER(c_int32)]
        self.cl.clCreateCommandQueue.restype = c_void_p
        self.cl.clCreateProgramWithSource.argtypes = [c_void_p, c_uint32, POINTER(c_char_p), POINTER(c_size_t), POINTER(c_int32)]
        self.cl.clCreateProgramWithSource.restype = c_void_p
        self.cl.clBuildProgram.argtypes = [c_void_p, c_uint32, POINTER(c_void_p), c_char_p, c_void_p, c_void_p]
        self.cl.clGetProgramBuildInfo.argtypes = [c_void_p, c_void_p, c_uint32, c_size_t, c_void_p, POINTER(c_size_t)]
        self.cl.clGetProgramInfo.argtypes = [c_void_p, c_uint32, c_size_t, c_void_p, POINTER(c_size_t)]

        self.cl.clCreateKernel.argtypes = [c_void_p, c_char_p, POINTER(c_int32)]
        self.cl.clCreateKernel.restype = c_void_p
        self.cl.clCreateBuffer.argtypes = [c_void_p, c_uint64, c_size_t, c_void_p, POINTER(c_int32)]
        self.cl.clCreateBuffer.restype = c_void_p
        self.cl.clEnqueueWriteBuffer.argtypes = [c_void_p, c_void_p, c_uint32, c_size_t, c_size_t, c_void_p, c_uint32, POINTER(c_void_p), POINTER(c_void_p)]
        self.cl.clEnqueueReadBuffer.argtypes = [c_void_p, c_void_p, c_uint32, c_size_t, c_size_t, c_void_p, c_uint32, POINTER(c_void_p), POINTER(c_void_p)]
        self.cl.clEnqueueCopyBuffer.argtypes = [c_void_p, c_void_p, c_void_p, c_size_t, c_size_t, c_size_t, c_uint32, POINTER(c_void_p), POINTER(c_void_p)]
        self.cl.clSetKernelArg.argtypes = [c_void_p, c_uint32, c_size_t, c_void_p]
        self.cl.clEnqueueNDRangeKernel.argtypes = [c_void_p, c_void_p, c_uint32, POINTER(c_size_t), POINTER(c_size_t), POINTER(c_size_t), c_uint32, POINTER(c_void_p), POINTER(c_void_p)]
        self.cl.clFinish.argtypes = [c_void_p]
        self.cl.clReleaseMemObject.argtypes = [c_void_p]
        self.cl.clReleaseMemObject.restype = c_int32


    def create_buffer(self, flags, size):
        err = c_int32()
        buf = self.cl.clCreateBuffer(self.ctx, flags, size, None, byref(err))
        if err.value != 0: raise RuntimeError(f"clCreateBuffer error: {err.value}")
        return buf

    def release_buffer(self, buf):
        if buf:
            self.cl.clReleaseMemObject(buf)

    def set_arg(self, k, idx, size, val):
        self.cl.clSetKernelArg(k, idx, size, byref(val))


# ==========================================
# Bounded Kangaroo Solver
# ==========================================
def solve_bounded_dlp(
    engine: OpenCLKangarooEngine,
    target_pubkey: tuple[int, int],
    interval_min: int = 0,
    interval_max: int = 1 << 24,
    num_walkers: int = 1792,
    tame_ratio: float = 0.25,
    dp_bits: int | None = None,
    batch_dispatch_steps: int = 20,
    max_rounds: int = 2000,
    verbose: bool = True,
    return_stats: bool = False
) -> int | KangarooResult:
    """
    Solves target_pubkey = k * G where k in [interval_min, interval_max].
    Returns the secret scalar k or KangarooResult.
    """
    t_start = time.perf_counter()
    t_setup_start = time.perf_counter()

    W = interval_max - interval_min
    if W <= 0: raise ValueError("Invalid interval bounds")

    sqrt_w = max(1, int(math.isqrt(W)))
    mean_jump = max(8, sqrt_w // 4)

    # Automatic DP bits selection if not specified
    if dp_bits is None:
        dp_bits = max(3, min(14, int(math.log2(max(16, sqrt_w // (num_walkers // 8 + 1))))))
    dp_mask = (1 << dp_bits) - 1

    if verbose:
        print(f"\n[Kangaroo] Solving DLP on interval [{hex(interval_min)}, {hex(interval_max)}]")
        print(f"[Kangaroo] Interval width W = {W:,} (2^{math.log2(W):.2f}) | Mean jump: {mean_jump:,}")
        print(f"[Kangaroo] Walkers: {num_walkers} (Tame: {int(num_walkers * tame_ratio)}, Wild: {num_walkers - int(num_walkers * tame_ratio)}) | DP bits: {dp_bits}")

    # Generate 32 pseudorandom jumps
    random.seed(1337)
    jump_distances = []
    for _ in range(32):
        d = random.randint(max(1, mean_jump // 2), max(2, mean_jump * 3 // 2))
        jump_distances.append(d)
    jump_pts = [scalar_mult_ref(d, G) for d in jump_distances]

    jump_table_arr = (PtAffine * 32)()
    jump_dist_arr = (c_uint64 * 32)()
    for i in range(32):
        jump_table_arr[i].x = int_to_fe256(jump_pts[i][0])
        jump_table_arr[i].y = int_to_fe256(jump_pts[i][1])
        jump_table_arr[i].is_infinity = 0
        jump_dist_arr[i] = jump_distances[i]

    # Initialize Walkers
    num_tame = int(num_walkers * tame_ratio)
    num_wild = num_walkers - num_tame

    walkers_jac = (PtJacobian * num_walkers)()
    walkers_aff_x = (FE256 * num_walkers)()
    walkers_dist = (c_uint64 * num_walkers)()
    walkers_tame = (c_uint32 * num_walkers)()

    # Tame herd: distributed uniformly across search interval
    tame_step = max(1, W // num_tame)
    tame_step_pt = scalar_mult_ref(tame_step, G)
    curr_tame_s = interval_min + 1
    curr_tame_pt = scalar_mult_ref(curr_tame_s, G)

    for i in range(num_tame):
        walkers_jac[i].X = int_to_fe256(curr_tame_pt[0])
        walkers_jac[i].Y = int_to_fe256(curr_tame_pt[1])
        walkers_jac[i].Z = int_to_fe256(1)
        walkers_jac[i].is_infinity = 0
        walkers_aff_x[i] = int_to_fe256(curr_tame_pt[0])
        walkers_dist[i] = curr_tame_s
        walkers_tame[i] = 1

        curr_tame_s += tame_step
        curr_tame_pt = point_add_ref(curr_tame_pt, tame_step_pt)

    # Wild herd: centered at target_pubkey + incremental offsets
    wild_step = mean_jump * 2
    wild_step_pt = scalar_mult_ref(wild_step, G)
    curr_wild_pt = target_pubkey
    curr_wild_dist = 0

    for i in range(num_tame, num_walkers):
        walkers_jac[i].X = int_to_fe256(curr_wild_pt[0])
        walkers_jac[i].Y = int_to_fe256(curr_wild_pt[1])
        walkers_jac[i].Z = int_to_fe256(1)
        walkers_jac[i].is_infinity = 0
        walkers_aff_x[i] = int_to_fe256(curr_wild_pt[0])
        walkers_dist[i] = curr_wild_dist
        walkers_tame[i] = 0

        curr_wild_dist += wild_step
        curr_wild_pt = point_add_ref(curr_wild_pt, wild_step_pt)


    t_setup = time.perf_counter() - t_setup_start

    # Create buffers & transfer initial state to device
    t_h2d_start = time.perf_counter()
    buf_jumps = engine.create_buffer(4, sizeof(PtAffine) * 32)
    buf_dists = engine.create_buffer(4, sizeof(c_uint64) * 32)
    engine.cl.clEnqueueWriteBuffer(engine.queue, buf_jumps, 1, 0, sizeof(PtAffine) * 32, jump_table_arr, 0, None, None)
    engine.cl.clEnqueueWriteBuffer(engine.queue, buf_dists, 1, 0, sizeof(c_uint64) * 32, jump_dist_arr, 0, None, None)

    buf_w_jac = engine.create_buffer(1, sizeof(PtJacobian) * num_walkers)
    buf_w_aff_x = engine.create_buffer(1, sizeof(FE256) * num_walkers)
    buf_w_dist = engine.create_buffer(1, sizeof(c_uint64) * num_walkers)
    buf_w_tame = engine.create_buffer(1, sizeof(c_uint32) * num_walkers)

    MAX_DPS = 32768
    buf_dp = engine.create_buffer(1, sizeof(DPRecord) * MAX_DPS)
    buf_dp_cnt = engine.create_buffer(1, sizeof(c_uint32))

    engine.cl.clEnqueueWriteBuffer(engine.queue, buf_w_jac, 1, 0, sizeof(PtJacobian) * num_walkers, walkers_jac, 0, None, None)
    engine.cl.clEnqueueWriteBuffer(engine.queue, buf_w_aff_x, 1, 0, sizeof(FE256) * num_walkers, walkers_aff_x, 0, None, None)
    engine.cl.clEnqueueWriteBuffer(engine.queue, buf_w_dist, 1, 0, sizeof(c_uint64) * num_walkers, walkers_dist, 0, None, None)
    engine.cl.clEnqueueWriteBuffer(engine.queue, buf_w_tame, 1, 0, sizeof(c_uint32) * num_walkers, walkers_tame, 0, None, None)
    t_h2d = time.perf_counter() - t_h2d_start

    # Set kernel arguments
    engine.set_arg(engine.k_step, 0, sizeof(c_void_p), c_void_p(buf_w_jac))
    engine.set_arg(engine.k_step, 1, sizeof(c_void_p), c_void_p(buf_w_aff_x))
    engine.set_arg(engine.k_step, 2, sizeof(c_void_p), c_void_p(buf_w_dist))
    engine.set_arg(engine.k_step, 3, sizeof(c_void_p), c_void_p(buf_jumps))
    engine.set_arg(engine.k_step, 4, sizeof(c_void_p), c_void_p(buf_dists))
    engine.set_arg(engine.k_step, 5, sizeof(c_uint32), c_uint32(num_walkers))

    engine.set_arg(engine.k_norm, 0, sizeof(c_void_p), c_void_p(buf_w_jac))
    engine.set_arg(engine.k_norm, 1, sizeof(c_void_p), c_void_p(buf_w_aff_x))
    engine.set_arg(engine.k_norm, 2, sizeof(c_void_p), c_void_p(buf_w_dist))
    engine.set_arg(engine.k_norm, 3, sizeof(c_void_p), c_void_p(buf_w_tame))
    engine.set_arg(engine.k_norm, 4, sizeof(c_void_p), c_void_p(buf_dp))
    engine.set_arg(engine.k_norm, 5, sizeof(c_void_p), c_void_p(buf_dp_cnt))
    engine.set_arg(engine.k_norm, 6, sizeof(c_uint32), c_uint32(MAX_DPS))
    engine.set_arg(engine.k_norm, 7, sizeof(c_uint32), c_uint32(dp_mask))
    engine.set_arg(engine.k_norm, 8, sizeof(c_uint32), c_uint32(num_walkers))

    gw = (c_size_t * 1)(num_walkers)
    lw = (c_size_t * 1)(64)

    dp_table: dict[int, tuple[int, int]] = {}
    total_steps = 0
    zero_cnt = c_uint32(0)
    cnt_val = c_uint32(0)
    read_dps = (DPRecord * MAX_DPS)()

    t_gpu_total = 0.0
    t_d2h_total = 0.0
    t_host_dp_total = 0.0
    t_verify_total = 0.0

    round_num = 0
    try:
        while round_num < max_rounds:
            round_num += 1
            t_h2d_sub = time.perf_counter()
            engine.cl.clEnqueueWriteBuffer(engine.queue, buf_dp_cnt, 1, 0, sizeof(c_uint32), byref(zero_cnt), 0, None, None)
            t_h2d += (time.perf_counter() - t_h2d_sub)

            t_gpu_sub = time.perf_counter()
            for _ in range(batch_dispatch_steps):
                engine.cl.clEnqueueNDRangeKernel(engine.queue, engine.k_step, 1, None, gw, lw, 0, None, None)
                engine.cl.clEnqueueNDRangeKernel(engine.queue, engine.k_norm, 1, None, gw, lw, 0, None, None)
            engine.cl.clFinish(engine.queue)
            t_gpu_total += (time.perf_counter() - t_gpu_sub)

            total_steps += num_walkers * batch_dispatch_steps

            t_d2h_sub = time.perf_counter()
            engine.cl.clEnqueueReadBuffer(engine.queue, buf_dp_cnt, 1, 0, sizeof(c_uint32), byref(cnt_val), 0, None, None)
            num_dps = min(cnt_val.value, MAX_DPS)

            if num_dps > 0:
                engine.cl.clEnqueueReadBuffer(engine.queue, buf_dp, 1, 0, sizeof(DPRecord) * num_dps, read_dps, 0, None, None)
            t_d2h_total += (time.perf_counter() - t_d2h_sub)

            if num_dps > 0:
                t_host_sub = time.perf_counter()
                for i in range(num_dps):
                    rec = read_dps[i]
                    rx = fe256_to_int(rec.x)
                    rdist = int(rec.distance)
                    rtame = int(rec.is_tame)

                    if rx in dp_table:
                        prev_tame, prev_dist = dp_table[rx]
                        if prev_tame != rtame:
                            if prev_tame == 1:
                                d_tame, d_wild = prev_dist, rdist
                            else:
                                d_tame, d_wild = rdist, prev_dist
                            k_candidate = (d_tame - d_wild) % N
                            t_host_dp_total += (time.perf_counter() - t_host_sub)

                            t_ver_sub = time.perf_counter()
                            is_match = (scalar_mult_ref(k_candidate, G) == target_pubkey)
                            t_verify_total += (time.perf_counter() - t_ver_sub)

                            if is_match:
                                elapsed = time.perf_counter() - t_start
                                rate = (total_steps / elapsed) / 1e3 if elapsed > 0 else 0.0
                                if verbose:
                                    print("\n" + "="*70)
                                    print("SUCCESS: COLLISION DETECTED & PRIVATE KEY RECONSTRUCTED!")
                                    print("="*70)
                                    print(f"Secret Key (k):      {hex(k_candidate)} ({k_candidate})")
                                    print(f"Interval Bounds:     [{hex(interval_min)}, {hex(interval_max)}]")
                                    print(f"Total Steps:         {total_steps:,} across {num_walkers} walkers")
                                    print(f"Distinct DPs Stored: {len(dp_table):,}")
                                    print(f"Elapsed Time:        {elapsed:.3f} s ({rate:.2f} kAdds/s sustained)")
                                    print(f"Public Key Match:    100% Verified!")
                                    print("="*70)
                                res = KangarooResult(
                                    recovered_scalar=k_candidate,
                                    verified=True,
                                    total_steps=total_steps,
                                    num_dps=len(dp_table),
                                    num_rounds=round_num,
                                    total_time=elapsed,
                                    throughput_kadds=rate,
                                    timing={
                                        "setup": t_setup,
                                        "h2d": t_h2d,
                                        "gpu_kernel": t_gpu_total,
                                        "d2h": t_d2h_total,
                                        "host_dp": t_host_dp_total,
                                        "verify": t_verify_total,
                                    }
                                )
                                return res if return_stats else k_candidate
                            t_host_sub = time.perf_counter()
                    else:
                        dp_table[rx] = (rtame, rdist)
                t_host_dp_total += (time.perf_counter() - t_host_sub)

            if verbose and (round_num % 5 == 0):
                elapsed = time.perf_counter() - t_start
                rate = (total_steps / elapsed) / 1e3 if elapsed > 0 else 0.0
                print(f"  Round {round_num:3d} | Steps: {total_steps:8,d} | DPs stored: {len(dp_table):6,d} | Rate: {rate:5.1f} kAdds/s", end="\r")

        raise RuntimeError("Search exceeded max rounds without finding collision")
    finally:
        engine.release_buffer(buf_jumps)
        engine.release_buffer(buf_dists)
        engine.release_buffer(buf_w_jac)
        engine.release_buffer(buf_w_aff_x)
        engine.release_buffer(buf_w_dist)
        engine.release_buffer(buf_w_tame)
        engine.release_buffer(buf_dp)
        engine.release_buffer(buf_dp_cnt)


if __name__ == "__main__":
    print("="*70)
    print("POLLARD'S KANGAROO secp256k1 GPU SOLVER SUITE")
    print("="*70)
    engine = OpenCLKangarooEngine()

    test_cases = [
        ("W = 2^16 (65,536)", 65536, 4),
        ("W = 2^20 (1,048,576)", 1048576, 5),
        ("W = 2^24 (16,777,216)", 16777216, 6),
        ("W = 2^28 (268,435,456)", 268435456, 7),
        ("W = 2^32 (4,294,967,296)", 4294967296, 8),
    ]

    for label, W, dp_bits in test_cases:
        print(f"\n--- Benchmark Challenge: {label} ---")
        secret_k = random.randint(1, W - 1)
        target_Q = scalar_mult_ref(secret_k, G)
        print(f"Target Secret Scalar: {hex(secret_k)} ({secret_k})")
        print(f"Target Public Key:    ({hex(target_Q[0])[:18]}..., {hex(target_Q[1])[:18]}...)")

        found_k = solve_bounded_dlp(
            engine,
            target_pubkey=target_Q,
            interval_min=0,
            interval_max=W,
            num_walkers=896,
            dp_bits=dp_bits
        )
        assert found_k == secret_k, f"Verification failed! Expected {secret_k}, got {found_k}"
        print(f"[PASS] {label} solved & verified mathematically on GPU!")
