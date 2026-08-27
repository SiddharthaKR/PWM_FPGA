"""Simulate red_pitaya_trigger_block.v in isolation: feed a multi-cycle sine
wave, arm a positive-slope threshold trigger with hysteresis and auto-rearm,
and show trig_o (replicated on dat_o via output_select=TTL) pulsing once per
period, right where the input crosses the threshold going up.

Run: python run_trigger.py
"""

import pathlib
import sys

import numpy as np

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE / "common"))

import plotting  # noqa: E402
import regbridge  # noqa: E402
import runner  # noqa: E402
import stimlib  # noqa: E402
import vcdtools  # noqa: E402

FS = 125e6
DUT_FILES = ["red_pitaya_trigger_block.v", "red_pitaya_filter_block.v", "red_pitaya_lpf_block.v"]
TB_FILE = HERE / "tb_trigger.v"
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)

THRESHOLD = 0.2
HYSTERESIS = 0.03


def write_cfg(workdir):
    lines = [
        f"{regbridge.TrigRegs.ADDR_TRIGGER_SOURCE:04x} {1:08x}",  # bit0=1: positive slope
        f"{regbridge.TrigRegs.ADDR_OUTPUT_SELECT:04x} {0:08x}",  # TTL
        f"{regbridge.TrigRegs.ADDR_THRESHOLD:04x} {regbridge.TrigRegs.volts(THRESHOLD):08x}",
        f"{regbridge.TrigRegs.ADDR_HYSTERESIS:04x} {regbridge.TrigRegs.volts(HYSTERESIS):08x}",
        f"{regbridge.TrigRegs.ADDR_AUTO_REARM:04x} {1:08x}",  # bit0=auto_rearm
        f"{regbridge.TrigRegs.ADDR_ARM:04x} {0:08x}",  # any write arms it (write LAST)
    ]
    (workdir / "cfg.hex").write_text("\n".join(lines) + "\n")


def demo():
    n = 4000
    samples = stimlib.sine(n, amplitude=0.5, cycles=6)
    workdir = OUT / "trigger"
    workdir.mkdir(parents=True, exist_ok=True)
    stimlib.to_hex_file(workdir / "stimulus.hex", samples)
    write_cfg(workdir)
    vcd_path = runner.compile_and_run(
        DUT_FILES, TB_FILE, workdir, defines={"N_SAMPLES": n}, include_dirs=[HERE]
    )
    parsed = vcdtools.parse_vcd(vcd_path)

    clk = parsed[vcdtools.find(parsed, ".clk")]
    t_raw = clk["times"][clk["values"] == 1]
    ts = clk["timescale_s"]
    time_us = (t_raw.astype(np.float64) - t_raw[0]) * ts * 1e6

    dat_i = vcdtools.decode_fixed(vcdtools.hold_sample(parsed[vcdtools.find(parsed, ".dat_i")], t_raw), 14, 2**13)
    trig_o = vcdtools.hold_sample(parsed[vcdtools.find(parsed, ".trig_o")], t_raw).astype(np.float64)

    plotting.plot_traces(
        [
            ("input dat_i (sine)", time_us, dat_i, "volts (norm)"),
            ("trig_o (1-cycle pulse per crossing)", time_us, trig_o, "0/1"),
        ],
        OUT / "trigger_demo.png",
        title=f"Trigger block: positive-slope threshold={THRESHOLD}V, hysteresis={HYSTERESIS}V",
        xlabel="time [us]",
    )

    n_pulses = int(np.sum(np.diff(trig_o.astype(int)) == 1))
    print(f"[Trigger] number of trig_o pulses detected: {n_pulses} (expect close to 6, one per sine cycle)")
    # every pulse should occur while dat_i is near the rising edge through THRESHOLD
    pulse_idx = np.where(np.diff(trig_o.astype(int)) == 1)[0] + 1
    at_threshold_ok = np.all(np.abs(dat_i[pulse_idx] - THRESHOLD) < 3 * HYSTERESIS)
    ok = (4 <= n_pulses <= 7) and at_threshold_ok
    print(f"[Trigger] pulse-count and threshold-crossing sanity check: {'PASS' if ok else 'FAIL'}")


if __name__ == "__main__":
    demo()
