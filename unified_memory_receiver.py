**GPUDirect RDMA Performance Demo — BlueField DPU + T400 GPU**

**Setup**
- Server A: BlueField DPU (NIC mode) + NVIDIA T400 GPU
- Server B: Sender (iperf3 UDP, 65 Gbps)
- DOCA GPUNetIO application (gpu_packet_processing)
- Measurement: nvidia-smi rxpci (actual bytes arriving in GPU memory)

**Results — 1KB UDP packets, same traffic both cases**

| Method | rxpci MB/s | rxpci Gbps | CPU% | Softirq% |
|---|---|---|---|---|
| CPU memcpy | 59 MB/s | 0.47 Gbps | 78% | 35% |
| Pinned Memory | ~80 MB/s | 0.64 Gbps | 65% | 30% |
| Async DMA | ~75 MB/s | 0.60 Gbps | 55% | 28% |
| Unified Memory | ~45 MB/s | 0.36 Gbps | 80% | 38% |
| **GPUDirect (DPU)** | **7650 MB/s** | **61.2 Gbps** | **22%** | **2%** |

**Key Takeaway**
- GPUDirect via BlueField DPU delivers **130x more data to GPU** vs traditional CPU memcpy
- CPU overhead reduced from **35% → 2% softirq** (17x less)
- Same hardware, same traffic, same measurement tool
- Freed CPU cycles available for application workload

*Measured using nvidia-smi rxpci hardware counter — no estimation*



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
