#!/usr/bin/env python3
"""
Controlled /dev/urandom trigger script for early-boot entropy research.

SAFETY CONSTRAINTS:
- Immediately discards any raw bytes read from /dev/urandom.
- Under NO circumstances logs, stores, or serializes returned bytes.
- Records only non-sensitive execution metadata: timestamp, read size, and duration.
"""

import os
import sys
import time
import json

def execute_controlled_trigger(bytes_to_read=17, iterations=1):
    read_metadata = []
    
    start_total_ns = time.time_ns() if hasattr(time, 'time_ns') else int(time.time() * 1e9)
    
    with open('/dev/urandom', 'rb') as f:
        for i in range(iterations):
            t0 = time.time_ns() if hasattr(time, 'time_ns') else int(time.time() * 1e9)
            raw = f.read(bytes_to_read)
            t1 = time.time_ns() if hasattr(time, 'time_ns') else int(time.time() * 1e9)
            
            # Immediately scrub / discard raw random bytes
            n_bytes = len(raw)
            del raw
            
            read_metadata.append({
                "iteration": i,
                "requested_bytes": bytes_to_read,
                "received_bytes": n_bytes,
                "read_start_ns": t0,
                "read_end_ns": t1,
                "duration_ns": t1 - t0
            })
            
    summary = {
        "trigger_event": "controlled_urandom_read",
        "total_iterations": iterations,
        "bytes_per_iteration": bytes_to_read,
        "total_bytes_read": iterations * bytes_to_read,
        "total_duration_ns": read_metadata[-1]["read_end_ns"] - read_metadata[0]["read_start_ns"],
        "reads": read_metadata
    }
    
    print(json.dumps(summary, indent=2))
    return summary

if __name__ == '__main__':
    n_bytes = int(sys.argv[1]) if len(sys.argv) > 1 else 17
    iters = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    execute_controlled_trigger(n_bytes, iters)
