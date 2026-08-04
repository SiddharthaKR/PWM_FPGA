# DPU DDoS Training — 3 Tasks · Both Trainees

Two trainees run in parallel on separate bridges. All commands below are grouped
by trainee. Each has their own bridge, subnet, and interface — nothing collides.

| | **Trainee A** | **Trainee B** |
|---|---|---|
| Bridge | `ovsbr1` | `ovsbr2` |
| Host NIC | `eno16595np0` | `eno16595np1` |
| Host base IP | `192.168.10.11` | `192.168.20.11` |
| DPU target IP | `192.168.10.10` | `192.168.20.10` |
| Representor | `pf0hpf` | `pf1hpf` |
| Subnet | `192.168.10.0/24` | `192.168.20.0/24` |

**Golden rule for every task:** a block only counts if it appears under
`dpctl/dump-flows type=offloaded` with its packet counter climbing.
`dump-flows ovsbr1` alone does NOT prove hardware offload.

---

# TRAINEE A  (ovsbr1 · 192.168.10.x)

## Task A1 — Block a UDP Flood by Port

**Host (attack):**
```bash
sudo hping3 --udp --flood -p 53 192.168.10.10
```

**DPU (solution):**
```bash
sudo ovs-ofctl add-flow ovsbr1 "priority=100,udp,tp_dst=53,actions=drop"
```

**DPU (verify — prove hardware):**
```bash
sudo ovs-appctl dpctl/dump-flows type=offloaded | grep -i udp
sudo ovs-ofctl dump-flows ovsbr1 | grep udp
```
Pass = `udp(dst=53) actions:drop` under `type=offloaded`, packets climbing.

---

## Task A2 — Subnet Block with Whitelist Exception

**Host (add whitelisted user + attack):**
```bash
# Whitelisted user's IP — assigned as a REAL alias (needed to ping from it)
sudo ip addr add 192.168.10.50/24 dev eno16595np0

# Attack from a spoofed subnet IP
sudo hping3 -S --flood -p 80 -a 192.168.10.77 192.168.10.10
```

**DPU (solution — whitelist FIRST, then blanket block):**
```bash
sudo ovs-ofctl add-flow ovsbr1 "priority=200,ip,nw_src=192.168.10.50,actions=NORMAL"
sudo ovs-ofctl add-flow ovsbr1 "priority=100,ip,nw_src=192.168.10.0/24,actions=drop"
```

**DPU (verify ordering + hardware):**
```bash
sudo ovs-ofctl dump-flows ovsbr1                                    # 200 above 100
sudo ovs-appctl dpctl/dump-flows type=offloaded | grep "192.168.10"
```

**Host (verify logic — use REAL host IPs, not the spoofed .77):**
```bash
ping -c 3 -I 192.168.10.50 192.168.10.10    # whitelisted → 0% loss (works)
ping -c 3 -I 192.168.10.11 192.168.10.10    # blocked subnet → 100% loss
```
Pass = `.50` pings succeed, `.11` fully dropped, subnet drop offloaded.

> Note: do NOT `ping -I 192.168.10.77` — that IP is only a spoofed hping3 source,
> it isn't assigned to the host, so ping can't bind to it. Use `.11` to test the block.

---

## Task A3 — Detect and Block a Spoofed Attacker

**Host (trainer runs; the .88 IP is hidden from the trainee):**
```bash
sudo hping3 -S --flood -p 80 -a 192.168.10.88 192.168.10.10
```

**DPU (solution — DISCOVER the IP, then block):**
```bash
# Step 1 — identify the attacker
sudo tcpdump -i pf0hpf -n -c 20
# (optional) top-talker confirmation
sudo timeout 5 tcpdump -i pf0hpf -n -q 2>/dev/null | \
  awk '{print $3}' | cut -d. -f1-4 | sort | uniq -c | sort -rn | head

# Step 2 — block the IP you found (192.168.10.88)
sudo ovs-ofctl add-flow ovsbr1 "priority=100,ip,nw_src=192.168.10.88,actions=drop"
```

**DPU (verify — hardware + silence):**
```bash
sudo ovs-appctl dpctl/dump-flows type=offloaded | grep 192.168.10.88
sudo tcpdump -i pf0hpf -n -c 10    # should hang/timeout — packets die in silicon
```
Pass = correctly identified `.88`, blocked it, offloaded, tcpdump goes silent.

---

# TRAINEE B  (ovsbr2 · 192.168.20.x)

## Task B1 — Block a UDP Flood by Port

**Host (attack):**
```bash
sudo hping3 --udp --flood -p 53 192.168.20.10
```

**DPU (solution):**
```bash
sudo ovs-ofctl add-flow ovsbr2 "priority=100,udp,tp_dst=53,actions=drop"
```

**DPU (verify — prove hardware):**
```bash
sudo ovs-appctl dpctl/dump-flows type=offloaded | grep -i udp
sudo ovs-ofctl dump-flows ovsbr2 | grep udp
```
Pass = `udp(dst=53) actions:drop` under `type=offloaded`, packets climbing.

---

## Task B2 — Subnet Block with Whitelist Exception

**Host (add whitelisted user + attack):**
```bash
sudo ip addr add 192.168.20.50/24 dev eno16595np1
sudo hping3 -S --flood -p 80 -a 192.168.20.77 192.168.20.10
```

**DPU (solution — whitelist FIRST, then blanket block):**
```bash
sudo ovs-ofctl add-flow ovsbr2 "priority=200,ip,nw_src=192.168.20.50,actions=NORMAL"
sudo ovs-ofctl add-flow ovsbr2 "priority=100,ip,nw_src=192.168.20.0/24,actions=drop"
```

**DPU (verify ordering + hardware):**
```bash
sudo ovs-ofctl dump-flows ovsbr2
sudo ovs-appctl dpctl/dump-flows type=offloaded | grep "192.168.20"
```

**Host (verify logic — use REAL host IPs, not the spoofed .77):**
```bash
ping -c 3 -I 192.168.20.50 192.168.20.10    # whitelisted → 0% loss (works)
ping -c 3 -I 192.168.20.11 192.168.20.10    # blocked subnet → 100% loss
```
Pass = `.50` pings succeed, `.11` fully dropped, subnet drop offloaded.

> Note: do NOT `ping -I 192.168.20.77` — spoofed source only, not assigned to host.

---

## Task B3 — Detect and Block a Spoofed Attacker

**Host (trainer runs; the .88 IP is hidden from the trainee):**
```bash
sudo hping3 -S --flood -p 80 -a 192.168.20.88 192.168.20.10
```

**DPU (solution — DISCOVER the IP, then block):**
```bash
sudo tcpdump -i pf1hpf -n -c 20
sudo timeout 5 tcpdump -i pf1hpf -n -q 2>/dev/null | \
  awk '{print $3}' | cut -d. -f1-4 | sort | uniq -c | sort -rn | head

sudo ovs-ofctl add-flow ovsbr2 "priority=100,ip,nw_src=192.168.20.88,actions=drop"
```

**DPU (verify — hardware + silence):**
```bash
sudo ovs-appctl dpctl/dump-flows type=offloaded | grep 192.168.20.88
sudo tcpdump -i pf1hpf -n -c 10    # should hang/timeout
```
Pass = correctly identified `.88`, blocked it, offloaded, tcpdump goes silent.

---

# IMPORTANT: Shared Offload View

`dpctl/dump-flows type=offloaded` shows ALL offloaded flows on the whole DPU —
BOTH bridges together (single eSwitch datapath). So each trainee must grep for
their OWN subnet to see only their rules:

```bash
# Trainee A
sudo ovs-appctl dpctl/dump-flows type=offloaded | grep "192.168.10"
# Trainee B
sudo ovs-appctl dpctl/dump-flows type=offloaded | grep "192.168.20"
```

---

# CLEANUP BETWEEN TRAINEES

**DPU (both bridges):**
```bash
sudo ovs-ofctl del-flows ovsbr1
sudo ovs-ofctl del-flows ovsbr2
sudo ovs-ofctl add-flow ovsbr1 "priority=0,actions=NORMAL"
sudo ovs-ofctl add-flow ovsbr2 "priority=0,actions=NORMAL"
sudo ip neigh flush all
sudo ovs-ofctl dump-flows ovsbr1     # verify NORMAL only
sudo ovs-ofctl dump-flows ovsbr2     # verify NORMAL only
```

**Host A:**
```bash
sudo killall hping3 2>/dev/null
sudo ip addr del 192.168.10.50/24 dev eno16595np0 2>/dev/null
sudo ip neigh flush all
ping -c 3 192.168.10.10
```

**Host B:**
```bash
sudo killall hping3 2>/dev/null
sudo ip addr del 192.168.20.50/24 dev eno16595np1 2>/dev/null
sudo ip neigh flush all
ping -c 3 192.168.20.10
```

---

# PRE-SESSION CHECK (trainer, before trainees arrive)

```bash
# Offload ON
sudo ovs-vsctl get Open_vSwitch . other_config:hw-offload      # "true"

# Both bridges up with IPs
ip -br addr show ovsbr1
ip -br addr show ovsbr2

# Both representors exist and up
ip -br link show pf0hpf pf1hpf

# Baseline ping BOTH paths
ping -c 3 192.168.10.10    # from host, A path
ping -c 3 192.168.20.10    # from host, B path
```
Fix any B-side (ovsbr2 / pf1hpf / p1) issues BEFORE the session, not during.
