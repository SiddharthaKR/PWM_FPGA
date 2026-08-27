"""Interactive exploratory session against red_pitaya_dsp.v -- the full
crossbar. Run with `python -i live_dsp_crossbar.py`.

Routes PID0(ADC1)+PID1(ADC2) -> DAC1 (summed) and PID2(ADC1) -> DAC2
independently (same layout as run_dsp_crossbar.py), then changes PID1's
gain *mid-session* and shows DAC1 update while DAC2 (which doesn't depend
on PID1) stays put -- demonstrating both live reconfiguration and the
crossbar's per-DAC independence, live.
"""

import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE / "common"))

import regbridge  # noqa: E402
import session  # noqa: E402

DUT_FILES = [
    "red_pitaya_dsp.v",
    str(HERE / "patched_rtl" / "red_pitaya_pid_block.v"),
    "red_pitaya_filter_block.v",
    "red_pitaya_lpf_block.v",
    "red_pitaya_trigger_block.v",
    str(HERE / "patched_rtl" / "red_pitaya_iir_block.v"),
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
TB_FILE = HERE / "tb_dsp_top_live.v"
WORKDIR = HERE / "out" / "dsp_crossbar_live"

POKE_CODES = {"dat_a_i": 0, "dat_b_i": 1, "asg1_i": 2, "asg2_i": 3}
PROBE_CODES = {"dat_a_o": 0, "dat_b_o": 1, "trig_o": 2, "scope1_o": 3, "scope2_o": 4}

R = regbridge.DspCrossbarRegs


def route(sim, module, input_sel, output_sel, p_gain):
    sim.write(R.addr_input_select(module), input_sel)
    sim.write(R.addr_output_select(module), output_sel)
    sim.write(R.addr_local(module, regbridge.PidRegs.ADDR_KP), regbridge.PidRegs.p(p_gain))


def show(sim, label):
    snap = sim.snapshot(["dat_a_o", "dat_b_o"])
    decoded = {k: round(session.decode(v, 14, 2**13), 4) for k, v in snap.items()}
    print(f"[{label}] DAC1(dat_a_o)={decoded['dat_a_o']}  DAC2(dat_b_o)={decoded['dat_b_o']}")


if __name__ == "__main__":
    sim = session.Session(
        DUT_FILES, TB_FILE, WORKDIR, poke_codes=POKE_CODES, probe_codes=PROBE_CODES, include_dirs=[HERE]
    )

    route(sim, R.PID0, R.ADC1, R.OUT1, 1.0)
    route(sim, R.PID1, R.ADC2, R.OUT1, 0.5)
    route(sim, R.PID2, R.ADC1, R.OUT2, 0.3)

    sim.poke("dat_a_i", regbridge.encode_signed(0.4, 14, 2**13))
    sim.poke("dat_b_i", regbridge.encode_signed(-0.2, 14, 2**13))
    sim.run(12)
    show(sim, "initial: DAC1=1.0*0.4+0.5*(-0.2)=0.3, DAC2=0.3*0.4=0.12")

    # change PID1's gain mid-session -- DAC1 should move, DAC2 (fed only by
    # PID2, untouched here) should not
    sim.write(R.addr_local(R.PID1, regbridge.PidRegs.ADDR_KP), regbridge.PidRegs.p(1.0))
    sim.run(15)  # give the pipeline (kp_mult -> kp_reg -> pid_sum -> dat_o) time to catch up
    show(sim, "after PID1 p: 0.5->1.0: DAC1=1.0*0.4+1.0*(-0.2)=0.2, DAC2 unchanged")

    print(f"\nfull waveform history: {sim.vcd_path()}")
    print("session object 'sim' is still live")
