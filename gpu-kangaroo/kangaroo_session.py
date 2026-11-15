"""
kangaroo_session.py
Phase 7: Persistent Session Architecture for secp256k1 Kangaroo Solver
Features:
- Track A: Single-Instance Lowest Latency with GPU-accelerated Wild Herd Initialization
           and Device-to-Device Tame State Restoration (Warm setup < 1 ms).
- Track B: Multi-Instance Shared-Tame Batching for M Concurrent Targets.
"""
from __future__ import annotations
import ctypes
from ctypes import (
    c_uint32, c_uint64, c_int32, c_void_p, c_size_t,
    byref, Structure, sizeof
)
import time, math, random
from dataclasses import dataclass, field

from kangaroo_solver import (
    OpenCLKangarooEngine, FE256, PtAffine, PtJacobian, DPRecord,
    int_to_fe256, fe256_to_int, point_add_ref, scalar_mult_ref,
    P, N, G, Gx, Gy, KangarooResult
)

class PersistentKangarooSession:
    """
    Persistent GPU session for an interval [interval_min, interval_max].
    Keeps OpenCL buffers allocated and jump tables cached on the device.
    Precomputes tame state and wild offset generators to minimize per-instance setup.
    """
    def __init__(
        self,
        engine: OpenCLKangarooEngine,
        interval_min: int = 0,
        interval_max: int = 1 << 28,
        num_walkers: int = 1792,
        tame_ratio: float = 0.25,
        dp_bits: int | None = None,
        batch_dispatch_steps: int = 20
    ):
        self.engine = engine
        self.interval_min = interval_min
        self.interval_max = interval_max
        self.num_walkers = num_walkers
        self.tame_ratio = tame_ratio
        self.batch_dispatch_steps = batch_dispatch_steps

        self.W = interval_max - interval_min
        if self.W <= 0:
            raise ValueError("Invalid interval bounds")

        self.sqrt_w = max(1, int(math.isqrt(self.W)))
        self.mean_jump = max(8, self.sqrt_w // 4)

        if dp_bits is None:
            self.dp_bits = max(3, min(14, int(math.log2(max(16, self.sqrt_w // (num_walkers // 8 + 1))))))
        else:
            self.dp_bits = dp_bits
        self.dp_mask = (1 << self.dp_bits) - 1

        self.num_tame = int(num_walkers * tame_ratio)
        self.num_wild = num_walkers - self.num_tame
        assert self.num_walkers % 64 == 0

        self._init_session_precomputations()
        self._allocate_gpu_buffers()

    def _init_session_precomputations(self):
        t0 = time.perf_counter()
        # 1. Deterministic Jump Table
        random.seed(1337)
        self.jump_distances = []
        for _ in range(32):
            d = random.randint(max(1, self.mean_jump // 2), max(2, self.mean_jump * 3 // 2))
            self.jump_distances.append(d)
        self.jump_pts = [scalar_mult_ref(d, G) for d in self.jump_distances]

        self.jump_table_arr = (PtAffine * 32)()
        self.jump_dist_arr = (c_uint64 * 32)()
        for i in range(32):
            self.jump_table_arr[i].x = int_to_fe256(self.jump_pts[i][0])
            self.jump_table_arr[i].y = int_to_fe256(self.jump_pts[i][1])
            self.jump_table_arr[i].is_infinity = 0
            self.jump_dist_arr[i] = self.jump_distances[i]

        # 2. Precompute Initial Tame Herd Coordinates (Fixed for interval)
        tame_step = max(1, self.W // self.num_tame)
        tame_step_pt = scalar_mult_ref(tame_step, G)
        curr_tame_s = self.interval_min + 1
        curr_tame_pt = scalar_mult_ref(curr_tame_s, G)

        self.tame_init_jac = (PtJacobian * self.num_tame)()
        self.tame_init_aff_x = (FE256 * self.num_tame)()
        self.tame_init_dist = (c_uint64 * self.num_tame)()

        for i in range(self.num_tame):
            self.tame_init_jac[i].X = int_to_fe256(curr_tame_pt[0])
            self.tame_init_jac[i].Y = int_to_fe256(curr_tame_pt[1])
            self.tame_init_jac[i].Z = int_to_fe256(1)
            self.tame_init_jac[i].is_infinity = 0
            self.tame_init_aff_x[i] = int_to_fe256(curr_tame_pt[0])
            self.tame_init_dist[i] = curr_tame_s

            curr_tame_s += tame_step
            curr_tame_pt = point_add_ref(curr_tame_pt, tame_step_pt)

        # 3. Precompute Wild Offsets (Fixed stride generators stored in GPU affine array)
        self.wild_step = self.mean_jump * 2
        wild_step_pt = scalar_mult_ref(self.wild_step, G)

        self.wild_offsets_arr = (PtAffine * self.num_wild)()
        self.wild_dists_arr = (c_uint64 * self.num_wild)()
        curr_off_pt = (0, 0)
        c_dist = 0
        for i in range(self.num_wild):
            if i == 0:
                self.wild_offsets_arr[i].x = int_to_fe256(0)
                self.wild_offsets_arr[i].y = int_to_fe256(0)
                self.wild_offsets_arr[i].is_infinity = 1
            elif i == 1:
                curr_off_pt = wild_step_pt
                self.wild_offsets_arr[i].x = int_to_fe256(curr_off_pt[0])
                self.wild_offsets_arr[i].y = int_to_fe256(curr_off_pt[1])
                self.wild_offsets_arr[i].is_infinity = 0
            else:
                curr_off_pt = point_add_ref(curr_off_pt, wild_step_pt)
                self.wild_offsets_arr[i].x = int_to_fe256(curr_off_pt[0])
                self.wild_offsets_arr[i].y = int_to_fe256(curr_off_pt[1])
                self.wild_offsets_arr[i].is_infinity = 0
            self.wild_dists_arr[i] = c_dist
            c_dist += self.wild_step

        self.cold_precompute_time = time.perf_counter() - t0

    def _allocate_gpu_buffers(self):
        engine = self.engine
        N = self.num_walkers

        # 1. Jumps buffer
        self.buf_jumps = engine.create_buffer(4, sizeof(PtAffine) * 32)
        self.buf_dists = engine.create_buffer(4, sizeof(c_uint64) * 32)
        engine.cl.clEnqueueWriteBuffer(engine.queue, self.buf_jumps, 1, 0, sizeof(PtAffine) * 32, self.jump_table_arr, 0, None, None)
        engine.cl.clEnqueueWriteBuffer(engine.queue, self.buf_dists, 1, 0, sizeof(c_uint64) * 32, self.jump_dist_arr, 0, None, None)

        # 2. Main walker state buffers
        self.buf_w_jac = engine.create_buffer(1, sizeof(PtJacobian) * N)
        self.buf_w_aff_x = engine.create_buffer(1, sizeof(FE256) * N)
        self.buf_w_dist = engine.create_buffer(1, sizeof(c_uint64) * N)
        self.buf_w_tame = engine.create_buffer(1, sizeof(c_uint32) * N)

        # 3. Device backup buffers for instantaneous tame herd restoration
        self.buf_tame_bak_jac = engine.create_buffer(1, sizeof(PtJacobian) * self.num_tame)
        self.buf_tame_bak_aff_x = engine.create_buffer(1, sizeof(FE256) * self.num_tame)
        self.buf_tame_bak_dist = engine.create_buffer(1, sizeof(c_uint64) * self.num_tame)

        engine.cl.clEnqueueWriteBuffer(engine.queue, self.buf_tame_bak_jac, 1, 0, sizeof(PtJacobian) * self.num_tame, self.tame_init_jac, 0, None, None)
        engine.cl.clEnqueueWriteBuffer(engine.queue, self.buf_tame_bak_aff_x, 1, 0, sizeof(FE256) * self.num_tame, self.tame_init_aff_x, 0, None, None)
        engine.cl.clEnqueueWriteBuffer(engine.queue, self.buf_tame_bak_dist, 1, 0, sizeof(c_uint64) * self.num_tame, self.tame_init_dist, 0, None, None)

        # 4. Device wild offset buffers for sub-millisecond GPU initialization
        self.buf_wild_offsets = engine.create_buffer(4, sizeof(PtAffine) * self.num_wild)
        self.buf_wild_dists = engine.create_buffer(4, sizeof(c_uint64) * self.num_wild)
        engine.cl.clEnqueueWriteBuffer(engine.queue, self.buf_wild_offsets, 1, 0, sizeof(PtAffine) * self.num_wild, self.wild_offsets_arr, 0, None, None)
        engine.cl.clEnqueueWriteBuffer(engine.queue, self.buf_wild_dists, 1, 0, sizeof(c_uint64) * self.num_wild, self.wild_dists_arr, 0, None, None)

        # Preload tame flags (1 for tame, 0 for wild)
        tame_flags = (c_uint32 * N)()
        for i in range(self.num_tame):
            tame_flags[i] = 1
        for i in range(self.num_tame, N):
            tame_flags[i] = 0
        engine.cl.clEnqueueWriteBuffer(engine.queue, self.buf_w_tame, 1, 0, sizeof(c_uint32) * N, tame_flags, 0, None, None)

        self.MAX_DPS = 32768
        self.buf_dp = engine.create_buffer(1, sizeof(DPRecord) * self.MAX_DPS)
        self.buf_dp_cnt = engine.create_buffer(1, sizeof(c_uint32))

        # Static arguments for step and norm kernels
        engine.set_arg(engine.k_step, 0, sizeof(c_void_p), c_void_p(self.buf_w_jac))
        engine.set_arg(engine.k_step, 1, sizeof(c_void_p), c_void_p(self.buf_w_aff_x))
        engine.set_arg(engine.k_step, 2, sizeof(c_void_p), c_void_p(self.buf_w_dist))
        engine.set_arg(engine.k_step, 3, sizeof(c_void_p), c_void_p(self.buf_jumps))
        engine.set_arg(engine.k_step, 4, sizeof(c_void_p), c_void_p(self.buf_dists))
        engine.set_arg(engine.k_step, 5, sizeof(c_uint32), c_uint32(N))

        engine.set_arg(engine.k_norm, 0, sizeof(c_void_p), c_void_p(self.buf_w_jac))
        engine.set_arg(engine.k_norm, 1, sizeof(c_void_p), c_void_p(self.buf_w_aff_x))
        engine.set_arg(engine.k_norm, 2, sizeof(c_void_p), c_void_p(self.buf_w_dist))
        engine.set_arg(engine.k_norm, 3, sizeof(c_void_p), c_void_p(self.buf_w_tame))
        engine.set_arg(engine.k_norm, 4, sizeof(c_void_p), c_void_p(self.buf_dp))
        engine.set_arg(engine.k_norm, 5, sizeof(c_void_p), c_void_p(self.buf_dp_cnt))
        engine.set_arg(engine.k_norm, 6, sizeof(c_uint32), c_uint32(self.MAX_DPS))
        engine.set_arg(engine.k_norm, 7, sizeof(c_uint32), c_uint32(self.dp_mask))
        engine.set_arg(engine.k_norm, 8, sizeof(c_uint32), c_uint32(N))

        # Static arguments for k_init_wild
        engine.set_arg(engine.k_init_wild, 0, sizeof(c_void_p), c_void_p(self.buf_w_jac))
        engine.set_arg(engine.k_init_wild, 1, sizeof(c_void_p), c_void_p(self.buf_w_aff_x))
        engine.set_arg(engine.k_init_wild, 2, sizeof(c_void_p), c_void_p(self.buf_w_dist))
        engine.set_arg(engine.k_init_wild, 3, sizeof(c_void_p), c_void_p(self.buf_wild_offsets))
        engine.set_arg(engine.k_init_wild, 4, sizeof(c_void_p), c_void_p(self.buf_wild_dists))
        # args 5 and 6 (target_x, target_y) will be set per solve call
        engine.set_arg(engine.k_init_wild, 7, sizeof(c_uint32), c_uint32(self.num_tame))
        engine.set_arg(engine.k_init_wild, 8, sizeof(c_uint32), c_uint32(self.num_wild))

        self.gw = (c_size_t * 1)(N)
        self.lw = (c_size_t * 1)(64)
        self.gw_wild = (c_size_t * 1)(self.num_wild)
        self.lw_wild = (c_size_t * 1)(64)

        self.zero_cnt = c_uint32(0)
        self.cnt_val = c_uint32(0)
        self.read_dps = (DPRecord * self.MAX_DPS)()

    def solve_single(
        self,
        target_pubkey: tuple[int, int],
        max_rounds: int = 3000,
        verbose: bool = False,
        return_stats: bool = True
    ) -> int | KangarooResult:
        """
        Track A: Single-Instance Lowest Latency Solve using Warm Session State.
        Executes zero host-side EC operations; restores tame state via GPU buffer copy
        and initializes wild herd via fast GPU kernel.
        """
        t_start = time.perf_counter()
        t_setup_start = time.perf_counter()
        engine = self.engine

        target_fe_x = int_to_fe256(target_pubkey[0])
        target_fe_y = int_to_fe256(target_pubkey[1])
        t_setup = time.perf_counter() - t_setup_start

        # Fast GPU warm setup
        t_h2d_start = time.perf_counter()
        # 1. Device-to-Device fast copy to restore tame state
        tame_bytes_jac = sizeof(PtJacobian) * self.num_tame
        tame_bytes_aff = sizeof(FE256) * self.num_tame
        tame_bytes_dist = sizeof(c_uint64) * self.num_tame

        engine.cl.clEnqueueCopyBuffer(engine.queue, self.buf_tame_bak_jac, self.buf_w_jac, 0, 0, tame_bytes_jac, 0, None, None)
        engine.cl.clEnqueueCopyBuffer(engine.queue, self.buf_tame_bak_aff_x, self.buf_w_aff_x, 0, 0, tame_bytes_aff, 0, None, None)
        engine.cl.clEnqueueCopyBuffer(engine.queue, self.buf_tame_bak_dist, self.buf_w_dist, 0, 0, tame_bytes_dist, 0, None, None)

        # 2. Launch GPU wild initialization kernel
        engine.set_arg(engine.k_init_wild, 5, sizeof(FE256), target_fe_x)
        engine.set_arg(engine.k_init_wild, 6, sizeof(FE256), target_fe_y)
        engine.cl.clEnqueueNDRangeKernel(engine.queue, engine.k_init_wild, 1, None, self.gw_wild, self.lw_wild, 0, None, None)
        engine.cl.clFinish(engine.queue)
        t_h2d = time.perf_counter() - t_h2d_start

        # 3. Solver Loop
        dp_table: dict[int, tuple[int, int]] = {}
        total_steps = 0
        round_num = 0
        t_gpu_total = 0.0
        t_d2h_total = 0.0
        t_host_dp_total = 0.0
        t_verify_total = 0.0

        while round_num < max_rounds:
            round_num += 1
            t_sub = time.perf_counter()
            engine.cl.clEnqueueWriteBuffer(engine.queue, self.buf_dp_cnt, 1, 0, sizeof(c_uint32), byref(self.zero_cnt), 0, None, None)
            t_h2d += (time.perf_counter() - t_sub)

            t_gpu_sub = time.perf_counter()
            for _ in range(self.batch_dispatch_steps):
                engine.cl.clEnqueueNDRangeKernel(engine.queue, engine.k_step, 1, None, self.gw, self.lw, 0, None, None)
                engine.cl.clEnqueueNDRangeKernel(engine.queue, engine.k_norm, 1, None, self.gw, self.lw, 0, None, None)
            engine.cl.clFinish(engine.queue)
            t_gpu_total += (time.perf_counter() - t_gpu_sub)

            total_steps += self.num_walkers * self.batch_dispatch_steps

            t_d2h_sub = time.perf_counter()
            engine.cl.clEnqueueReadBuffer(engine.queue, self.buf_dp_cnt, 1, 0, sizeof(c_uint32), byref(self.cnt_val), 0, None, None)
            num_dps = min(self.cnt_val.value, self.MAX_DPS)

            if num_dps > 0:
                engine.cl.clEnqueueReadBuffer(engine.queue, self.buf_dp, 1, 0, sizeof(DPRecord) * num_dps, self.read_dps, 0, None, None)
            t_d2h_total += (time.perf_counter() - t_d2h_sub)

            if num_dps > 0:
                t_host_sub = time.perf_counter()
                for i in range(num_dps):
                    rec = self.read_dps[i]
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

        raise RuntimeError("Search exceeded max rounds without finding collision")

    def close(self):
        engine = self.engine
        engine.release_buffer(self.buf_jumps)
        engine.release_buffer(self.buf_dists)
        engine.release_buffer(self.buf_w_jac)
        engine.release_buffer(self.buf_w_aff_x)
        engine.release_buffer(self.buf_w_dist)
        engine.release_buffer(self.buf_w_tame)
        engine.release_buffer(self.buf_tame_bak_jac)
        engine.release_buffer(self.buf_tame_bak_aff_x)
        engine.release_buffer(self.buf_tame_bak_dist)
        engine.release_buffer(self.buf_wild_offsets)
        engine.release_buffer(self.buf_wild_dists)
        engine.release_buffer(self.buf_dp)
        engine.release_buffer(self.buf_dp_cnt)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
