#!/bin/bash
# live_monitor.sh
# Live metrics — numbers only
# Updates every 5 seconds

IFACE="enp70s0"
INTERVAL=5
OUTPUT="./results/live_monitor_$(date +%H%M%S).txt"
mkdir -p ./results

# ─── Get Metrics ─────────────────────────

get_rxpci() {
    nvidia-smi dmon \
        -s t -d 1 -c 2 2>/dev/null | \
    awk '!/^#/{val=$2} END{print (val=="")?0:val}'
}

get_txpci() {
    nvidia-smi dmon \
        -s t -d 1 -c 2 2>/dev/null | \
    awk '!/^#/{val=$3} END{print (val=="")?0:val}'
}

get_gpu_compute() {
    nvidia-smi \
        --query-gpu=utilization.gpu \
        --format=csv,noheader,nounits \
        2>/dev/null | tr -d ' '
}

get_gpu_mem() {
    nvidia-smi \
        --query-gpu=memory.used \
        --format=csv,noheader,nounits \
        2>/dev/null | tr -d ' '
}

get_nic_mbps() {
    local P=$(cat /sys/class/net/$IFACE/\
statistics/rx_bytes 2>/dev/null || echo 0)
    sleep 1
    local C=$(cat /sys/class/net/$IFACE/\
statistics/rx_bytes 2>/dev/null || echo 0)
    local D=$(( C - P ))
    echo "scale=1; $D/1000000*8" | bc
}

get_cpu_total() {
    mpstat 1 1 2>/dev/null | \
    awk '/Average.*all/{printf "%.1f", 100-$NF}'
}

get_cpu_soft() {
    mpstat 1 1 2>/dev/null | \
    awk '/Average.*all/{printf "%.1f", $10}'
}

get_cpu_irq() {
    mpstat 1 1 2>/dev/null | \
    awk '/Average.*all/{printf "%.1f", $9}'
}

# ─── Log Header ──────────────────────────

{
echo "========================================================"
echo "  GPU Packet Transfer Live Monitor"
echo "  $(date)"
echo "  Interface: $IFACE"
echo "========================================================"
printf "%-10s %-12s %-12s %-12s %-10s %-10s %-10s %-10s %-10s\n" \
    "Time" \
    "rxpci_MBps" \
    "rxpci_Gbps" \
    "NIC_Mbps" \
    "CPU_pct" \
    "Soft_pct" \
    "IRQ_pct" \
    "GPU_pct" \
    "GPU_MiB"
echo "--------------------------------------------------------\
-----------------------------"
} | tee $OUTPUT

# ─── Main Loop ───────────────────────────

SAMPLE=0

while true; do
    SAMPLE=$(( SAMPLE + 1 ))
    TS=$(date '+%H:%M:%S')

    # Collect metrics
    RXPCI=$(get_rxpci)
    TXPCI=$(get_txpci)
    GPU_C=$(get_gpu_compute)
    GPU_M=$(get_gpu_mem)
    NIC_MBPS=$(get_nic_mbps)
    CPU=$(get_cpu_total)
    SOFT=$(get_cpu_soft)
    IRQ=$(get_cpu_irq)

    # Convert rxpci MB/s to Gbps
    RXPCI_GBPS=$(echo \
        "scale=3; $RXPCI*8/1000" | bc)

    # Print to screen and file
    printf "%-10s %-12s %-12s %-12s %-10s %-10s %-10s %-10s %-10s\n" \
        "$TS" \
        "$RXPCI MB/s" \
        "$RXPCI_GBPS Gbps" \
        "$NIC_MBPS Mbps" \
        "$CPU %" \
        "$SOFT %" \
        "$IRQ %" \
        "$GPU_C %" \
        "$GPU_M MiB" \
        | tee -a $OUTPUT

    sleep $INTERVAL
done
