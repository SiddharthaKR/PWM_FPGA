"""Interactive (deterministic-replay) simulation session.

Mimics the "write a register, read it back, poke an input, watch a signal"
workflow of PyRPL's real GUI/notebook session, but against the Icarus
simulation instead of hardware -- see fpga_sim/README.md's "Interactive
sessions" section for the full design rationale.

Each call (write/read/poke/probe/run) appends one event to a growing,
strictly-ordered event log and re-runs the *entire* simulation from time 0
through the updated log (the iverilog compile step is cached after the
first call -- only the cheap vvp run repeats). Since RTL simulation is
deterministic, this gives results identical to a real persistent session,
while reusing runner.py/vcdtools.py/the tb_bus16/32.vh bus tasks unchanged.
"""

import pathlib

import runner


class Session:
    def __init__(self, dut_files, tb_file, workdir, poke_codes=None, probe_codes=None,
                 defines=None, include_dirs=None):
        """poke_codes / probe_codes: {name: small_int_code} dicts matching
        the P/Q code table documented in the testbench's header comment
        (e.g. tb_pid_live.v). Raw write()/read() always work on any address
        regardless of these maps -- that's what supports a custom/
        undocumented register.
        """
        self.workdir = pathlib.Path(workdir)
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.poke_codes = dict(poke_codes or {})
        self.probe_codes = dict(probe_codes or {})
        self._events = []  # list of (cmd:str, a1:int, a2:int)
        self._results = []
        self._vvp_path = runner.compile(dut_files, tb_file, self.workdir, defines=defines,
                                         include_dirs=include_dirs)

    # -- raw bus access: any address, no restriction to documented registers --

    def write(self, addr, data):
        self._events.append(("W", addr, data))
        self._sync()

    def read(self, addr):
        self._events.append(("R", addr, 0))
        self._sync()
        return self._results[-1]

    # -- named poke/probe (input stimulus / any signal in the DUT hierarchy) --

    def poke(self, name, value):
        code = self.poke_codes[name]
        self._events.append(("P", code, value))
        self._sync()

    def probe(self, name):
        code = self.probe_codes[name]
        self._events.append(("Q", code, 0))
        self._sync()
        return self._results[-1]

    def snapshot(self, names):
        """probe several signals at once (one replay instead of len(names))."""
        for name in names:
            self._events.append(("Q", self.probe_codes[name], 0))
        self._sync()
        values = self._results[-len(names):]
        return dict(zip(names, values))

    # -- time --

    def run(self, n_cycles=1):
        self._events.append(("N", n_cycles, 0))
        self._sync()

    # -- offline review --

    def vcd_path(self):
        """full waveform history of every event so far -- load with
        vcdtools.parse_vcd(...) / plot with plotting.py, same as the batch
        run_<block>.py demos."""
        return self.workdir / "dump.vcd"

    def event_log(self):
        return list(self._events)

    # -- internals --

    def _sync(self):
        lines = [f"{cmd} {a1 & 0xFFFFFFFF:x} {a2 & 0xFFFFFFFF:x}" for cmd, a1, a2 in self._events]
        (self.workdir / "events.txt").write_text("\n".join(lines) + "\n")
        runner.run_vvp(self._vvp_path, self.workdir, verbose=False)
        results_path = self.workdir / "results.txt"
        if results_path.exists():
            self._results = [_parse_result_line(line) for line in results_path.read_text().splitlines() if line.strip()]
        else:
            self._results = []


def _parse_result_line(line):
    """A read()/probe() result is normally a decimal int, but Verilog's
    "%0d" formats an undefined (X) signal as the literal text "x" -- e.g. a
    pipeline register probed before it has ever been driven a real value.
    That's a legitimate outcome of probing raw RTL state (not a session
    bug), so represent it as None instead of raising, and let the caller
    decide whether to retry/ignore/report it -- crashing the whole session
    over one momentarily-undefined read would be hostile for an interactive
    tool whose entire point is exploring exactly this kind of edge case.
    """
    line = line.strip().lower()
    if "x" in line or "z" in line:
        return None
    return int(line)


def decode(raw_value, bits, norm=1.0):
    """convenience: decode a raw read()/probe() result as a signed
    fixed-point value, same convention as regbridge.decode_signed /
    pyrpl.attributes.FloatRegister.to_python (value = signed(raw)/norm).
    Returns None unchanged (see _parse_result_line) if the underlying
    signal was undefined (X) at the moment it was probed.
    """
    if raw_value is None:
        return None
    v = int(raw_value) & ((1 << bits) - 1)
    if v >= 1 << (bits - 1):
        v -= 1 << bits
    return v / norm
