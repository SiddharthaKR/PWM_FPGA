"""Interactive exploratory session against red_pitaya_iq_block.v.

Run with `python -i live_iq.py`. Demonstrates the documented sync-pulse
requirement (README.md finding #2) done by hand via poke(), then feeds a
short sine tone sample-by-sample (poke+run in a loop) and watches the
demodulated signal_o converge -- the interactive-session equivalent of
run_iq.py's on-resonance case, just built one sample at a time instead of a
single batch $readmemh stimulus file.
"""

import math
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE / "common"))

import regbridge  # noqa: E402
import session  # noqa: E402

DUT_FILES = [
    "red_pitaya_iq_block.v",
    "red_pitaya_iq_fgen_block.v",
    "red_pitaya_iq_demodulator_block.v",
    "red_pitaya_iq_modulator_block.v",
    "red_pitaya_iq_hpf_block.v",
    "red_pitaya_iq_lpf_block.v",
    "red_pitaya_pfd_block.v",
    "red_pitaya_filter_block.v",
    "red_pitaya_lpf_block.v",
    "red_pitaya_saturate.v",
    "red_pitaya_product_sat.v",
]
TB_FILE = HERE / "tb_iq_live.v"
WORKDIR = HERE / "out" / "iq_live"

POKE_CODES = {"dat_i": 0, "sync_i": 1}
PROBE_CODES = {"dat_o": 0, "signal_o": 1, "signal2_o": 2}

FS = 125e6
TONE_HZ = 1.0e6

if __name__ == "__main__":
    sim = session.Session(
        DUT_FILES, TB_FILE, WORKDIR, poke_codes=POKE_CODES, probe_codes=PROBE_CODES, include_dirs=[HERE]
    )

    sim.write(regbridge.IqRegs.ADDR_FREQUENCY, regbridge.IqRegs.frequency(TONE_HZ))
    sim.write(regbridge.IqRegs.ADDR_G3, regbridge.IqRegs.gain(1.0 / 256))  # see run_iq.py for why 1/256

    # the documented sync pulse -- do it by hand, exactly as a real user
    # exploring the module for the first time would have to
    sim.poke("sync_i", 0)
    sim.run(2)
    sim.poke("sync_i", 1)

    print("feeding a 1 MHz tone sample-by-sample and watching signal_o settle:")
    n_samples = 60
    for k in range(n_samples):
        t = k / FS
        v = 0.5 * math.sin(2 * math.pi * TONE_HZ * t)
        sim.poke("dat_i", regbridge.encode_signed(v, 14, 2**13))
        sim.run(1)
        if k % 10 == 9:
            signal_o_raw = sim.probe("signal_o")
            signal_o_v = session.decode(signal_o_raw, 14, 2**13)
            signal_o_str = "X (undefined)" if signal_o_v is None else f"{signal_o_v:+.4f}"
            print(f"  sample {k + 1:3d}: dat_i={v:+.4f}  signal_o={signal_o_str}")

    print(f"\nfull waveform history: {sim.vcd_path()}")
    print("session object 'sim' is still live")
