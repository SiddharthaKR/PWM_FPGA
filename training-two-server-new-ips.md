# DPU DDoS Training — Two-Server Setup (Real Sender)

Server B sends real traffic across the wire to Server A (the DPU host).
This is closer to real life — and riskier — so **safety rules come first.**

---

## TOPOLOGY

| | **Trainee A path** | **Trainee B path** |
|---|---|---|
| Subnet | `192.168.100.0/24` | `192.168.110.0/24` |
| **Server A** (receiver, DPU host) | `192.168.100.158` | `192.168.110.158` |
| **Server B** (sender / attacker) | `192.168.100.157` | `192.168.110.157` |
| Bridge (on DPU) | `ovsbr1` | `ovsbr2` |
| Physical uplink (attack ingress) | `p0` | `p1` |
| Host representor (toward Server A host) | `pf0hpf` | `pf1hpf` |

Traffic path (attack):
`Server B → wire → p0 (uplink) → bridge → pf0hpf → Server A host (.158)`

Block rules go on the **DPU bridge** (`ovsbr1` / `ovsbr2`).
Sends go from **Server B**. Verification pings go from **Server B**.

> Verify these interface names on THIS server before starting:
> `ip -br link show | grep -E "p0|p1|pf0hpf|pf1hpf|ovsbr"`

---

## ⚠️ SAFETY — READ BEFORE ANYTHING

1. **Protect your management path.** Confirm how you SSH to the DPU and to
   Server A. If that path is on `192.168.100.x` or `192.168.110.x`, the Task 2
   subnet block WILL cut you off. Keep management out-of-band, or whitelist the
   management source IP at the highest priority (see Task 2).

2. **Offload must be ON before any flood.**
   ```bash
   sudo ovs-vsctl get Open_vSwitch . other_config:hw-offload   # must be "true"
   ```
   With offload OFF, a real external flood hits the DPU/host CPU in software and
   can overload the box. Never `--flood` with offload off on this setup.

3. **Ramp up — don't open with `--flood`.** For every task, first send at a
   MODERATE rate, confirm forwarding and the block work, confirm the drop is
   offloaded, THEN (optionally) escalate. Hardware absorbs the flood only after
   the offloaded rule is in place.

4. **Keep a kill switch ready.**
   ```bash
   # Server B — stop sending immediately
   sudo killall hping3
   # DPU — remove a bad rule (replace priority as needed)
   sudo ovs-ofctl del-flows ovsbr1 "priority=300"
   ```

5. **Subnet blocks must whitelist the receiver's own IP (.158)** or you drop
   Server A's own replies and break even whitelisted traffic. Built into Task 2.

---

## PRE-SESSION VERIFICATION (trainer)

```bash
# --- On the DPU ---
sudo ovs-vsctl get Open_vSwitch . other_config:hw-offload    # "true"
ip -br addr show ovsbr1 ovsbr2
ip -br link show p0 p1 pf0hpf pf1hpf                          # all UP

# --- On Server A host --- confirm receiver IPs are present
ip -br addr show | grep -E "192.168.100.158|192.168.110.158"

# --- From Server B --- baseline reachability (MODERATE, not flood)
ping -c 3 192.168.100.158      # A path
ping -c 3 192.168.110.158      # B path
```
Both pings must succeed before training. Fix any B-path (ovsbr2/p1/pf1hpf)
issue now, not during the session.

---

# TRAINEE A  —  subnet 192.168.100.x · ovsbr1

## Task A1 — Block a UDP Flood by Port

**SEND — Server B (start moderate, then escalate):**
```bash
# 1) moderate first — confirm it flows and can be blocked
sudo hping3 --udp -i u1000 -p 53 192.168.100.158
# (u1000 = 1 packet / 1000 us ≈ 1000 pps — safe to observe)

# 2) after the block is verified offloaded, you MAY escalate:
# sudo hping3 --udp --flood -p 53 192.168.100.158
```

**SOLUTION — DPU:**
```bash
sudo ovs-ofctl add-flow ovsbr1 "priority=100,udp,tp_dst=53,actions=drop"
```

**VERIFY — DPU (prove hardware):**
```bash
sudo ovs-appctl dpctl/dump-flows type=offloaded | grep -i "udp"
sudo ovs-ofctl dump-flows ovsbr1 | grep udp
```
Pass = `udp(dst=53) actions:drop` under `type=offloaded`, packets climbing.
This rule is source-agnostic and port-specific — it will NOT touch SSH/ICMP. Safe.

---

## Task A2 — Subnet Block with Whitelist Exception

**SETUP — Server B (add a second source IP = the attacker):**
```bash
# .157 stays the LEGIT server; add .160 as the ATTACKER source
sudo ip addr add 192.168.100.160/24 dev <serverB_ifaceA>
```

**SEND — Server B:**
```bash
# Attack from .160 (moderate first)
sudo hping3 -S -i u1000 -p 80 -a 192.168.100.160 192.168.100.158
```

**SOLUTION — DPU (whitelists FIRST, then blanket block):**
```bash
# Protect the receiver's OWN replies (critical — do not skip)
sudo ovs-ofctl add-flow ovsbr1 "priority=200,ip,nw_src=192.168.100.158,actions=NORMAL"
# Whitelist the legit server
sudo ovs-ofctl add-flow ovsbr1 "priority=200,ip,nw_src=192.168.100.157,actions=NORMAL"
# Blanket block the rest of the subnet
sudo ovs-ofctl add-flow ovsbr1 "priority=100,ip,nw_src=192.168.100.0/24,actions=drop"
```

**VERIFY — DPU:**
```bash
sudo ovs-ofctl dump-flows ovsbr1                                     # 200s above 100
sudo ovs-appctl dpctl/dump-flows type=offloaded | grep "192.168.100"
```

**VERIFY — Server B (logic works both ways):**
```bash
ping -c 3 -I 192.168.100.157 192.168.100.158    # legit → 0% loss (works)
ping -c 3 -I 192.168.100.160 192.168.100.158    # attacker → 100% loss (blocked)
```
Pass = `.157` works, `.160` blocked, `.158` replies intact (that's why the
priority-200 own-IP whitelist matters).

---

## Task A3 — Detect and Block a Spoofed Attacker

**SEND — Server B (TRAINER runs; `.170` hidden from trainee, moderate rate):**
```bash
sudo hping3 -S -i u500 -p 80 -a 192.168.100.170 192.168.100.158
# spoofed source .170 — trainee must DISCOVER it
```

**SOLUTION — DPU (discover, then block):**
```bash
# Step 1 — find the attacker in live traffic
sudo tcpdump -i pf0hpf -n -c 20
#   (alt ingress view:  sudo tcpdump -i p0 -n -c 20 )
# trainee reads the source IP → 192.168.100.170

# Step 2 — block the discovered IP
sudo ovs-ofctl add-flow ovsbr1 "priority=100,ip,nw_src=192.168.100.170,actions=drop"
```

**VERIFY — DPU (hardware + silence):**
```bash
sudo ovs-appctl dpctl/dump-flows type=offloaded | grep 192.168.100.170
sudo tcpdump -i pf0hpf -n -c 10     # goes silent — packets die in silicon
```
Pass = correctly identified `.170`, blocked, offloaded, tcpdump silent.
(Spoofed source, so verify via the offload counter + silence, NOT ping.)

---

# TRAINEE B  —  subnet 192.168.110.x · ovsbr2

## Task B1 — Block a UDP Flood by Port

**SEND — Server B:**
```bash
sudo hping3 --udp -i u1000 -p 53 192.168.110.158      # moderate first
# then optionally: sudo hping3 --udp --flood -p 53 192.168.110.158
```

**SOLUTION — DPU:**
```bash
sudo ovs-ofctl add-flow ovsbr2 "priority=100,udp,tp_dst=53,actions=drop"
```

**VERIFY — DPU:**
```bash
sudo ovs-appctl dpctl/dump-flows type=offloaded | grep -i "udp"
sudo ovs-ofctl dump-flows ovsbr2 | grep udp
```

---

## Task B2 — Subnet Block with Whitelist Exception

**SETUP — Server B:**
```bash
sudo ip addr add 192.168.110.160/24 dev <serverB_ifaceB>
```

**SEND — Server B:**
```bash
sudo hping3 -S -i u1000 -p 80 -a 192.168.110.160 192.168.110.158
```

**SOLUTION — DPU:**
```bash
sudo ovs-ofctl add-flow ovsbr2 "priority=200,ip,nw_src=192.168.110.158,actions=NORMAL"
sudo ovs-ofctl add-flow ovsbr2 "priority=200,ip,nw_src=192.168.110.157,actions=NORMAL"
sudo ovs-ofctl add-flow ovsbr2 "priority=100,ip,nw_src=192.168.110.0/24,actions=drop"
```

**VERIFY — DPU:**
```bash
sudo ovs-ofctl dump-flows ovsbr2
sudo ovs-appctl dpctl/dump-flows type=offloaded | grep "192.168.110"
```

**VERIFY — Server B:**
```bash
ping -c 3 -I 192.168.110.157 192.168.110.158    # works
ping -c 3 -I 192.168.110.160 192.168.110.158    # blocked
```

---

## Task B3 — Detect and Block a Spoofed Attacker

**SEND — Server B (TRAINER; `.170` hidden):**
```bash
sudo hping3 -S -i u500 -p 80 -a 192.168.110.170 192.168.110.158
```

**SOLUTION — DPU:**
```bash
sudo tcpdump -i pf1hpf -n -c 20            # discover → 192.168.110.170
sudo ovs-ofctl add-flow ovsbr2 "priority=100,ip,nw_src=192.168.110.170,actions=drop"
```

**VERIFY — DPU:**
```bash
sudo ovs-appctl dpctl/dump-flows type=offloaded | grep 192.168.110.170
sudo tcpdump -i pf1hpf -n -c 10            # silent
```

---

# SHARED OFFLOAD VIEW (both trainees)

`dpctl/dump-flows type=offloaded` shows BOTH bridges. Grep your own subnet:
```bash
sudo ovs-appctl dpctl/dump-flows type=offloaded | grep "192.168.100"   # Trainee A
sudo ovs-appctl dpctl/dump-flows type=offloaded | grep "192.168.110"   # Trainee B
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
sudo ovs-ofctl dump-flows ovsbr1     # NORMAL only
sudo ovs-ofctl dump-flows ovsbr2     # NORMAL only
```

**Server B (stop sending + remove attacker aliases):**
```bash
sudo killall hping3 2>/dev/null
sudo ip addr del 192.168.100.160/24 dev <serverB_ifaceA> 2>/dev/null
sudo ip addr del 192.168.110.160/24 dev <serverB_ifaceB> 2>/dev/null
sudo ip neigh flush all
```

**Confirm the receiver is healthy again:**
```bash
# From Server B
ping -c 3 192.168.100.158
ping -c 3 192.168.110.158
```

---

# WHY THE RECEIVER STAYS UP (the point of the demo)

- UDP-port and single-IP drops are narrow — they never touch SSH/ICMP/mgmt.
- The subnet block whitelists BOTH the legit server AND the receiver's own IP,
  so replies keep flowing.
- Every flood is offloaded to the eSwitch, so attack volume is dropped in
  silicon and never reaches the host CPU — the server keeps serving.
- Ramp-up (moderate → verify offload → escalate) means you never hit the box
  with full flood volume in software.
