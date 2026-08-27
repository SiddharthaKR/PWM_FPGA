"""Interactive exploratory session against red_pitaya_iir_block.v.

Run with `python -i live_iir.py`. Configures the same one-pole low-pass as
run_iir.py, then pokes a step onto dat_i and watches dat_o settle sample by
sample -- with `loops=1`, remember dat_o only actually advances once every 3
raw clock cycles (README.md finding #3), so probes are spaced 3 RUN cycles
apart here to see a genuinely new value each time.
"""

import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE / "common"))

import regbridge  # noqa: E402
import session  # noqa: E402

DUT_FILES = [
    str(HERE / "patched_rtl" / "red_pitaya_iir_block.v"),
    "red_pitaya_filter_block.v",
    "red_pitaya_lpf_block.v",
    "red_pitaya_saturate.v",
    "red_pitaya_product_sat.v",
]
TB_FILE = HERE / "tb_iir_live.v"
WORKDIR = HERE / "out" / "iir_live"

POKE_CODES = {"dat_i": 0}
PROBE_CODES = {"dat_o": 0}

FC_HZ = 500e3

if __name__ == "__main__":
    sim = session.Session(
        DUT_FILES, TB_FILE, WORKDIR, poke_codes=POKE_CODES, probe_codes=PROBE_CODES, include_dirs=[HERE]
    )

    coeffs = regbridge.IirRegs.onehot_pole_lowpass(FC_HZ)
    for name, value in coeffs.items():
        sim.write(regbridge.IirRegs.coeff_addr(0, name), regbridge.IirRegs.coeff_raw(value))
    sim.write(regbridge.IirRegs.ADDR_LOOPS, 1)
    sim.write(regbridge.IirRegs.ADDR_ON_SHORTCUT, 1)  # on=1, shortcut=0

    sim.poke("dat_i", regbridge.encode_signed(0.4, 14, 2**13))
    print(f"stepped dat_i to 0.4V, one-pole LPF fc={FC_HZ/1e3:.0f}kHz, loops=1 (3 cycles/sample):")
    for k in range(10):
        sim.run(3)
        dat_o = session.decode(sim.probe("dat_o"), 14, 2**13)
        print(f"  sample {k + 1:2d}: dat_o={dat_o}")

    print(f"\nfull waveform history: {sim.vcd_path()}")
    print("session object 'sim' is still live")
