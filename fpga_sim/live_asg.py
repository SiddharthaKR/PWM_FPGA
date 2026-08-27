"""Interactive exploratory session against red_pitaya_asg.v.

Run with `python -i live_asg.py`. Programs a small sine table via ordinary
register writes (the waveform RAM is just addresses 0x10000+, same as any
other register from this session's point of view), configures free-running
playback, then RUNs a few cycles at a time and probes dac_a_o to watch it
play.
"""

import math
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE / "common"))

import regbridge  # noqa: E402
import session  # noqa: E402

DUT_FILES = [
    "red_pitaya_asg.v",
    "red_pitaya_asg_ch.v",
    "red_pitaya_adv_trigger.v",
    "red_pitaya_prng.v",
]
TB_FILE = HERE / "tb_asg_live.v"
WORKDIR = HERE / "out" / "asg_live"

POKE_CODES = {"trig_a_i": 0, "trig_b_i": 1, "trig_scope_i": 2}
PROBE_CODES = {"dac_a_o": 0, "dac_b_o": 1, "trig_out_o": 2}

TABLE_LEN = 64
FS = 125e6
PLAY_FREQ_HZ = 500e3

if __name__ == "__main__":
    sim = session.Session(
        DUT_FILES, TB_FILE, WORKDIR, poke_codes=POKE_CODES, probe_codes=PROBE_CODES, include_dirs=[HERE]
    )

    for i in range(TABLE_LEN):
        sample = round(math.sin(2 * math.pi * i / TABLE_LEN) * 8191)
        sim.write(regbridge.AsgRegs.ADDR_TABLE_BASE + 4 * i, sample & 0x3FFF)

    sim.write(regbridge.AsgRegs.ADDR_AMP_DC, regbridge.AsgRegs.amp_word(1.0))
    sim.write(regbridge.AsgRegs.ADDR_SIZE, regbridge.AsgRegs.size_word(TABLE_LEN))
    sim.write(regbridge.AsgRegs.ADDR_OFFSET, 0)
    sim.write(regbridge.AsgRegs.ADDR_STEP, regbridge.AsgRegs.step_word(PLAY_FREQ_HZ, TABLE_LEN, FS))
    sim.write(regbridge.AsgRegs.ADDR_CTRL, regbridge.AsgRegs.ctrl_word())  # last: starts free-running

    print(f"playing a {TABLE_LEN}-sample sine table at {PLAY_FREQ_HZ/1e3:.0f} kHz, watching dac_a_o:")
    for _ in range(16):
        sim.run(20)
        dac_a = session.decode(sim.probe("dac_a_o"), 14, 2**13)
        print(f"  dac_a_o={dac_a:+.4f}")

    print(f"\nfull waveform history: {sim.vcd_path()}")
    print("session object 'sim' is still live")
