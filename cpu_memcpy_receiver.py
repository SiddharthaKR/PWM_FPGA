#!/usr/bin/env python3
# cpu_memcpy_receiver.py
# Method: NIC → CPU RAM → cudaMemcpy → GPU
# Traditional pageable memory copy

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

gpu_buffer   = cp.zeros(
    PKT_SIZE * GPU_BUF_PKTS,
    dtype=cp.uint8
)
gpu_idx      = 0
stats        = {'packets': 0, 'bytes': 0}

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

    # Regular pageable CPU buffer
    # allocated by OS normally
    # can be swapped to disk
    cpu_buf = np.zeros(PKT_SIZE, dtype=np.uint8)

    print("Method: cudaMemcpy (pageable)")
    print(f"Port  : {UDP_PORT}")
    print("Waiting for packets...")

    while RUNNING:
        try:
            data, _ = sock.recvfrom(PKT_SIZE)
            pkt_len = min(len(data), PKT_SIZE)

            # Put in pageable CPU buffer
            cpu_buf[:pkt_len] = np.frombuffer(
                data[:pkt_len], dtype=np.uint8)

            # cudaMemcpy pageable → GPU
            # CPU must stage through
            # pinned buffer internally
            # = extra copy overhead
            offset = gpu_idx * PKT_SIZE
            gpu_buffer[offset:offset+pkt_len] = \
                cp.asarray(cpu_buf[:pkt_len])

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
        print(f"[cudaMemcpy] "
              f"{dp/5:.0f} pps  "
              f"{gbps:.3f} Gbps  "
              f"total={stats['packets']}")
        prev_p = stats['packets']
        prev_b = stats['bytes']

if __name__ == "__main__":
    print("=" * 50)
    print("  Method 1: cudaMemcpy (pageable)")
    print("  NIC → CPU RAM → GPU")
    print("  Measure: nvidia-smi dmon -s t -d 1")
    print("=" * 50)
    t = threading.Thread(
        target=print_stats, daemon=True)
    t.start()
    receive_and_copy()
