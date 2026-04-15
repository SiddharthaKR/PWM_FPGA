#!/usr/bin/env python3
# async_dma_receiver.py
# Method: NIC → CPU RAM → Async DMA → GPU
# CPU submits transfer and continues
# does not wait/block for completion

import socket
import numpy as np
import threading
import time
import signal
import sys

try:
    import cupy as cp
    import cupy.cuda as cuda
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

# CUDA stream for async operations
# CPU submits work to stream
# CPU does not wait for completion
# GPU executes independently
stream = cp.cuda.Stream(non_blocking=True)

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

    # Pinned buffer needed for async DMA
    # async transfers require pinned memory
    # pageable memory cannot be used
    # with async transfers
    pinned_mem = cuda.alloc_pinned_memory(
        PKT_SIZE)
    cpu_buf = np.frombuffer(
        pinned_mem,
        dtype=np.uint8,
        count=PKT_SIZE
    )

    print("Method: Async DMA (non-blocking)")
    print(f"Port  : {UDP_PORT}")
    print("Waiting for packets...")

    while RUNNING:
        try:
            data, _ = sock.recvfrom(PKT_SIZE)
            pkt_len = min(len(data), PKT_SIZE)

            # Copy to pinned buffer
            cpu_buf[:pkt_len] = np.frombuffer(
                data[:pkt_len], dtype=np.uint8)

            # Submit async DMA to stream
            # CPU does NOT block here
            # CPU moves to next packet
            # immediately
            # GPU processes in background
            with stream:
                offset = gpu_idx * PKT_SIZE
                gpu_buffer[
                    offset:offset+pkt_len
                ] = cp.asarray(
                    cpu_buf[:pkt_len])

            # No synchronize here
            # = truly async
            # CPU free to receive next

            gpu_idx = (gpu_idx + 1) % GPU_BUF_PKTS
            stats['packets'] += 1
            stats['bytes']   += pkt_len

        except socket.timeout:
            # Sync stream on timeout
            # catch up with GPU
            stream.synchronize()
            continue

    stream.synchronize()
    sock.close()

def print_stats():
    prev_p = 0
    prev_b = 0
    while RUNNING:
        time.sleep(5)
        dp = stats['packets'] - prev_p
        db = stats['bytes']   - prev_b
        gbps = (db * 8) / 5 / 1e9
        print(f"[AsyncDMA] "
              f"{dp/5:.0f} pps  "
              f"{gbps:.3f} Gbps  "
              f"total={stats['packets']}")
        prev_p = stats['packets']
        prev_b = stats['bytes']

if __name__ == "__main__":
    print("=" * 50)
    print("  Method 3: Async DMA")
    print("  NIC → Pinned CPU RAM → GPU (async)")
    print("  Measure: nvidia-smi dmon -s t -d 1")
    print("=" * 50)
    t = threading.Thread(
        target=print_stats, daemon=True)
    t.start()
    receive_and_copy()
