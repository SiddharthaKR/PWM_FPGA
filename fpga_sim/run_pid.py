"""Simulate red_pitaya_pid_block.v in isolation:
1) step response with configured P/I gains -> plot dat_i, error, integrator, dat_o
2) swept single-tone frequency response -> compare against the analytic
   Pid._transfer_function model (reimplemented in common/regbridge.py, see
   its docstring for why it isn't imported directly from pyrpl).

Run: python run_pid.py
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

FS = 125e6  # clock / sample rate, 8ns period
DUT_FILES = ["red_pitaya_pid_block.v", "red_pitaya_filter_block.v", "red_pitaya_lpf_block.v"]
TB_FILE = HERE / "tb_pid.v"
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)

P_GAIN = 0.5
I_GAIN_HZ = 2.0e4  # integral unity-gain frequency


def write_cfg(workdir, p, i, setpoint=0.0):
    lines = [
        f"{regbridge.PidRegs.ADDR_SETPOINT:04x} {regbridge.PidRegs.setpoint(setpoint):08x}",
        f"{regbridge.PidRegs.ADDR_KP:04x} {regbridge.PidRegs.p(p):08x}",
        f"{regbridge.PidRegs.ADDR_KI:04x} {regbridge.PidRegs.i(i):08x}",
    ]
    (workdir / "cfg.hex").write_text("\n".join(lines) + "\n")


def run_case(workdir, samples, p=P_GAIN, i=I_GAIN_HZ, setpoint=0.0):
    workdir = pathlib.Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    stimlib.to_hex_file(workdir / "stimulus.hex", samples)
    write_cfg(workdir, p, i, setpoint)
    vcd_path = runner.compile_and_run(
        DUT_FILES,
        TB_FILE,
        workdir,
        defines={"N_SAMPLES": len(samples)},
        include_dirs=[HERE],
    )
    parsed = vcdtools.parse_vcd(vcd_path)
    return parsed


def clk_edge_times(parsed):
    """returns (raw_ticks, timescale_s) of clk posedges. raw_ticks are in the
    VCD's native integer time unit (e.g. picoseconds for `timescale 1ns/1ps)
    -- use raw_ticks directly with vcdtools.hold_sample (same units as every
    other signal's recorded times), and multiply by timescale_s to get
    seconds for plotting / DFTs."""
    clk = parsed[vcdtools.find(parsed, ".clk")]
    rising_raw = clk["times"][clk["values"] == 1]
    return rising_raw, clk["timescale_s"]


def step_response_demo():
    n = 4000
    samples = stimlib.step(n, amplitude=0.3, start=n // 8)
    workdir = OUT / "pid_step"
    parsed = run_case(workdir, samples)

    t, ts = clk_edge_times(parsed)
    dat_i = vcdtools.decode_fixed(vcdtools.hold_sample(parsed[vcdtools.find(parsed, ".dat_i")], t), 14, 2**13)
    dat_o = vcdtools.decode_fixed(vcdtools.hold_sample(parsed[vcdtools.find(parsed, ".dat_o")], t), 14, 2**13)
    error = vcdtools.decode_fixed(vcdtools.hold_sample(parsed[vcdtools.find(parsed, ".error")], t), 15, 2**13)
    int_shr = vcdtools.decode_fixed(
        vcdtools.hold_sample(parsed[vcdtools.find(parsed, ".int_shr")], t), 16, 2**13
    )

    time_us = (t.astype(np.float64) - t[0]) * ts * 1e6

    plotting.plot_traces(
        [
            ("input dat_i (step)", time_us, dat_i, "volts (norm)"),
            ("error = filtered_input - setpoint", time_us, error, "volts (norm)"),
            ("integrator output (int_shr)", time_us, int_shr, "volts (norm)"),
            ("output dat_o = P + I (+D) saturated", time_us, dat_o, "volts (norm)"),
        ],
        OUT / "pid_step_response.png",
        title=f"PID step response  (p={P_GAIN}, i={I_GAIN_HZ:.0f} Hz)",
        xlabel="time [us]",
    )

    # sanity check: final steady-state output should match p*step (integrator
    # keeps driving until error->0, so eventually dat_o == setpoint asymptotically
    # is wrong for an isolated PID with no feedback loop connected -- here the
    # PID free-runs open-loop, so with i!=0 the output keeps integrating the
    # constant post-step error and never reaches a true "final value". Instead
    # check the *initial* proportional jump right after the step matches p*step.
    # the module has several cycles of pipeline latency (input filter +
    # error register + Kp multiply/shift register, ~_delay=3 documented in
    # pid.py plus extra stages from the (bypassed but still registered)
    # input filter) before dat_o reflects a change on dat_i -- measure well
    # past that latency, but still soon enough that the (slow, by design)
    # integrator has barely moved.
    step_idx = np.argmax(dat_i > 0.29 * dat_i.max())
    jump = dat_o[step_idx + 12] - dat_o[step_idx - 3]
    expected_jump = P_GAIN * 0.3
    print(f"[PID step] measured P-jump={jump:.4f}, expected~{expected_jump:.4f}")
    ok = abs(jump - expected_jump) < 0.05
    print(f"[PID step] proportional response sanity check: {'PASS' if ok else 'FAIL'}")


def single_tone_response(freq_hz, cycles=10, p=P_GAIN, i=I_GAIN_HZ):
    n = int(np.ceil(cycles * FS / freq_hz))
    n = min(n, 400000)  # cap runtime/VCD size
    samples = stimlib.sine_freq(n, FS, amplitude=0.3, freq=freq_hz)
    workdir = OUT / f"pid_freq_{int(freq_hz)}"
    parsed = run_case(workdir, samples, p=p, i=i, setpoint=0.0)

    t, ts = clk_edge_times(parsed)
    dat_i = vcdtools.decode_fixed(vcdtools.hold_sample(parsed[vcdtools.find(parsed, ".dat_i")], t), 14, 2**13)
    dat_o = vcdtools.decode_fixed(vcdtools.hold_sample(parsed[vcdtools.find(parsed, ".dat_o")], t), 14, 2**13)

    # discard first 40% of the record to let integrator transient settle,
    # then measure complex response via a single-frequency DFT (Goertzel-style)
    n_used = len(t)
    start = int(0.4 * n_used)
    tt = (t[start:].astype(np.float64) - t[0]) * ts
    w = 2 * np.pi * freq_hz
    basis = np.exp(-1j * w * tt)
    x_component = np.sum(dat_i[start:] * basis)
    y_component = np.sum(dat_o[start:] * basis)
    if abs(x_component) < 1e-9:
        return None
    return y_component / x_component


def frequency_sweep_demo():
    freqs = np.geomspace(20e3, 5e6, 6)
    measured = []
    for f in freqs:
        resp = single_tone_response(f)
        print(f"[PID freq] f={f:9.0f} Hz  measured gain={abs(resp):.4f}  phase={np.angle(resp, deg=True):+7.2f} deg")
        measured.append(resp)
    measured = np.array(measured)

    model_freqs = np.geomspace(20e3, 5e6, 200)
    model = regbridge.PidRegs.transfer_function(model_freqs, P_GAIN, I_GAIN_HZ)

    plotting.plot_bode(
        freqs,
        measured,
        OUT / "pid_bode.png",
        title=f"PID frequency response  (p={P_GAIN}, i={I_GAIN_HZ:.0f} Hz) vs analytic model",
        model_freqs_hz=model_freqs,
        model_response=model,
    )

    model_at_meas = regbridge.PidRegs.transfer_function(freqs, P_GAIN, I_GAIN_HZ)
    rel_err = np.abs(np.abs(measured) - np.abs(model_at_meas)) / np.abs(model_at_meas)
    print(f"[PID freq] max relative magnitude error vs analytic model: {rel_err.max():.3f}")
    print(f"[PID freq] Bode sanity check: {'PASS' if rel_err.max() < 0.15 else 'FAIL'}")


if __name__ == "__main__":
    step_response_demo()
    frequency_sweep_demo()
