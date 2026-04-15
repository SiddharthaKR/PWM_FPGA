#!/bin/bash
# live_monitor.sh
# Single terminal live monitor
# Shows all metrics every 5 seconds
# Works for all cases:
#   - CPU methods (cudaMemcpy/Pinned/Async/UM)
#   - GPUDirect (DOCA app)

IFACE="enp70s0"
INTERVAL=5
OUTPUT="./results/live_monitor_\
$(date +%H%M%S).txt"

mkdir -p ./results

# ─── Colors ──────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
WHITE='\033[1;37m'
BOLD='\033[1m'
NC='\033[0m'

# ─── Get Metrics ─────────────────────────

get_rxpci_mbs() {
    # GPU PCIe receive MB/s
    # = actual bytes into GPU memory
    nvidia-smi dmon \
        -s t -d 1 -c 2 2>/dev/null | \
    awk '!/^#/{val=$2} \
        END{print (val=="")?0:val}'
}

get_txpci_mbs() {
    # GPU PCIe transmit MB/s
    nvidia-smi dmon \
        -s t -d 1 -c 2 2>/dev/null | \
    awk '!/^#/{val=$3} \
        END{print (val=="")?0:val}'
}

get_gpu_compute() {
    # GPU compute utilization %
    nvidia-smi \
        --query-gpu=utilization.gpu \
        --format=csv,noheader,nounits \
        2>/dev/null | tr -d ' '
}

get_gpu_mem_used() {
    # GPU memory used MiB
    nvidia-smi \
        --query-gpu=memory.used \
        --format=csv,noheader,nounits \
        2>/dev/null | tr -d ' '
}

get_cpu_total() {
    # Total CPU usage %
    mpstat 1 1 2>/dev/null | \
    awk '/Average.*all/ \
        {printf "%.1f", 100-$NF}'
}

get_cpu_softirq() {
    # CPU softirq %
    # = CPU time handling
    #   network interrupts
    mpstat 1 1 2>/dev/null | \
    awk '/Average.*all/ \
        {printf "%.1f", $10}'
}

get_cpu_irq() {
    # Hardware IRQ %
    mpstat 1 1 2>/dev/null | \
    awk '/Average.*all/ \
        {printf "%.1f", $9}'
}

get_nic_gbps() {
    # NIC receive throughput Gbps
    # = bytes arriving at NIC
    local P=$(cat \
        /sys/class/net/$IFACE/\
statistics/rx_bytes \
        2>/dev/null || echo 0)
    sleep 1
    local C=$(cat \
        /sys/class/net/$IFACE/\
statistics/rx_bytes \
        2>/dev/null || echo 0)
    local D=$(( C - P ))
    echo "scale=3; $D*8/1000000000" | bc
}

get_nic_pps() {
    # NIC receive packets per second
    local P=$(cat \
        /sys/class/net/$IFACE/\
statistics/rx_packets \
        2>/dev/null || echo 0)
    sleep 1
    local C=$(cat \
        /sys/class/net/$IFACE/\
statistics/rx_packets \
        2>/dev/null || echo 0)
    echo $(( C - P ))
}

draw_bar() {
    local value=$1
    local max=$2
    local width=20
    local color=$3
    local filled=$(( value * width / max ))
    [ $filled -gt $width ] && filled=$width
    local empty=$(( width - filled ))
    printf "${color}["
    printf '%0.s█' $(seq 1 $filled) 2>/dev/null
    printf '%0.s░' $(seq 1 $empty)  2>/dev/null
    printf "]${NC}"
}

# ─── Header ──────────────────────────────

print_header() {
    echo -e "${BOLD}${CYAN}"
    echo "╔══════════════════════════════════════════════════════╗"
    echo "║          GPU Packet Transfer Live Monitor            ║"
    echo "║  nvidia-smi rxpci + CPU + GPU metrics every 5s      ║"
    echo "╚══════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo -e "  Interface : ${WHITE}$IFACE${NC}"
    echo -e "  Output    : ${WHITE}$OUTPUT${NC}"
    echo -e "  Press ${RED}Ctrl+C${NC} to stop"
    echo ""
}

# ─── Log Header ──────────────────────────

log_header() {
    {
    echo "========================================================"
    echo "  GPU Packet Transfer Live Monitor"
    echo "  $(date)"
    echo "========================================================"
    printf "%-8s %-10s %-10s %-10s %-10s %-10s %-10s %-10s\n" \
        "Time" \
        "rxpci_MBs" \
        "rxpci_Gbps" \
        "NIC_Gbps" \
        "CPU_pct" \
        "SoftIRQ" \
        "GPU_pct" \
        "GPU_MiB"
    echo "--------------------------------------------------------"
    } > $OUTPUT
}

# ─── Main Loop ───────────────────────────

clear
print_header
log_header

SAMPLE=0

while true; do
    SAMPLE=$(( SAMPLE + 1 ))
    TS=$(date '+%H:%M:%S')

    # Collect all metrics in parallel
    # where possible

    # rxpci — GPU PCIe receive
    RXPCI=$(get_rxpci_mbs)
    TXPCI=$(get_txpci_mbs)

    # Convert rxpci to Gbps
    RXPCI_GBPS=$(echo \
        "scale=3; $RXPCI*8/1000" | bc)

    # NIC throughput
    NIC_GBPS=$(get_nic_gbps)

    # CPU metrics
    CPU_TOTAL=$(get_cpu_total)
    CPU_SOFT=$(get_cpu_softirq)
    CPU_IRQ=$(get_cpu_irq)

    # GPU metrics
    GPU_COMPUTE=$(get_gpu_compute)
    GPU_MEM=$(get_gpu_mem_used)

    # ── Display ──────────────────────────
    printf '\033[H'   # cursor home no flash

    print_header

    echo -e "  ${BOLD}Sample #${SAMPLE}   ${TS}${NC}"
    echo ""

    # ── rxpci Section ────────────────────
    echo -e "  ${BOLD}${CYAN}GPU PCIe Receive (rxpci):${NC}"
    echo -e "  ${WHITE}= actual bytes arriving"
    echo -e "    in GPU memory${NC}"
    echo ""

    RXPCI_INT=${RXPCI%.*}
    [ -z "$RXPCI_INT" ] && RXPCI_INT=0

    printf "  rxpci raw  : %6s MB/s  " \
        "$RXPCI"
    draw_bar $RXPCI_INT 8000 $CYAN
    echo ""

    printf "  rxpci Gbps : %6s Gbps  " \
        "$RXPCI_GBPS"
    draw_bar $RXPCI_INT 8000 $GREEN
    echo ""

    printf "  txpci      : %6s MB/s\n" \
        "$TXPCI"

    echo ""

    # ── NIC Section ──────────────────────
    echo -e "  ${BOLD}${CYAN}NIC Throughput:${NC}"
    echo -e "  ${WHITE}= bytes arriving at interface${NC}"
    echo ""

    NIC_INT=$(echo "$NIC_GBPS" | \
        awk '{printf "%d", $1*10}')
    [ -z "$NIC_INT" ] && NIC_INT=0

    printf "  NIC rx     : %6s Gbps  " \
        "$NIC_GBPS"
    draw_bar $NIC_INT 650 $YELLOW
    echo ""

    echo ""

    # ── CPU Section ──────────────────────
    echo -e "  ${BOLD}${CYAN}CPU Utilization:${NC}"
    echo ""

    CPU_INT=${CPU_TOTAL%.*}
    SOFT_INT=${CPU_SOFT%.*}
    IRQ_INT=${CPU_IRQ%.*}
    [ -z "$CPU_INT"  ] && CPU_INT=0
    [ -z "$SOFT_INT" ] && SOFT_INT=0
    [ -z "$IRQ_INT"  ] && IRQ_INT=0

    printf "  CPU total  : %6s %%      " \
        "$CPU_TOTAL"
    draw_bar $CPU_INT 100 $RED
    echo ""

    printf "  SoftIRQ    : %6s %%      " \
        "$CPU_SOFT"
    draw_bar $SOFT_INT 50 $RED
    echo -e "  ${WHITE}← network processing cost${NC}"

    printf "  HardIRQ    : %6s %%      " \
        "$CPU_IRQ"
    draw_bar $IRQ_INT 10 $YELLOW
    echo ""

    echo ""

    # ── GPU Section ──────────────────────
    echo -e "  ${BOLD}${CYAN}GPU Utilization:${NC}"
    echo ""

    GPU_INT=${GPU_COMPUTE%.*}
    [ -z "$GPU_INT" ] && GPU_INT=0

    printf "  GPU compute: %6s %%      " \
        "$GPU_COMPUTE"
    draw_bar $GPU_INT 100 $GREEN
    echo ""

    printf "  GPU memory : %6s MiB\n" \
        "$GPU_MEM"

    echo ""

    # ── Summary Box ──────────────────────
    echo -e "  ${BOLD}══════════════════════════════════════${NC}"

    # Determine what is happening
    if [ "$RXPCI_INT" -gt 1000 ]; then
        echo -e "  ${GREEN}${BOLD}  GPUDirect RDMA ACTIVE${NC}"
        echo -e "  ${GREEN}  DPU feeding GPU at ${RXPCI_GBPS} Gbps${NC}"
    elif [ "$RXPCI_INT" -gt 10 ]; then
        echo -e "  ${YELLOW}${BOLD}  CPU → GPU transfer active${NC}"
        echo -e "  ${YELLOW}  CPU copying at ${RXPCI_GBPS} Gbps${NC}"
    else
        echo -e "  ${WHITE}  No GPU transfer detected${NC}"
        echo -e "  ${WHITE}  Start receiver + iperf3${NC}"
    fi

    echo -e "  ${BOLD}══════════════════════════════════════${NC}"
    echo ""
    echo -e "  ${WHITE}Updated: $TS${NC}"

    # ── Log to File ──────────────────────
    printf "%-8s %-10s %-10s %-10s %-10s %-10s %-10s %-10s\n" \
        "$TS" \
        "$RXPCI" \
        "$RXPCI_GBPS" \
        "$NIC_GBPS" \
        "$CPU_TOTAL" \
        "$CPU_SOFT" \
        "$GPU_COMPUTE" \
        "$GPU_MEM" \
        >> $OUTPUT

    sleep $INTERVAL
done
