# PyRPL FPGA block simulation harness

Icarus Verilog + Python harness for simulating PyRPL's individual FPGA DSP
blocks in isolation (and the DSP crossbar that ties them together), driving
them with Python-generated stimulus and visualizing internal + output
signals with matplotlib. Everything here is exploration tooling for
`pyrpl/fpga/rtl/` -- nothing in the actual repository is modified.

## What each module does

The DSP crossbar (`red_pitaya_dsp.v`) is the piece that makes PyRPL's FPGA
different from stock Red Pitaya firmware: instead of a fixed ADC->PID->DAC
wiring, every module below can take its input from *any* other module's
output and sum its own output onto either DAC -- see the crossbar row.

| Module | RTL file | What it does |
|---|---|---|
| **PID** | `red_pitaya_pid_block.v` | Proportional-Integral-(Derivative) feedback controller. Computes `error = filtered_input - setpoint`, sums the P/I/D terms, saturates the result. The core building block for closing a feedback loop (e.g. stabilizing a laser's frequency or intensity against a reference). |
| **IQ** | `red_pitaya_iq_block.v` (+ NCO/demodulator/modulator submodules) | Lock-in amplifier: a numerically-controlled oscillator (NCO) generates sine/cosine at a programmable frequency, multiplies it against the input to demodulate (extract the amplitude/phase of a component at that frequency), and can also modulate a signal back out. Used for PDH-style error-signal generation, network-analyzer-style transfer function measurement, and phase detection (PFD mode). |
| **IIR** | `red_pitaya_iir_block.v` | General-purpose configurable digital filter (biquad-style: up to 14 independent stages, coefficients loaded into a small RAM rather than fixed in hardware). Used to add extra frequency-shaping/compensation in series with a PID, beyond what the PID's own fixed P/I/D structure can do. |
| **Trigger** | `red_pitaya_trigger_block.v` | Threshold + hysteresis edge/level detector (with an internal phase pass-through output). Produces a one-cycle trigger pulse used to synchronize or gate other modules, or timestamp an event -- independent of, and simpler than, the Scope's own trigger logic. |
| **ASG** (arbitrary signal generator) | `red_pitaya_asg.v` + `red_pitaya_asg_ch.v` | Plays back a programmable waveform table (a small RAM you write sample-by-sample) through a phase accumulator, at a chosen frequency, with amplitude/offset scaling and trigger/burst/repetition control. The source for synthetic test signals fed into the rest of the chain, or straight out to a DAC. |
| **Scope** | `red_pitaya_scope.v` (+ `red_pitaya_dfilt1.v` compensation filter) | ADC acquisition buffer: continuously writes (optionally decimated/averaged) samples into a circular RAM, with arm/trigger logic (software, threshold, or external) that freezes pre- and post-trigger data in place for readback -- the oscilloscope. |
| **DSP crossbar** | `red_pitaya_dsp.v` | The routing/summing switchboard tying everything above together: each module's `input_select` register picks which other module's output feeds it, and each module's `output_select` register picks which DAC(s) its own output gets summed onto. This is what turns the fixed-function blocks above into an arbitrarily reconfigurable signal-processing chain. |

## Signal flow

### On real hardware (`red_pitaya_top.v`, not part of this harness)

```
                        PS (ARM/Linux, via MonitorClient/monitor_server)
                                          |
                                system bus (32-bit addr/data)
                                          |
                         +-----------------------------------+
  ADC pins ------------->|                                   |-------> PWM pins
  (2ch, 14-bit, sign-    |          red_pitaya_dsp.v          |         (slow DAC /
   converted in          |            (the crossbar)          |          LED-driver
   red_pitaya_top.v)     |                                    |            style)
                         |   PID0-2 / Trig / IIR / IQ0-2,      |
                         |   each with input_select +          |-------> DAC pins
                         |   output_select (see routing        |         (2ch, summed)
                         |   table below)                      |
                         +-----------------------------------+
                             ^              |            ^
                             |              v            |
                        ASG1 / ASG2   Scope1 / Scope2   trig_dsp_i
                        (waveform      (taps whatever    (from the
                         generator,     is currently      Trigger
                         feeds the      routed there,      module;
                         crossbar AND   for capture)        can arm
                         drives the                         the Scope)
                         DAC directly)
```

Every module (PID0-2, Trig, IIR, IQ0-2) sits *inside* the crossbar as one of
its numbered slots; ADC1/ADC2/DAC1/DAC2/ASG1/ASG2 are additional numbered
slots representing the chip pins themselves. Selecting a module's input is
"pick a slot number"; selecting its output destination sums it onto DAC1
and/or DAC2 alongside whatever every *other* module currently routed there
is also producing.

### What this harness actually drives

Each `tb_<block>.v`/`tb_<block>_live.v` instantiates **one block standalone**
and feeds it synthetic ADC-equivalent samples directly on its `dat_i` (or
`adc_a_i`, `dac_a_o`, ...) port -- the pin-level sign-conversion, PLL/clock
generation, and PS/AXI plumbing in `red_pitaya_top.v` and `red_pitaya_ps.v`
aren't simulated (and don't need to be; they don't affect the DSP math).
`tb_dsp_top.v`/`tb_dsp_top_live.v` are the exception: they instantiate the
**actual crossbar itself**, so `input_select`/`output_select` writes there
exercise the real routing/summing logic, exactly as `run_dsp_crossbar.py`
and `live_dsp_crossbar.py` do.

### Crossbar routing table (`red_pitaya_dsp.v`, mirrored in `regbridge.DspCrossbarRegs`)

Module `input_select` (address `module*0x10000 + 0x00`) is set to one of
these numbers to choose that module's *input* source:

| Number | Source | Number | Source |
|---|---|---|---|
| 0 | PID0 output | 8 | ASG1 |
| 1 | PID1 output | 9 | ASG2 |
| 2 | PID2 output | 10 | ADC1 (channel A in) |
| 3 | Trigger output | 11 | ADC2 (channel B in) |
| 4 | IIR output | 12 | DAC1 (channel A out -- lets you chain onto what's already summed there) |
| 5 | IQ0 output | 13 | DAC2 (channel B out) |
| 6 | IQ1 output | 15 | off (constant 0) |
| 7 | IQ2 output | | |

Module `output_select` (address `module*0x10000 + 0x04`) is a 2-bit field:
`0`=off, `1`=DAC1, `2`=DAC2, `3`=both (summed with every other module also
routed there).

### Worked example: ADC1 -> PID0 -> DAC1

1. Write `input_select` at address `0x00000` (PID0's region, offset `0x00`)
   to `10` (ADC1) -- PID0 now reads `dat_a_i` as `input_signal[PID0]`.
2. Write PID0's own `p`/`i`/`setpoint` registers (offset `0x108`/`0x10C`/`0x104`
   within that same `0x00000`-based region) -- computes `output_direct[PID0]`.
3. Write `output_select` at address `0x00004` to `1` (OUT1) -- PID0's
   `output_direct` is now added into the tree-adder feeding `dat_a_o`.
4. `dat_a_o` (DAC1) settles to `p * ADC1` a few pipeline cycles later (same
   latency behavior documented for the standalone PID block in `run_pid.py`).

This is exactly what `live_dsp_crossbar.py`'s `route()` helper does, and
what `regbridge.DspCrossbarRegs.addr_input_select`/`addr_output_select`/
`addr_local` compute the addresses for.

## Requirements

- `iverilog` / `vvp` (Icarus Verilog) on PATH
- Python with `numpy`, `matplotlib`

No other dependencies -- the VCD parser (`common/vcdtools.py`) is
hand-written, no `pyvcd`/`vcdvcd` needed.

## Layout

```
common/            shared Python + Verilog infrastructure
  tb_clock.vh        clock (125MHz)/reset generation tasks
  tb_bus16.vh        write_reg16/read_reg16 tasks (pid/iq/iir/trigger's 16-bit addr bus)
  tb_bus32.vh        write_reg32/read_reg32 tasks (asg/scope/dsp-top's 32-bit sys bus)
  tb_events16.vh     event-log interactive-session loop, 16-bit-bus DUTs (see below)
  tb_events32.vh     event-log interactive-session loop, 32-bit-bus DUTs (see below)
  stimlib.py         stimulus generators (step, sine, chirp, noise, ...) + $readmemh writer
  regbridge.py       physical-units <-> raw fixed-point register encoding, per block
  runner.py          iverilog/vvp invocation wrapper (compile() / run_vvp() / compile_and_run())
  session.py         Session: interactive write/read/poke/probe API (see below)
  vcdtools.py        minimal VCD parser + two's-complement decode
  plotting.py        matplotlib helpers (time-domain traces, Bode plots)
patched_rtl/       simulation-only patched copies of 2 files with real RTL bugs
                   that block Icarus elaboration/simulation -- see its README.md.
                   The actual pyrpl/fpga/rtl/ files are never touched.
tb_<block>.v         batch testbench per block, run_<block>.py the matching driver
tb_<block>_live.v    interactive-session testbench per block, live_<block>.py the matching demo
out/               generated stimulus/cfg/events/results/dump.vcd/*.png per run (scratch, safe to delete)
```

## Running

```
python run_pid.py            # step response + Bode vs analytic model
python run_iq.py              # lock-in demodulation, on-resonance vs detuned
python run_iir.py             # one-pole low-pass step response + Bode
python run_trigger.py         # threshold/hysteresis edge trigger pulses
python run_asg.py             # arbitrary waveform table playback
python run_scope.py           # capture + readback vs driven input
python run_dsp_crossbar.py    # full crossbar: routing + summing across DACs
```

Each prints a `[Block] ... sanity check: PASS/FAIL` line and saves one or
more PNGs to `out/`.

## Interactive sessions

See `WORKFLOW.md` for a hands-on, copy-pasteable walkthrough of what to
type at the prompt. The rest of this section is the design/protocol
reference.

The scripts above are batch demos: generate all stimulus up front, run once,
plot. That doesn't match how you'd actually explore a module through
PyRPL's real GUI/notebook -- write one register, read it back, poke an
input, watch a signal, try a different address, repeat. `live_<block>.py`
gives you exactly that, as a plain Python object:

```python
python -i live_pid.py
# sim.write(regbridge.PidRegs.ADDR_KP, regbridge.PidRegs.p(0.8))
# sim.poke('dat_i', regbridge.encode_signed(0.3, 14, 2**13))
# sim.run(10)
# sim.probe('error')
# sim.read(0x1f0)   # any address, documented or not
```

Run any `live_<block>.py` with `python -i` (or paste its contents into a
notebook) and the `sim` object stays alive afterward for you to keep poking
at the prompt.

**How it works** (see `common/session.py`'s docstring for the full
rationale): each call appends one event to a growing, ordered log and
*replays the whole simulation from time 0* through the updated log every
time. Since RTL simulation is deterministic, this gives results identical
to a real persistent session, while reusing every other piece of this
harness (`runner.py`, the bus tasks, `vcdtools`/`plotting.py` for a full
waveform review afterward via `sim.vcd_path()`) completely unchanged. The
`iverilog` compile happens once per `Session`; only the cheap `vvp` run
repeats per call.

**Session API** (`common/session.py`):
- `sim.write(addr, data)` / `sim.read(addr)` -- any address, no restriction
  to documented registers. This is what answers "what if I poke a custom
  address."
- `sim.poke(name, value)` / `sim.probe(name)` -- named testbench-level
  inputs/signals (input pins, or *any* internal DUT signal), via the small
  integer-code table documented at the top of each `tb_<block>_live.v`.
- `sim.snapshot(names)` -- several probes in one replay.
- `sim.run(n_cycles)` -- advance time, holding current pokes constant.
- A probe/read of a signal that is currently undefined (X) in the RTL
  returns `None` rather than raising -- see finding #6 below; decode it
  with `session.decode(raw, bits, norm)`, which passes `None` through.

**Event-log wire format** (`events.txt`, regenerated in full on every
call, one event per line, always 3 whitespace-separated hex fields):

| Line | Meaning |
|---|---|
| `W <addr> <data>` | register write |
| `R <addr> 0` | register read -> appended to `results.txt` |
| `P <code> <value>` | poke a named input (see the testbench's code table) |
| `Q <code> 0` | probe a named signal -> appended to `results.txt` |
| `N <n> 0` | advance `n` clock cycles |

`results.txt` accumulates one line per `R`/`Q` event in the log, in order;
`Session` always takes the newest one(s) for the call that just ran.

**Wiring up a genuinely new/custom module**: copy the nearest
`tb_<block>_live.v`, swap in the new DUT's instantiation and port names,
and write a small `poke_signal`/`probe_signal` task pair (an `if`/`case` on
an integer code -> your signal, following the pattern already in every
`tb_<block>_live.v`). Nothing in `common/tb_events16.vh`, `tb_events32.vh`,
or `session.py` needs to change -- pick whichever bus width the new
module actually uses (see `common/tb_bus16.vh` vs `tb_bus32.vh`) and go.

## What each demo shows

| Script | DUT | What it proves |
|---|---|---|
| `run_pid.py` | `red_pitaya_pid_block.v` | Step response (error/integrator/output traces) + swept-frequency Bode plot matching `Pid._transfer_function` (reimplemented in `regbridge.PidRegs.transfer_function`) to ~1%. |
| `run_iq.py` | `red_pitaya_iq_block.v` + NCO/demod/mod submodules | Lock-in amplifier behavior: demodulated DC level is large when the NCO matches the input tone, ~1000x smaller when detuned. |
| `run_iir.py` | `red_pitaya_iir_block.v` | A configured one-pole low-pass's step response and Bode magnitude match the analytic `H(z)=(1-a)/(1-a z^-1)` model closely (see effective-sample-rate note below). |
| `run_trigger.py` | `red_pitaya_trigger_block.v` | Positive-slope threshold+hysteresis trigger fires exactly once per input cycle, right at the crossing. |
| `run_asg.py` | `red_pitaya_asg.v` + `_ch.v` | A programmed waveform table plays back continuously at the requested frequency and amplitude. |
| `run_scope.py` | `red_pitaya_scope.v` | Captured ring-buffer readback (via real sys-bus reads, not VCD) reproduces a driven chirp. |
| `run_dsp_crossbar.py` | `red_pitaya_dsp.v` (the whole crossbar) | Two independently-configured PID modules routed to the *same* DAC sum correctly; a third routed to the other DAC stays independent. |

Each block also has a `live_<block>.py` interactive counterpart (see
"Interactive sessions" above) demonstrating the same DUT through
write/poke/probe calls instead of a batch stimulus file -- e.g.
`live_pid.py` changes `p` *mid-session* (impossible in the batch version)
and shows `dat_o` respond; `live_dsp_crossbar.py` does the same for one
routed module while confirming the other DAC stays untouched;
`live_scope.py` reads the capture buffer back with plain `sim.read(addr)`
calls at the same addresses `run_scope.py` uses.

## Findings worth knowing before extending this

These came out of actually simulating the RTL, not just reading it -- keep
them in mind if you add more scenarios:

1. **`red_pitaya_pid_block.v`, DERIVATIVE=0 (the default)**: the `kd_reg_s`
   signal referenced by `pid_sum` is a dead, never-driven net (shadowed by a
   same-named signal in an unused generate branch). Simulates as `X` forever
   in Icarus; harmless in real synthesis. `tb_pid.v` works around it with a
   one-time hierarchical deposit; `patched_rtl/red_pitaya_pid_block.v` fixes
   it at the source (needed for `tb_dsp_top.v`, which has 3 instances).
2. **`red_pitaya_iq_block.v`**: the NCO's phase accumulator only zeros
   itself when its `on` input (tied to `sync_i`) is pulsed through 0 -- if
   held high from the start of a testbench, `phase` stays permanently `X`.
   This matches pyrpl's own `DspModule._synchronize()` behavior
   (`pyrpl/hardware_modules/dsp.py`), which exists for exactly this reason.
   Also: the demodulated readback (`signal_o`, `output_select==QUADRATURE`)
   is scaled by gain register **g3** ("quadrature_factor"), not g1/g2
   ("amplitude", which instead scale the modulator's AM output `dat_o`) --
   easy to miss since both are named similarly.
3. **`red_pitaya_iir_block.v`**: with `loops=1` (a single active biquad, no
   time-multiplexing with other stages), the shared multiply-accumulate
   pipeline has a read-before-write hazard on its own feedback history: a
   single active stage only advances by one true filtered sample every 3
   raw clock cycles, not every cycle. `regbridge.IirRegs.EFFECTIVE_SAMPLE_DIVIDER`
   captures this; both the coefficient design and the analytic comparison
   model account for it. Also contains an unrelated leftover debug
   `$fwrite` to an undeclared `fdebug` identifier that blocks Icarus
   elaboration entirely -- see `patched_rtl/README.md`.
4. **`red_pitaya_scope.v`**: `pretrig_ok` requires either a large fraction of
   a full buffer's worth of pretrigger samples accumulated, *or* `set_dly >=
   2**RSZ` (16384) to bypass that requirement. Without the latter, a short
   testbench run can never satisfy a trigger. The ADC-to-buffer path also
   runs through `red_pitaya_dfilt1.v` (a configurable compensation filter,
   left at its default coefficients here), which adds a small, frequency-
   dependent group delay -- visible as slowly growing (not constant) error
   between driven input and read-back buffer on a chirp stimulus.
5. **General elaboration gotcha**: an include (`` `include "common/tb_*.vh" ``)
   containing `task`/`always` statements must appear *inside* the `module
   ... endmodule` block, not before it -- easy to get backwards since the
   include looks like a header.
6. **`red_pitaya_iq_block.v`, found via `live_iq.py`**: probing `signal_o`
   sample-by-sample (poke `dat_i`, run 1 cycle, probe) shows it occasionally
   reads back undefined (X) mid-stream, even after the documented sync
   pulse -- something the smooth, every-cycle `$readmemh` stimulus in
   `run_iq.py`'s batch test never surfaces (that harness's VCD-array parser
   also silently maps X to 0 in aggregate plots/DFTs, where a few isolated
   cycles don't move the result enough to notice). Root cause not fully
   pinned down; treated as a real property of probing raw pipelined RTL
   state at arbitrary cycle boundaries rather than chased further -- see
   `Session`'s handling of this (returns `None`, doesn't crash) rather than
   assuming every probe returns a defined value.

## Adding a new scenario or block

(For an *interactive* session on a new module instead of a batch demo, see
"Wiring up a genuinely new/custom module" under Interactive sessions above
-- same idea, `tb_<block>_live.v` instead of `tb_<block>.v`.)

1. Copy the closest existing `tb_<block>.v` + `run_<block>.py` pair.
2. Get the real register map from the RTL directly (`grep -n "addr==" <file>.v`
   or `sys_addr\[19:0\]==`), not just from the Python driver in
   `pyrpl/hardware_modules/` -- as found above, the two aren't always
   perfectly aligned (dead registers, renamed fields, etc.), and only the
   RTL is authoritative for what a testbench needs to drive.
3. Use `regbridge.encode_signed`/`decode_signed` for any physical-unit
   register (mirrors `pyrpl/attributes.py`'s `FloatRegister` convention:
   value = signed(raw)/norm) instead of reinventing fixed-point math.
4. `$dumpvars(0, tb_<block>)` gives you every internal signal for free --
   use `vcdtools.find(parsed, ".signal_name")` to locate one by its leaf
   name without knowing the exact hierarchy path.
5. Compile early and often -- several of the above findings only showed up
   by actually running the simulation and staring at "why is this signal
   stuck at 0/X", not from reading the Verilog alone.
