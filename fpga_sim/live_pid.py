"""Interactive exploratory session against red_pitaya_pid_block.v.

Run with `python -i live_pid.py` (or paste into a notebook) -- the `sim`
object stays alive afterward so you can keep calling sim.write(...) /
sim.poke(...) / sim.probe(...) / sim.run(...) at the prompt, exactly like a
live PyRPL GUI/notebook session, but against the simulation.

Every call above is a REAL register write/read or a poke/probe of any named
signal -- including addresses/names you make up yourself. See
fpga_sim/README.md's "Interactive sessions" section for the full protocol
and how to point this at a custom address or an entirely new module.
"""

import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE / "common"))

import regbridge  # noqa: E402
import session  # noqa: E402

DUT_FILES = ["red_pitaya_pid_block.v", "red_pitaya_filter_block.v", "red_pitaya_lpf_block.v"]
TB_FILE = HERE / "tb_pid_live.v"
WORKDIR = HERE / "out" / "pid_live"

# must match the P/Q code table documented in tb_pid_live.v's header comment
POKE_CODES = {"dat_i": 0, "diff_dat_i": 1, "sync_i": 2}
PROBE_CODES = {"dat_o": 0, "error": 1, "int_shr": 2, "pid_out": 3, "kp_reg": 4}


def show(sim, label):
    snap = sim.snapshot(["dat_o", "error", "int_shr", "pid_out"])
    decoded = {}
    for k, v in snap.items():
        d = session.decode(v, 14 if k != "int_shr" else 16, 2**13)
        decoded[k] = "X (undefined)" if d is None else round(d, 4)
    print(f"[{label}] {decoded}")


if __name__ == "__main__":
    sim = session.Session(
        DUT_FILES, TB_FILE, WORKDIR, poke_codes=POKE_CODES, probe_codes=PROBE_CODES, include_dirs=[HERE]
    )

    # configure like the GUI would: r.pid0.setpoint = 0; r.pid0.p = 0.5; r.pid0.i = 0
    sim.write(regbridge.PidRegs.ADDR_SETPOINT, regbridge.PidRegs.setpoint(0.0))
    sim.write(regbridge.PidRegs.ADDR_KP, regbridge.PidRegs.p(0.5))
    sim.write(regbridge.PidRegs.ADDR_KI, regbridge.PidRegs.i(0.0))

    # poke a step onto dat_i (like feeding a constant analog input) and let
    # it propagate through the module's pipeline latency
    sim.poke("dat_i", regbridge.encode_signed(0.4, 14, 2**13))
    sim.run(12)
    show(sim, "after step, p=0.5")

    # change p *mid-session* -- something the old batch harness couldn't do
    # at all, since it loaded all config up front before any stimulus
    sim.write(regbridge.PidRegs.ADDR_KP, regbridge.PidRegs.p(1.0))
    sim.run(5)
    show(sim, "after p changed to 1.0, same dat_i")

    # a genuinely custom/undocumented address -- nothing in regbridge.PidRegs
    # names this one; the session doesn't care, it's just a raw bus read
    custom_addr = 0x1F0
    print(f"[custom] read(0x{custom_addr:x}) = {sim.read(custom_addr)} (whatever the RTL's default case returns)")

    print(f"\nfull waveform history: {sim.vcd_path()}")
    print("session object 'sim' is still live -- try sim.poke('dat_i', ...) / sim.probe('error') yourself")
