"""Simulate red_pitaya_dsp.v -- the full crossbar -- to demonstrate its
signal-routing/summing logic (the part of the FPGA design most specific to
pyrpl, per red_pitaya_dsp.v's own header comment):

  PID0: input=ADC1, output_select=OUT1, p=1.0
  PID1: input=ADC2, output_select=OUT1, p=0.5   (SAME DAC1 as PID0 -> tests summing)
  PID2: input=ADC1, output_select=OUT2, p=0.3   (independent DAC2 -> tests DAC1/DAC2 isolation)

Expected (all ki=0, so this is a pure static-gain check, same as run_pid.py):
  DAC1 = 1.0*ADC1_step + 0.5*ADC2_step
  DAC2 = 0.3*ADC1_step

Run: python run_dsp_crossbar.py
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
    "red_pitaya_dsp.v",
    str(HERE / "patched_rtl" / "red_pitaya_pid_block.v"),  # see patched_rtl/README.md
    "red_pitaya_filter_block.v",
    "red_pitaya_lpf_block.v",
    "red_pitaya_trigger_block.v",
    str(HERE / "patched_rtl" / "red_pitaya_iir_block.v"),  # see patched_rtl/README.md
    "red_pitaya_iq_block.v",
    "red_pitaya_iq_fgen_block.v",
    "red_pitaya_iq_demodulator_block.v",
    "red_pitaya_iq_modulator_block.v",
    "red_pitaya_iq_hpf_block.v",
    "red_pitaya_iq_lpf_block.v",
    "red_pitaya_pfd_block.v",
    "red_pitaya_saturate.v",
    "red_pitaya_product_sat.v",
]
TB_FILE = HERE / "tb_dsp_top.v"
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)

ADC1_STEP = 0.4
ADC2_STEP = -0.2
PID0_P, PID1_P, PID2_P = 1.0, 0.5, 0.3


def pid_local(gain):
    return regbridge.PidRegs.p(gain)


def write_cfg(workdir):
    R = regbridge.DspCrossbarRegs
    lines = []

    def route(module, input_sel, output_sel, p_gain):
        lines.append(f"{R.addr_input_select(module):05x} {input_sel:08x}")
        lines.append(f"{R.addr_output_select(module):05x} {output_sel:08x}")
        lines.append(f"{R.addr_local(module, regbridge.PidRegs.ADDR_KP):05x} {pid_local(p_gain):08x}")

    route(R.PID0, R.ADC1, R.OUT1, PID0_P)
    route(R.PID1, R.ADC2, R.OUT1, PID1_P)
    route(R.PID2, R.ADC1, R.OUT2, PID2_P)

    (workdir / "cfg.hex").write_text("\n".join(lines) + "\n")


def demo():
    n = 4000
    samples_a = stimlib.step(n, amplitude=ADC1_STEP, start=n // 8)
    samples_b = stimlib.step(n, amplitude=ADC2_STEP, start=n // 8)

    workdir = OUT / "dsp_crossbar"
    workdir.mkdir(parents=True, exist_ok=True)
    stimlib.to_hex_file(workdir / "stimulus_a.hex", samples_a)
    stimlib.to_hex_file(workdir / "stimulus_b.hex", samples_b)
    write_cfg(workdir)

    vcd_path = runner.compile_and_run(
        DUT_FILES, TB_FILE, workdir, defines={"N_SAMPLES": n}, include_dirs=[HERE]
    )
    parsed = vcdtools.parse_vcd(vcd_path)

    clk = parsed[vcdtools.find(parsed, ".clk")]
    t_raw = clk["times"][clk["values"] == 1]
    ts = clk["timescale_s"]
    time_us = (t_raw.astype(np.float64) - t_raw[0]) * ts * 1e6

    dat_a_i = vcdtools.decode_fixed(vcdtools.hold_sample(parsed[vcdtools.find(parsed, ".dat_a_i")], t_raw), 14, 2**13)
    dat_b_i = vcdtools.decode_fixed(vcdtools.hold_sample(parsed[vcdtools.find(parsed, ".dat_b_i")], t_raw), 14, 2**13)
    dat_a_o = vcdtools.decode_fixed(vcdtools.hold_sample(parsed[vcdtools.find(parsed, ".dat_a_o")], t_raw), 14, 2**13)
    dat_b_o = vcdtools.decode_fixed(vcdtools.hold_sample(parsed[vcdtools.find(parsed, ".dat_b_o")], t_raw), 14, 2**13)

    plotting.plot_traces(
        [
            ("dat_a_i (ADC1 step)", time_us, dat_a_i, "V"),
            ("dat_b_i (ADC2 step)", time_us, dat_b_i, "V"),
            ("dat_a_o = DAC1 = 1.0*PID0(ADC1) + 0.5*PID1(ADC2)", time_us, dat_a_o, "V"),
            ("dat_b_o = DAC2 = 0.3*PID2(ADC1)", time_us, dat_b_o, "V"),
        ],
        OUT / "dsp_crossbar_demo.png",
        title="DSP crossbar: independent routing + summed outputs",
        xlabel="time [us]",
    )

    # measure well past the pipeline latency (see run_pid.py's step test for
    # why a ~12-sample margin is needed), well before either PID's (zero-gain)
    # integrator could matter -- ki is left at 0 for all three, so this is a
    # pure static-gain check, same idea as run_pid.py's proportional-jump test.
    step_idx = np.argmax(np.abs(dat_a_i) > 0.9 * np.abs(dat_a_i).max())
    dac1_measured = dat_a_o[step_idx + 12] - dat_a_o[step_idx - 3]
    dac2_measured = dat_b_o[step_idx + 12] - dat_b_o[step_idx - 3]
    dac1_expected = PID0_P * ADC1_STEP + PID1_P * ADC2_STEP
    dac2_expected = PID2_P * ADC1_STEP

    print(f"[DSP crossbar] DAC1: measured={dac1_measured:.4f}, expected={dac1_expected:.4f}")
    print(f"[DSP crossbar] DAC2: measured={dac2_measured:.4f}, expected={dac2_expected:.4f}")
    ok = abs(dac1_measured - dac1_expected) < 0.03 and abs(dac2_measured - dac2_expected) < 0.03
    print(f"[DSP crossbar] routing + summing sanity check: {'PASS' if ok else 'FAIL'}")


if __name__ == "__main__":
    demo()
