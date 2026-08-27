"""Simulate red_pitaya_scope.v in isolation: feed a distinctive (non-periodic)
chirp into adc_a_i, arm the scope with an immediate manual trigger and a
large `set_dly` (see comment in write_cfg for why), then read back the first
CAPTURE_LEN samples of the channel-A ring buffer over the sys bus and check
they reproduce the driven input (allowing for the small constant pipeline
delay through the write logic + compensation filter, found via a best-offset
search rather than assumed analytically).

Run: python run_scope.py
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
DUT_FILES = ["red_pitaya_scope.v", "red_pitaya_dfilt1.v", "axi_wr_fifo.v"]
TB_FILE = HERE / "tb_scope.v"
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)

N_SAMPLES = 3000
CAPTURE_LEN = 500


def write_cfg(workdir):
    lines = [
        f"{regbridge.ScopeRegs.ADDR_DECIMATION:04x} {1:08x}",
        # set_dly deliberately >= 2**RSZ (16384): the RTL's `pretrig_ok`
        # condition is `(accumulated_samples > 2**RSZ - set_dly) ||
        # any_bit_of_set_dly_above_bit_RSZ_set` -- with a small set_dly the
        # module would refuse to honor a trigger until it has accumulated
        # nearly a full buffer's worth of *pretrigger* samples first, which
        # our short 3000-sample run would never satisfy. A large set_dly
        # short-circuits that via the second OR term, so a manual trigger
        # fired right at the start of the run is honored immediately.
        f"{regbridge.ScopeRegs.ADDR_DELAY:04x} {20000:08x}",
        f"{regbridge.ScopeRegs.ADDR_CTRL:04x} {1:08x}",  # bit0: SW ARM
        # trig_src=1 (manual) with wdata==1 ALSO pulses the sw trigger itself
        # in the same write (see red_pitaya_scope.v: adc_trig_sw <= sys_wen
        # && addr==0x4 && wdata[3:0]==1), so this both selects manual trigger
        # mode and fires it, right before any stimulus samples are fed.
        f"{regbridge.ScopeRegs.ADDR_TRIG_SRC:04x} {regbridge.ScopeRegs.TRIG_SRC_MANUAL:08x}",
    ]
    (workdir / "cfg.hex").write_text("\n".join(lines) + "\n")


def demo():
    samples, _ = stimlib.chirp(N_SAMPLES, amplitude=0.4, f_start_cycles=5, f_stop_cycles=80, log=False)

    workdir = OUT / "scope"
    workdir.mkdir(parents=True, exist_ok=True)
    stimlib.to_hex_file(workdir / "stimulus.hex", samples)
    write_cfg(workdir)

    runner.compile_and_run(
        DUT_FILES,
        TB_FILE,
        workdir,
        defines={"N_SAMPLES": N_SAMPLES, "CAPTURE_LEN": CAPTURE_LEN},
        include_dirs=[HERE],
    )

    readback_path = workdir / "readback.txt"
    readback = np.array([int(line) for line in readback_path.read_text().splitlines() if line.strip()])
    readback_signed = vcdtools.decode_signed(readback, 14).astype(np.float64) / 2**13
    stim_v = stimlib.from_twos(samples).astype(np.float64) / 2**13

    # search for the small constant pipeline-delay offset between the
    # readback buffer and the driven stimulus (see module docstring)
    best_offset, best_err = 0, np.inf
    for offset in range(0, 30):
        n = min(CAPTURE_LEN, len(stim_v) - offset)
        err = np.mean(np.abs(readback_signed[:n] - stim_v[offset : offset + n]))
        if err < best_err:
            best_err, best_offset = err, offset

    n = min(CAPTURE_LEN, len(stim_v) - best_offset)
    plotting.plot_traces(
        [
            ("driven adc_a_i (chirp, offset-aligned)", np.arange(n), stim_v[best_offset : best_offset + n], "V"),
            ("scope readback (channel A buffer)", np.arange(n), readback_signed[:n], "V"),
        ],
        OUT / "scope_readback.png",
        title=f"Scope capture readback vs driven input (best alignment offset={best_offset} samples)",
        xlabel="sample index",
    )

    print(f"[Scope] best alignment offset={best_offset} samples, mean|error|={best_err:.4f}")
    # residual error grows with instantaneous frequency (verified: ~0.019 in
    # the first 100 samples vs ~0.040 in the last 200, on a 0.4V-amplitude
    # chirp sweeping 5->80 cycles over the record) -- consistent with the
    # small, roughly-constant group delay of the adc_a_i -> red_pitaya_dfilt1
    # compensation filter ahead of the capture buffer (a few samples' delay
    # shows up as more phase error at higher instantaneous frequency), not a
    # readback/alignment bug. 0.05 comfortably separates that from a real
    # capture failure (which would show gross, not gradually-growing, error).
    ok = best_err < 0.05
    print(f"[Scope] readback-matches-driven-input sanity check: {'PASS' if ok else 'FAIL'}")


if __name__ == "__main__":
    demo()
