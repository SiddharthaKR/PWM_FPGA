# ZCU208 DDS + System ILA Sample — Build & Bench-Test Reference

**Base design:** Xilinx "Zynq UltraScale+ RFSoC Example Design: ZCU208 — DDS Compiler for DAC and System ILA for ADC Capture" (deck: *ZCU208_dds_ila_2020p2*).
**What it does:** DDS Compiler plays a 10 MHz sine → DAC Tile 228 Ch0 → external coax loopback → ADC Tile 226 Ch0 → System ILA capture. Fs = 1.47456 GHz, interpolation/decimation ×8, AXI-Stream at 184.32 MHz. Bare-metal (standalone) app on `psu_cortexa53_0`.

> **Tool version note:** The deck is written for **2020.2**. This build was done in **Vivado/Vitis 2021.2**. See "Divergences from the deck" below — slide numbers still map, with the noted differences.

---

## Part 1 — Offline build (PC only, no board) — COMPLETED

All steps below were done at the home machine. None require the board.

### 1.1 Vivado — bitstream
- Opened the 2020.2 project in **Vivado 2021.2** → prompted **Upgrade IP** (DDS Compiler 6.0, System ILA 1.1, RF Data Converter 2.4 → 2.5).
- Re-ran synthesis + implementation → **Generate Bitstream**.
- *(Deck slides 10–11, done in 2021.2 instead of 2020.2.)*

### 1.2 Export hardware → XSA
- **File → Export → Export Hardware → Include bitstream** → `design_1_wrapper.xsa`.
- *(Deck slides 13–14.)*

### 1.3 Create platform (INLINE route — divergence)
- The standalone **Platform Project** wizard would not open on the Linux box, so the platform was created **inside the Application Project wizard**:
  - **File → New → Application Project → "Create a new platform from hardware (XSA)"** tab → browsed to `design_1_wrapper.xsa`.
  - OS = **standalone**, processor = **psu_cortexa53_0**, arch = **64-bit**, **Generate boot components** = checked (creates FSBL).
- Result: platform is named **`design_1_wrapper`** (not `ZCU208` as in the deck) — cosmetic only.
- *(Replaces deck slides 16–19; platform name differs — substitute `design_1_wrapper` wherever the deck says `ZCU208`.)*

### 1.4 Enable libmetal + build platform
- Opened `platform.spr` → `psu_cortexa53_0 → standalone → Board Support Package → Modify BSP Settings` → ticked **libmetal** → OK.
  - **Why:** the RF Data Converter driver (`xrfdc`) is built on libmetal; without it the app won't compile (`metal/*.h` missing).
- Platform showed **"(Out-of-date)"** → right-click platform → **Build Project** to recompile with libmetal.
- *(Deck slide 21.)*

### 1.5 Create application + import sources
- App project **`RFSOC`** (Empty Application, C) on the platform, target `psu_cortexa53_0`, domain `standalone on psu_cortexa53_0`.
- Right-click `RFSOC/src` → **Import Sources** → from kit `src` folder → Select All (`main.c`, `xrfclk*`, `LMK_display`, `LMX_display`, `lscript.ld`, headers) → **Yes To All** on overwrite prompt.
- *(Deck slides 24–30. Left "Create top-level folder" unchecked to avoid `src/src` nesting.)*

### 1.6 Build → RFSOC.elf
- Right-click `RFSOC` [Application] → **Build Project** → produced **`RFSOC.elf`**.
- *(Deck slides 31–32. If `xrfclk`/`xrfdc` API errors appear, they are 2021.2-vs-2020.2 driver drift — match calls to the 2021.2 driver headers in the BSP.)*

### 1.7 Create boot image → BOOT.bin
- **Xilinx → Create Boot Image** → import generated BIF → **Create Image** → `BOOT.bin`.
- **Verify the partition list contains all three:** bootloader (`fsbl.elf`), bitstream (`design_1_wrapper.bit`), and `RFSOC.elf`.
- *(Deck slides 49–50. Needed because the on-site machine has no Vitis — SD boot is the only way to run there.)*

### 1.8 Pre-fill Run Configuration (JTAG route — for later, on a machine WITH Vitis)
- Right-click `RFSOC` → **Run As → Run Configurations** → double-click **Single Application Debug** → **Target Setup** tab:
  - Bitstream = `design_1_wrapper.bit`, FSBL auto-filled.
  - Check: **Reset entire system**, **Reset APU**, **Program FPGA**, **Use FSBL flow**, **Initialize using FSBL** → **Apply**.
- *(Deck slides 35–37. Cannot **Run** without a board + Vitis — this is for a future Vivado-equipped session, e.g. to view the ILA waveform.)*

---

## Part 2 — On-site test (tomorrow) — SD-CARD BOOT

> **Constraint:** the site has **Linux but NO Vivado/Vitis**. The JTAG/Vitis "Run" route (slides 35–38) and the Hardware Manager ILA waveform (slides 40–47) are **NOT available there.** Verification is via **SD-card boot** + serial terminal output only.

### 2.1 Bring with you
- [ ] ZCU208 board + CLK104 + XM655 (usually already on the board at the site — confirm CLK104 and XM655 are seated)
- [ ] Power supply for the board
- [ ] 1× SMA coax cable (loopback)
- [ ] **SD card (FAT32)** with **`BOOT.bin`** at its root — plus a **spare copy of BOOT.bin on a USB stick**
- [ ] (Optional) 2nd SD card as backup
- [ ] USB cable (board ↔ site PC, for the serial console)
- [ ] (Optional insurance) workspace zip + XSA — unusable without Vitis, but zero cost to carry

### 2.2 SD card prep
1. Format SD card as **FAT32**.
2. Copy **`BOOT.bin`** to the **root** of the card.

### 2.3 Board hardware setup
1. Confirm **CLK104** and **XM655** cards seated.
2. **Loopback cable:** DAC **Tile 228 Ch0** OUT → ADC **Tile 226 Ch0** IN, both on the XM655 **LF (low-frequency) balun** SMAs. *(Deck slides 2, 9.)*
3. Insert the SD card into the board's SD slot. *(Deck slide 51.)*
4. **SW2 = on, off, off, off** → **SD-card boot mode.**
   - ⚠️ This is the **opposite** of JTAG mode (on,on,on,on). Wrong setting = no boot.
5. Connect USB cable → site Linux PC.

### 2.4 Serial terminal on the site PC
1. List serial devices:
   ```bash
   ls /dev/ttyUSB*
   ```
   (Four appear: `ttyUSB0`–`3`. PS UART is usually the **2nd**, `ttyUSB1`.)
2. Identify the PS UART if unsure:
   ```bash
   dmesg | grep ttyUSB
   ```
3. Open it at **115200 8-N-1**:
   ```bash
   sudo screen /dev/ttyUSB1 115200
   ```
   (Quit `screen` later: `Ctrl+A` then `K` then `y`. Permission denied? `sudo usermod -aG dialout $USER`, then log out/in.)

### 2.5 Power on + verify
Power on the board. It boots FSBL → bitstream → `RFSOC.elf`. Expected terminal output *(deck slide 39)*:

```
Xilinx Zynq MP First Stage Boot Loader
...
Hello RFSoC World!
RFDC IP Version: 2.x
Configuring the data converter clocks...
Clk settings read from LMK ...   DCLKout00 ... 184320KHz ...
=== Metal log enabled ===
...
The Power-on sequence step. 0xF is complete.
   DAC Tile0 Power-on Sequence Step: 0x0000000F
   ADC Tile2 Power-on Sequence Step: 0x0000000F
Data Converter start up is complete!
------------ Startup Complete ----------------
```

**PASS criteria:**
- Both tiles report **`0x0000000F`** (all 4 power-up sub-steps done).
- LMK dump shows **184320 KHz** on the DCLK outputs (not blanks).

### 2.6 What you CANNOT verify on-site
- The **10 MHz sine waveform** in Hardware Manager (slides 44–47) needs Vivado → not available at the site.
- On-site, the terminal's `0xF` status **is** your proof the board + CLK104 clocking + firmware are healthy.
- To actually **see** the loopback sine, use the JTAG/Vitis flow in **Part 3** on a tools-equipped machine.

---

## Part 3 — JTAG / Vitis run + waveform verification (machine WITH Vivado + Vitis)

> Use this when you're on a **tools-equipped machine** (home bench, or if the site turns out to have the IDE). This is the **only way to see the actual 10 MHz sine waveform** — the on-site SD path (Part 2) can only confirm `0xF` on the terminal, not display the loopback signal.

### 3.1 Board setup (JTAG mode)
1. CLK104 + XM655 seated; loopback DAC **Tile 228 Ch0** → ADC **Tile 226 Ch0** on XM655 LF baluns.
2. **SW2 = on, on, on, on** → **JTAG boot mode.** ⚠️ Opposite of SD mode (on,off,off,off).
3. USB cable → host.
4. Power on.
- *(Deck slide 9.)*

### 3.2 Open serial terminal
- Same as §2.4 — open the PS UART (`/dev/ttyUSB1`) at **115200 8-N-1**, or use the **Vitis Serial Terminal** view (Window → Show View → Vitis Serial Terminal → **+** → port + 115200).
- *(Deck slide 34.)*

### 3.3 Run from Vitis
1. Right-click `RFSOC` → **Run As → Run Configurations** → the **Single Application Debug** config you pre-filled (§1.8).
2. Confirm **Target Setup**: bitstream = `design_1_wrapper.bit`, FSBL set, and checked: **Reset entire system, Reset APU, Program FPGA, Use FSBL flow, Initialize using FSBL** → **Apply**.
3. **Run.** Vitis: resets system → programs FPGA (progress bar) → runs FSBL → downloads `RFSOC.elf` → starts it.
- *(Deck slides 35–38.)*

### 3.4 Verify startup on terminal
- Same expected output as §2.5 — **both tiles `0x0000000F`**, LMK dump at **184320 KHz**, "Startup Complete".
- *(Deck slide 39.)*

### 3.5 View the waveform in Hardware Manager (the part SD boot can't do)
1. In **Vivado** → **Open Hardware Manager** → **Open Target → Auto Connect** (or Open New Target → Local server, port 3121). Should enumerate **`xczu48dr_0`** (ID `147FB093`). *(Deck slides 40–43.)*
2. In `hw_ila_1`, select the two TDATA buses:
   - `slot_0 : Conn : TDATA` → **DAC path** (DDS output going to the DAC).
   - `slot_1 : usp_rf_data_converter_1_m20_axis : TDATA` → **ADC capture** (looped-back signal).
3. Right-click the buses → **Waveform Style → Analog**. *(Deck slide 44.)*
4. Right-click → **Analog Settings → Row height = 100**, Interpolation = Linear. *(Deck slide 45.)*
5. Right-click → **Radix → Signed Decimal** (without this, the 16-bit TDATA looks like noise). *(Deck slide 46.)*
6. Set trigger to **auto-retrigger** and run.
- *(Deck slides 44–47.)*

### 3.6 PASS criteria (waveform)
- Clean **10 MHz sine** on **both** `slot_0` (DAC) and `slot_1` (ADC).
- Amplitude ≈ **±9997 / −9998 counts** (16-bit signed). *(Deck slide 47.)*
- If `slot_0` shows the sine but `slot_1` is flat → loopback SMA loose or on the wrong tile (isolates DAC-vs-cable).

### 3.7 Notes
- 10 MHz sits at the **lower edge** of the XM655 LF balun passband (10 MHz–1 GHz) → minor amplitude roll-off at the band edge is normal, not a fault.
- Nyquist **Zone 1** for both converters; 10 MHz in a 1.47456 GHz Fs is well in-band (no folding).

---

## Pre-flight checklist (do BEFORE leaving, while tools are available)

- [ ] `BOOT.bin` built and its partition list shows **fsbl + bitstream + RFSOC.elf** (§1.7)
- [ ] `BOOT.bin` copied to SD card **and** USB stick
- [ ] **Dry run if any SD card is on hand now:** flash SD → SW2 to SD mode → boot → confirm terminal shows `0xF`. This proves the SD-boot path on your own bench and removes almost all on-site risk.
- [ ] Run Configuration pre-filled + Applied (§1.8) — for later JTAG/waveform session

---

## Quick troubleshooting (on-site, no IDE)

| Symptom | Likely cause | Action |
|---|---|---|
| Nothing on terminal / no boot | SW2 in wrong mode, or bad SD/BOOT.bin | Confirm SW2 = on,off,off,off; re-flash SD; try spare BOOT.bin |
| Boots but halts before "Hello RFSoC World!" | BOOT.bin missing a partition | Use spare; on a tools machine rebuild ensuring fsbl+bit+elf |
| `0xF` not reached / LMK dump blank | CLK104 not seated or clock config failed | Reseat CLK104; power-cycle |
| Startup fine but you doubt the loopback | Can't check waveform without Vivado | Terminal `0xF` is sufficient proof of converter bring-up; defer waveform |
| `screen`: permission denied | User not in dialout group | `sudo` now; `usermod -aG dialout $USER` for later |
| Wrong `/dev/ttyUSB` (silent port) | PS UART is a different node | Try each of ttyUSB0–3; `dmesg | grep ttyUSB` |

---

## Reference: slide map (deck → your build)

| Deck slides | Topic | Your variance |
|---|---|---|
| 2–5 | Design intro, clocking (CLK104, LMK04828B) | none |
| 6–8 | DAC/ADC + converter clocking config | none |
| 9 | Board setup, JTAG mode (SW2 on×4) | JTAG route only usable on a Vitis machine |
| 10–12 | Open project, bitstream, DDS config | done in **2021.2** (IP upgrade) |
| 13–14 | Export hardware → XSA | none |
| 16–19 | Platform Project | **replaced** by inline XSA route (§1.3) |
| 20–23 | BSP libmetal, build platform | none (§1.4) |
| 24–32 | App, import sources, build ELF | none (§1.5–1.6) |
| 34–38 | Terminal, run config, JTAG run | **not usable on-site** (no Vitis) |
| 39 | Startup terminal output | **primary on-site verification** |
| 40–47 | Hardware Manager ILA waveform | **not usable on-site** (no Vivado) |
| 48–51 | Boot image + SD boot | **primary on-site path** (§1.7, Part 2) |
