"""Interactive exploratory session against red_pitaya_trigger_block.v.

Run with `python -i live_trigger.py`. Arms a positive-slope threshold
trigger, then pokes dat_i through a slow ramp and watches trig_o fire right
at the crossing -- built one sample at a time instead of run_trigger.py's
batch sine sweep.
"""

import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE / "common"))

import regbridge  # noqa: E402
import session  # noqa: E402

DUT_FILES = ["red_pitaya_trigger_block.v", "red_pitaya_filter_block.v", "red_pitaya_lpf_block.v"]
TB_FILE = HERE / "tb_trigger_live.v"
WORKDIR = HERE / "out" / "trigger_live"

POKE_CODES = {"dat_i": 0, "phase1_i": 1}
PROBE_CODES = {"dat_o": 0, "signal_o": 1, "trig_o": 2}

THRESHOLD = 0.2

if __name__ == "__main__":
    sim = session.Session(
        DUT_FILES, TB_FILE, WORKDIR, poke_codes=POKE_CODES, probe_codes=PROBE_CODES, include_dirs=[HERE]
    )

    sim.write(regbridge.TrigRegs.ADDR_TRIGGER_SOURCE, 1)  # bit0=1: positive slope
    sim.write(regbridge.TrigRegs.ADDR_OUTPUT_SELECT, 0)  # TTL
    sim.write(regbridge.TrigRegs.ADDR_THRESHOLD, regbridge.TrigRegs.volts(THRESHOLD))
    sim.write(regbridge.TrigRegs.ADDR_HYSTERESIS, regbridge.TrigRegs.volts(0.03))
    sim.write(regbridge.TrigRegs.ADDR_ARM, 0)  # any write arms it

    print(f"ramping dat_i up through the {THRESHOLD}V threshold, watching trig_o:")
    for k in range(20):
        v = -0.3 + k * 0.04
        sim.poke("dat_i", regbridge.encode_signed(v, 14, 2**13))
        sim.run(1)
        trig = sim.probe("trig_o")
        marker = "  <-- FIRED" if trig == 1 else ""
        print(f"  dat_i={v:+.3f}V  trig_o={trig}{marker}")

    print(f"\nfull waveform history: {sim.vcd_path()}")
    print("session object 'sim' is still live")
