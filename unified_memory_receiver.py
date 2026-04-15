#!/usr/bin/env python3
# unified_memory_receiver.py
# Method: NIC → Unified Memory ← GPU

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
gpu_idx      = 0

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

    total_size = PKT_SIZE * GPU_BUF_PKTS

    # Allocate unified memory
    # returns MemoryPointer object
    um_mem = cp.cuda.malloc_managed(total_size)

    # Correct way to wrap MemoryPointer
    # as a CuPy array directly
    # do NOT use np.frombuffer on it
    um_gpu = cp.ndarray(
        total_size,
        dtype=cp.uint8,
        memptr=um_mem        # use memptr param
    )

    # CPU view of same memory
    # get raw pointer address
    # wrap with numpy using ctypes
    import ctypes
    ptr = um_mem.ptr          # raw memory address
    c_arr = (ctypes.c_uint8 * total_size)\
        .from_address(ptr)
    um_cpu = np.frombuffer(
        c_arr,
        dtype=np.uint8
    )

    print("Method: Unified Memory")
    print(f"Port  : {UDP_PORT}")
    print("Waiting for packets...")

    while RUNNING:
        try:
            data, _ = sock.recvfrom(PKT_SIZE)
            pkt_len = min(len(data), PKT_SIZE)

            offset = gpu_idx * PKT_SIZE

            # CPU writes to unified memory
            # via numpy view
            um_cpu[offset:offset+pkt_len] = \
                np.frombuffer(
                    data[:pkt_len],
                    dtype=np.uint8
                )

            gpu_idx = \
                (gpu_idx + 1) % GPU_BUF_PKTS
            stats['packets'] += 1
            stats['bytes']   += pkt_len

        except socket.timeout:
            continue
        except Exception as e:
            print(f"Error: {e}")
            continue

    sock.close()

def print_stats():
    prev_p = 0
    prev_b = 0
    while RUNNING:
        time.sleep(5)
        dp   = stats['packets'] - prev_p
        db   = stats['bytes']   - prev_b
        gbps = (db * 8) / 5 / 1e9
        pps  = dp / 5
        print(
            f"[UnifiedMem] "
            f"pps={pps:.0f}  "
            f"throughput={gbps:.3f} Gbps  "
            f"total={stats['packets']}"
        )
        prev_p = stats['packets']
        prev_b = stats['bytes']

if __name__ == "__main__":
    print("=" * 50)
    print("  Method 4: Unified Memory")
    print("  NIC → Unified Mem (CPU+GPU shared)")
    print("  Measure: nvidia-smi dmon -s t -d 1")
    print("=" * 50)
    print("")
    t = threading.Thread(
        target=print_stats,
        daemon=True
    )
    t.start()
    receive_and_copy()
