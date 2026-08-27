"""Simulate red_pitaya_asg.v in isolation: program a sine table into channel
A's waveform RAM, configure it to free-run (trig_src=always) and wrap
continuously at a chosen playback frequency, then capture dac_a_o and check
it reproduces the programmed table each period.

Run: python run_asg.py
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
DUT_FILES = [
    "red_pitaya_asg.v",
    "red_pitaya_asg_ch.v",
    "red_pitaya_adv_trigger.v",
    "red_pitaya_prng.v",  # defines red_pitaya_prng_xor
]
TB_FILE = HERE / "tb_asg.v"
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)

TABLE_LEN = 1024
PLAY_FREQ_HZ = 100e3


def write_cfg(workdir, table):
    lines = [
        f"{regbridge.AsgRegs.ADDR_AMP_DC:04x} {regbridge.AsgRegs.amp_word(1.0):08x}",
        f"{regbridge.AsgRegs.ADDR_SIZE:04x} {regbridge.AsgRegs.size_word(TABLE_LEN):08x}",
        f"{regbridge.AsgRegs.ADDR_OFFSET:04x} {0:08x}",
        f"{regbridge.AsgRegs.ADDR_STEP:04x} {regbridge.AsgRegs.step_word(PLAY_FREQ_HZ, TABLE_LEN, FS):08x}",
    ]
    for i, sample in enumerate(table):
        addr = regbridge.AsgRegs.ADDR_TABLE_BASE + 4 * i
        raw = int(sample) & 0x3FFF
        lines.append(f"{addr:08x} {raw:08x}")
    # control word (trig_src=always-on, wrap=periodic) written LAST so the
    # generator only starts free-running once the table/size/step are valid
    lines.append(f"{regbridge.AsgRegs.ADDR_CTRL:04x} {regbridge.AsgRegs.ctrl_word():08x}")
    (workdir / "cfg.hex").write_text("\n".join(lines) + "\n")


def demo():
    table = stimlib.sine(TABLE_LEN, amplitude=1.0, cycles=1)

    workdir = OUT / "asg"
    workdir.mkdir(parents=True, exist_ok=True)
    write_cfg(workdir, table)

    n_cycles_period = int(round(FS / PLAY_FREQ_HZ))
    n_samples = n_cycles_period * 4  # capture ~4 playback periods

    vcd_path = runner.compile_and_run(
        DUT_FILES, TB_FILE, workdir, defines={"N_SAMPLES": n_samples}, include_dirs=[HERE]
    )
    parsed = vcdtools.parse_vcd(vcd_path)

    clk = parsed[vcdtools.find(parsed, ".clk")]
    t_raw = clk["times"][clk["values"] == 1]
    ts = clk["timescale_s"]
    time_us = (t_raw.astype(np.float64) - t_raw[0]) * ts * 1e6

    dac_a = vcdtools.decode_fixed(vcdtools.hold_sample(parsed[vcdtools.find(parsed, ".dac_a_o")], t_raw), 14, 2**13)

    plotting.plot_traces(
        [("ASG channel A output (dac_a_o)", time_us, dac_a, "volts (norm)")],
        OUT / "asg_playback.png",
        title=f"ASG: {TABLE_LEN}-sample sine table played back at {PLAY_FREQ_HZ/1e3:.0f} kHz",
        xlabel="time [us]",
    )

    # sanity check: measured period (via zero-crossing spacing) should match
    # 1/PLAY_FREQ_HZ, and peak amplitude should be close to full scale (gain=1.0)
    rising_zero_idx = np.where((dac_a[:-1] < 0) & (dac_a[1:] >= 0))[0]
    if len(rising_zero_idx) >= 2:
        periods_us = np.diff(time_us[rising_zero_idx])
        measured_period_us = np.median(periods_us)
    else:
        measured_period_us = float("nan")
    expected_period_us = 1e6 / PLAY_FREQ_HZ
    peak = np.max(np.abs(dac_a))
    print(
        f"[ASG] measured period={measured_period_us:.4f} us, expected={expected_period_us:.4f} us, "
        f"peak amplitude={peak:.3f}"
    )
    ok = (
        abs(measured_period_us - expected_period_us) < 0.02 * expected_period_us
        and 0.9 < peak <= 1.0
    )
    print(f"[ASG] playback period/amplitude sanity check: {'PASS' if ok else 'FAIL'}")


if __name__ == "__main__":
    demo()
