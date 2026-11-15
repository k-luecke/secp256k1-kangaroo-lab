"""
solve_bitcoin_puzzle_series.py
Real-World Historical Targets: Bitcoin Puzzles #40, #41, #42
Executes Phase 8 Persistent Kangaroo Solver on actual historical Bitcoin puzzle challenges.
Verifies:
1. Public key Q hashes to published Bitcoin Address via Base58Check (SHA256 + RIPEMD160).
2. Phase 8 solver recovers scalar without prior knowledge of ground truth.
3. Recovered scalar k satisfies k * G == Q.
4. Derived address matches Bitcoin address.
5. Recovered scalar matches independently published historical solution.
"""
import sys, time, hashlib, math, json

from kangaroo_solver import OpenCLKangarooEngine, scalar_mult_ref, G
from kangaroo_session import PersistentKangarooSession

def base58_encode(b: bytes) -> str:
    alphabet = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
    n = int.from_bytes(b, 'big')
    chars = []
    while n > 0:
        n, r = divmod(n, 58)
        chars.append(alphabet[r])
    for byte in b:
        if byte == 0: chars.append('1')
        else: break
    return ''.join(reversed(chars))

def pubkey_to_address(pt: tuple[int, int], compressed: bool = True) -> str:
    x, y = pt
    if compressed:
        prefix = b'\x02' if y % 2 == 0 else b'\x03'
        pub_bytes = prefix + x.to_bytes(32, 'big')
    else:
        pub_bytes = b'\x04' + x.to_bytes(32, 'big') + y.to_bytes(32, 'big')
    s = hashlib.sha256(pub_bytes).digest()
    r = hashlib.new('ripemd160', s).digest()
    versioned = b'\x00' + r
    chk = hashlib.sha256(hashlib.sha256(versioned).digest()).digest()[:4]
    return base58_encode(versioned + chk)

PUZZLES = [
    {
        "puzzle_num": 40,
        "address": "1EeAxcprB2PpCnr34VfZdFrkUWuxyiNEFv",
        "interval_min": 1 << 39,
        "interval_max": 1 << 40,
        "Qx": 0xa2efa402fd5268400c77c20e574ba86409ededee7c4020e4b9f0edbee53de0d4,
        "Qy": 0x7ba1a987013e78aef5295bf842749bdf97e25336a82458bbaba8c00d16a79ea7,
        "ground_truth_hex": "e9ae4933d6",
        "dp_bits": 10
    },
    {
        "puzzle_num": 41,
        "address": "1L5sU9qvJeuwQUdt4y1eiLmquFxKjtHr3E",
        "interval_min": 1 << 40,
        "interval_max": 1 << 41,
        "Qx": 0xb357e68437da273dcf995a474a524439faad86fc9effc300183f714b0903468b,
        "Qy": 0x9a6435e99428f3ef51a405550940fc39ce67823cb8b35f7f4d829902974d0c65,
        "ground_truth_hex": "153869acc5b",
        "dp_bits": 10
    },
    {
        "puzzle_num": 42,
        "address": "1E32GPWgDyeyQac4aJxm9HVoLrrEYPnM4N",
        "interval_min": 1 << 41,
        "interval_max": 1 << 42,
        "Qx": 0xeec88385be9da803a0d6579798d977a5d0c7f80917dab49cb73c9e3927142cb6,
        "Qy": 0x28afea598588ea50a6b11e552f8574e0b93abd5595f5aa17ea3be5304103d255,
        "ground_truth_hex": "2a221c58d8f",
        "dp_bits": 10
    }
]

def solve_puzzle(engine: OpenCLKangarooEngine, puzzle_info: dict) -> dict:
    p_num = puzzle_info["puzzle_num"]
    addr = puzzle_info["address"]
    imin = puzzle_info["interval_min"]
    imax = puzzle_info["interval_max"]
    width = imax - imin
    sqrt_w = math.isqrt(width)
    Q = (puzzle_info["Qx"], puzzle_info["Qy"])
    ground_truth = int(puzzle_info["ground_truth_hex"], 16)
    dp_bits = puzzle_info["dp_bits"]

    print("\n" + "=" * 75)
    print(f"COMMENCING SOLVER RUN: BITCOIN PUZZLE #{p_num}")
    print("=" * 75)
    print(f"Target Bitcoin Address: {addr}")
    print(f"Search Interval:        [{hex(imin)}, {hex(imax - 1)}]")
    print(f"Interval Width:         {width:,} keys (2^{int(math.log2(width))}), sqrt(W) = {sqrt_w:,}")
    print(f"Target Pubkey Qx:       {hex(Q[0])}")
    print(f"Target Pubkey Qy:       {hex(Q[1])}")

    # Step 1: Verify Q hashes to published Bitcoin address
    check_addr = pubkey_to_address(Q, compressed=True)
    assert check_addr == addr, f"Input public key mismatch! {check_addr} != {addr}"
    print(f"[PRE-CHECK OK] Input public key Q strictly hashes to Bitcoin Address {addr}!")

    # Step 2: Initialize Session and execute search
    print(f"Initializing Persistent Kangaroo Session (dp_bits={dp_bits}, 25% tame / 75% wild)...")
    t0_session = time.perf_counter()
    with PersistentKangarooSession(
        engine,
        interval_min=imin,
        interval_max=imax,
        dp_bits=dp_bits,
        tame_ratio=0.25,
        batch_dispatch_steps=20
    ) as session:
        t_session = time.perf_counter() - t0_session
        print(f"Session ready in {t_session*1000:.1f} ms. Launching GPU solver loop...")

        t0_solve = time.perf_counter()
        res = session.solve_single(Q, max_rounds=6000, return_stats=True)
        t_solve = time.perf_counter() - t0_solve

    recovered_k = res.recovered_scalar
    c_factor = res.total_steps / sqrt_w

    print("\n>>> PUZZLE RECOVERED!")
    print(f"  Recovered Scalar (hex): {hex(recovered_k)}")
    print(f"  Recovered Scalar (dec): {recovered_k}")
    print(f"  Wall-Clock Solve Time:  {t_solve*1000:.1f} ms ({t_solve:.3f} s)")
    print(f"  Total Group Operations: {res.total_steps:,} point additions")
    print(f"  Work Factor (c):        {c_factor:.2f} * sqrt(W)")
    print(f"  Arithmetic Rate:        {res.throughput_kadds:.1f} kAdds/s ({res.throughput_kadds/1000:.2f} MAdds/s)")
    print(f"  Distinguished Points:   {res.num_dps:,} trapped")
    print(f"  GPU Dispatch Rounds:    {res.num_rounds}")

    # Step 3: Independent Cryptographic Verifications
    # 1. EC Curve point check
    pt_test = scalar_mult_ref(recovered_k, G)
    assert pt_test == Q, "EC scalar multiplication check FAILED!"
    print("  [VERIFIED 1/3] k * G == Q exactly on secp256k1 curve.")

    # 2. Bitcoin Address check
    derived_addr = pubkey_to_address(pt_test, compressed=True)
    assert derived_addr == addr, "Derived address does not match target address!"
    print(f"  [VERIFIED 2/3] Base58Check(HASH160(k*G)) == {derived_addr}.")

    # 3. Ground truth check
    assert recovered_k == ground_truth, f"Recovered scalar does not match published ground truth {hex(ground_truth)}!"
    print(f"  [VERIFIED 3/3] Solution matches published historical ground truth: {hex(ground_truth)}.")

    return {
        "puzzle_num": p_num,
        "address": addr,
        "interval_width": width,
        "recovered_scalar_hex": hex(recovered_k),
        "recovered_scalar_dec": str(recovered_k),
        "solve_time_sec": t_solve,
        "total_steps": res.total_steps,
        "c_work_factor": c_factor,
        "throughput_kadds": res.throughput_kadds,
        "num_dps": res.num_dps,
        "num_rounds": res.num_rounds,
        "timing": res.timing
    }

def main():
    engine = OpenCLKangarooEngine()
    results = []
    
    # Solve Puzzle 40, 41, 42
    for p in PUZZLES:
        res = solve_puzzle(engine, p)
        results.append(res)

    print("\n" + "=" * 75)
    print("ALL REAL-WORLD BITCOIN PUZZLE TARGETS VERIFIED & SOLVED!")
    print("=" * 75)
    for r in results:
        print(f"Puzzle #{r['puzzle_num']:2d} ({r['address']}): {r['solve_time_sec']:.3f} s | {r['total_steps']:,} steps (c={r['c_work_factor']:.2f}) | Key: {r['recovered_scalar_hex']}")

    with open("bitcoin_puzzle_real_world_report.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nSaved full verification ledger to bitcoin_puzzle_real_world_report.json")

if __name__ == "__main__":
    main()
