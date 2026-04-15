#!/usr/bin/env python3
# unified_memory_receiver.py
# Method: NIC → Unified Memory ← GPU
# CUDA manages CPU/GPU memory automatically
# GPU accesses CPU memory directly
# via page fault mechanism

import socket
import numpy as np
import threading
import time
import signal
import sys

try:
    import cupy as cp
    print("CuPy available ✅")
except ImportError:
    print("source ~/gpu_benchmark_env/bin/activate")
    sys.exit(1)

UDP_PORT     = 5201
PKT_SIZE     = 1024
GPU_BUF_PKTS = 2048
RUNNING      = True
stats        = {'packets': 0, 'bytes': 0}

# Unified memory buffer
# accessible from both CPU and GPU
# CUDA migrates pages automatically
# first GPU access causes page fault
# CUDA migrates page to GPU
# = overhead on first access
um_buffer = cp.cuda.alloc_managed(
    PKT_SIZE * GPU_BUF_PKTS
)
gpu_idx = 0

def signal_handler(sig, frame):
    global RUNNING
    RUNNING = False
signal.signal(signal.SIGINT, signal_handler)

def receive_and_copy():
    global gpu_idx, RUNNING

    sock = socket.socket(
        socket.AF_INET,
        socket.SOCK_DGRAM
    )
    sock.setsockopt(
        socket.SOL_SOCKET,
        socket.SO_RCVBUF,
        256 * 1024 * 1024
    )
    sock.bind(("0.0.0.0", UDP_PORT))
    sock.settimeout(1.0)

    print("Method: Unified Memory")
    print(f"Port  : {UDP_PORT}")
    print("Waiting for packets...")

    while RUNNING:
        try:
            data, _ = sock.recvfrom(PKT_SIZE)
            pkt_len = min(len(data), PKT_SIZE)

            # Write directly to unified memory
            # no explicit copy needed
            # CPU writes here
            # GPU reads from same address
            # CUDA handles migration
            offset = gpu_idx * PKT_SIZE
            um_buffer[offset:offset+pkt_len] = \
                data[:pkt_len]

            gpu_idx = (gpu_idx + 1) % GPU_BUF_PKTS
            stats['packets'] += 1
            stats['bytes']   += pkt_len

        except socket.timeout:
            continue

    sock.close()

def print_stats():
    prev_p = 0
    prev_b = 0
    while RUNNING:
        time.sleep(5)
        dp = stats['packets'] - prev_p
        db = stats['bytes']   - prev_b
        gbps = (db * 8) / 5 / 1e9
        print(f"[UnifiedMem] "
              f"{dp/5:.0f} pps  "
              f"{gbps:.3f} Gbps  "
              f"total={stats['packets']}")
        prev_p = stats['packets']
        prev_b = stats['bytes']

if __name__ == "__main__":
    print("=" * 50)
    print("  Method 4: Unified Memory")
    print("  NIC → Unified Mem (CPU+GPU shared)")
    print("  Measure: nvidia-smi dmon -s t -d 1")
    print("=" * 50)
    t = threading.Thread(
        target=print_stats, daemon=True)
    t.start()
    receive_and_copy()
