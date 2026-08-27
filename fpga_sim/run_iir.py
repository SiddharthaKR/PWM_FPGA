"""Simulate red_pitaya_iir_block.v in isolation: configure a single-pole
low-pass biquad (b1=a2=0) via the coefficient RAM, then
1) show its step response
2) sweep single-tone frequency response and compare to the analytic
   one-pole z-domain model (regbridge.IirRegs.onepole_lowpass_transfer_function)

Run: python run_iir.py
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
    # patched copy (see patched_rtl/README.md): the real file has a
    # leftover debug $fwrite to an undeclared `fdebug` identifier that
    # Icarus refuses to elaborate; harmless one-line removal, everything
    # else identical to pyrpl/fpga/rtl/red_pitaya_iir_block.v
    str(HERE / "patched_rtl" / "red_pitaya_iir_block.v"),
    "red_pitaya_filter_block.v",
    "red_pitaya_lpf_block.v",
    "red_pitaya_saturate.v",
    "red_pitaya_product_sat.v",
]
TB_FILE = HERE / "tb_iir.v"
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)

FC_HZ = 500e3  # filter cutoff


def write_cfg(workdir, fc_hz):
    coeffs = regbridge.IirRegs.onehot_pole_lowpass(fc_hz)
    lines = []
    for name, value in coeffs.items():
        addr = regbridge.IirRegs.coeff_addr(0, name)
        raw = regbridge.IirRegs.coeff_raw(value)
        lines.append(f"{addr:04x} {raw:08x}")
    lines.append(f"{regbridge.IirRegs.ADDR_LOOPS:04x} {1:08x}")  # loops=1 -> single active biquad
    lines.append(f"{regbridge.IirRegs.ADDR_ON_SHORTCUT:04x} {1:08x}")  # on=1, shortcut=0 (write LAST)
    (workdir / "cfg.hex").write_text("\n".join(lines) + "\n")
    return coeffs


def run_case(workdir, samples, fc_hz):
    workdir = pathlib.Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    stimlib.to_hex_file(workdir / "stimulus.hex", samples)
    write_cfg(workdir, fc_hz)
    vcd_path = runner.compile_and_run(
        DUT_FILES, TB_FILE, workdir, defines={"N_SAMPLES": len(samples)}, include_dirs=[HERE]
    )
    return vcdtools.parse_vcd(vcd_path)


def clk_edge_times(parsed):
    clk = parsed[vcdtools.find(parsed, ".clk")]
    rising = clk["times"][clk["values"] == 1]
    return rising, clk["timescale_s"]


def extract(parsed):
    t, ts = clk_edge_times(parsed)
    dat_i = vcdtools.decode_fixed(vcdtools.hold_sample(parsed[vcdtools.find(parsed, ".dat_i")], t), 14, 2**13)
    dat_o = vcdtools.decode_fixed(vcdtools.hold_sample(parsed[vcdtools.find(parsed, ".dat_o")], t), 14, 2**13)
    time_us = (t.astype(np.float64) - t[0]) * ts * 1e6
    return time_us, dat_i, dat_o


def step_response_demo():
    n = 2000
    samples = stimlib.step(n, amplitude=0.4, start=n // 8)
    parsed = run_case(OUT / "iir_step", samples, FC_HZ)
    t, dat_i, dat_o = extract(parsed)

    plotting.plot_traces(
        [
            ("input dat_i (step)", t, dat_i, "volts (norm)"),
            ("output dat_o (one-pole LPF)", t, dat_o, "volts (norm)"),
        ],
        OUT / "iir_step_response.png",
        title=f"IIR one-pole low-pass step response (fc={FC_HZ/1e3:.0f} kHz)",
        xlabel="time [us]",
    )

    # sanity check: an exponential step response should reach
    # 1-exp(-1) ~= 63% of its final value after one time constant tau=1/(2*pi*fc)
    step_idx = np.argmax(dat_i > 0.39 * dat_i.max())
    final = dat_i[step_idx + 5]  # one-pole LPF has DC gain 1 -> tracks input at DC
    tau_s = 1.0 / (2 * np.pi * FC_HZ)
    # see regbridge.IirRegs.EFFECTIVE_SAMPLE_DIVIDER: with loops=1, a single
    # active biquad only advances by one true filtered sample every 3 clock
    # cycles (a pipeline read-before-write hazard in the shared time-
    # multiplexed MAC engine), so 1 tau of *filter* time is 3x more raw clock
    # samples than a naive fs=125MHz assumption would suggest.
    fs_eff = FS / regbridge.IirRegs.EFFECTIVE_SAMPLE_DIVIDER
    tau_raw_samples = int(round(tau_s * fs_eff)) * regbridge.IirRegs.EFFECTIVE_SAMPLE_DIVIDER
    measured = dat_o[step_idx + tau_raw_samples] - dat_o[step_idx - 3]
    expected = (1 - np.exp(-1)) * (final - dat_o[step_idx - 3])
    print(f"[IIR step] after 1 tau ({tau_raw_samples} raw clock samples): measured={measured:.4f}, expected~={expected:.4f}")
    ok = abs(measured - expected) < 0.05
    print(f"[IIR step] one-tau-rise sanity check: {'PASS' if ok else 'FAIL'}")


def single_tone_response(freq_hz, cycles=10):
    n = int(np.ceil(cycles * FS / freq_hz))
    n = min(n, 400000)
    samples = stimlib.sine_freq(n, FS, amplitude=0.4, freq=freq_hz)
    parsed = run_case(OUT / f"iir_freq_{int(freq_hz)}", samples, FC_HZ)
    t, dat_i, dat_o = extract(parsed)

    n_used = len(t)
    start = int(0.4 * n_used)
    tt = (t[start:] - t[0]) * 1e-6
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
        print(f"[IIR freq] f={f:9.0f} Hz  measured gain={abs(resp):.4f}  phase={np.angle(resp, deg=True):+7.2f} deg")
        measured.append(resp)
    measured = np.array(measured)

    model_freqs = np.geomspace(20e3, 5e6, 200)
    model = regbridge.IirRegs.onepole_lowpass_transfer_function(model_freqs, FC_HZ)

    plotting.plot_bode(
        freqs,
        measured,
        OUT / "iir_bode.png",
        title=f"IIR one-pole low-pass frequency response (fc={FC_HZ/1e3:.0f} kHz) vs analytic model",
        model_freqs_hz=model_freqs,
        model_response=model,
    )

    model_at_meas = regbridge.IirRegs.onepole_lowpass_transfer_function(freqs, FC_HZ)
    rel_err = np.abs(np.abs(measured) - np.abs(model_at_meas)) / np.abs(model_at_meas)
    print(f"[IIR freq] max relative magnitude error vs analytic model: {rel_err.max():.3f}")
    print(f"[IIR freq] Bode sanity check: {'PASS' if rel_err.max() < 0.15 else 'FAIL'}")


if __name__ == "__main__":
    step_response_demo()
    frequency_sweep_demo()
