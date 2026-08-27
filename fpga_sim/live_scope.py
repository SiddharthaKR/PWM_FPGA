"""Interactive exploratory session against red_pitaya_scope.v.

Run with `python -i live_scope.py`. Arms an immediate manual trigger (with
the large set_dly needed to bypass the pretrig_ok gating -- README.md
finding #4), pokes a few distinct values onto adc_a_i, then reads them back
directly from the channel-A ring buffer with plain register reads at
0x10000+4*k -- this is the literal "write/read an address and see the
signal" workflow, applied to the scope's capture buffer.
"""

import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE / "common"))

import regbridge  # noqa: E402
import session  # noqa: E402

DUT_FILES = ["red_pitaya_scope.v", "red_pitaya_dfilt1.v", "axi_wr_fifo.v"]
TB_FILE = HERE / "tb_scope_live.v"
WORKDIR = HERE / "out" / "scope_live"

POKE_CODES = {"adc_a_i": 0, "adc_b_i": 1, "trig_ext_i": 2}
PROBE_CODES = {"trig_scope_o": 0}

if __name__ == "__main__":
    sim = session.Session(
        DUT_FILES, TB_FILE, WORKDIR, poke_codes=POKE_CODES, probe_codes=PROBE_CODES, include_dirs=[HERE]
    )

    sim.write(regbridge.ScopeRegs.ADDR_DECIMATION, 1)
    sim.write(regbridge.ScopeRegs.ADDR_DELAY, 20000)  # >= 2**RSZ, see docstring above
    sim.write(regbridge.ScopeRegs.ADDR_CTRL, 1)  # SW ARM
    sim.write(regbridge.ScopeRegs.ADDR_TRIG_SRC, regbridge.ScopeRegs.TRIG_SRC_MANUAL)  # arms + fires

    values = [0.1, 0.2, -0.1, -0.3, 0.05]
    print("poking a few distinct, repeated-and-held values onto adc_a_i:")
    for v in values:
        raw = regbridge.encode_signed(v, 14, 2**13)
        for _ in range(4):  # hold each value a few cycles so it's easy to spot in the buffer dump below
            sim.poke("adc_a_i", raw)
            sim.run(1)
        print(f"  poked {v:+.2f}V")

    # The buffer records starting from whichever raw clock cycle the trigger
    # actually fired on (a manual trigger here, fired by the ADDR_TRIG_SRC
    # write above) -- a few cycles pass between that write and the first
    # poke above (each register write is itself 2 clock cycles), so the
    # poked values don't necessarily land at buffer index 0. Read a wider
    # window and let the values speak for themselves rather than assuming
    # an exact index correspondence -- same "read address, see the signal"
    # idea, just honest about buffer/trigger alignment being something you
    # read back rather than something you can assume.
    n_read = 30
    print(f"\nreading back the first {n_read} channel-A buffer samples (0x10000 + 4*k):")
    for k in range(n_read):
        raw = sim.read(regbridge.ScopeRegs.ADDR_CH1_BASE + 4 * k)
        v = session.decode(raw, 14, 2**13)
        print(f"  buffer[{k:2d}] = {v:+.4f}V")

    print(f"\nfull waveform history: {sim.vcd_path()}")
    print("session object 'sim' is still live")
