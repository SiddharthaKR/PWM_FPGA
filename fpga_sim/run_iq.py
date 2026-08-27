"""Simulate red_pitaya_iq_block.v in isolation: feed a sine tone into dat_i,
configure the NCO frequency, and observe the demodulated quadrature output
signal_o. Compares an "on resonance" run (NCO frequency == tone frequency,
which should settle to a steady, comparatively large demodulated value)
against a "detuned" run (NCO far from the tone frequency, which should
average out to something much smaller, since the quadrature low-pass filter
is left at its power-on-reset default of "off"/passthrough here).

Run: python run_iq.py
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
    "red_pitaya_iq_block.v",
    "red_pitaya_iq_fgen_block.v",
    "red_pitaya_iq_demodulator_block.v",
    "red_pitaya_iq_modulator_block.v",
    "red_pitaya_iq_hpf_block.v",
    "red_pitaya_iq_lpf_block.v",
    "red_pitaya_pfd_block.v",
    "red_pitaya_filter_block.v",
    "red_pitaya_lpf_block.v",
    "red_pitaya_saturate.v",
    "red_pitaya_product_sat.v",
]
TB_FILE = HERE / "tb_iq.v"
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)

TONE_HZ = 1.0e6
CYCLES = 40
G3_GAIN = 1.0 / 256  # empirical: quadrature1 (24-bit, LPFBITS) already carries
# a large implicit scale from the sin/cos LUT multiply inside the demodulator,
# so a "unity" g3=1.0 badly saturates signal_o (confirmed by a first attempt
# that produced a clipped square wave). 1/256 keeps it comfortably in range.


def write_cfg(workdir, nco_freq_hz):
    # NOTE: the demodulated readback (signal_o, when output_select==QUADRATURE
    # which is the power-on-reset default) is scaled by gain register g3
    # ("quadrature_factor" in iq.py), *not* g1/g2 ("amplitude", which instead
    # scale the modulator's direct AM output dat_o) -- found by tracing
    # red_pitaya_iq_modulator_block.v's signal_q1_o path. g3 defaults to 0 on
    # reset, so without writing it here, signal_o reads zero even though the
    # demodulation math upstream (quadrature1/quadrature1_hf) is working.
    lines = [
        f"{regbridge.IqRegs.ADDR_FREQUENCY:04x} {regbridge.IqRegs.frequency(nco_freq_hz):08x}",
        f"{regbridge.IqRegs.ADDR_G3:04x} {regbridge.IqRegs.gain(G3_GAIN):08x}",
    ]
    (workdir / "cfg.hex").write_text("\n".join(lines) + "\n")


def run_case(workdir, samples, nco_freq_hz):
    workdir = pathlib.Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    stimlib.to_hex_file(workdir / "stimulus.hex", samples)
    write_cfg(workdir, nco_freq_hz)
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
    signal_o = vcdtools.decode_fixed(
        vcdtools.hold_sample(parsed[vcdtools.find(parsed, ".signal_o")], t), 14, 2**13
    )
    time_us = (t.astype(np.float64) - t[0]) * ts * 1e6
    return time_us, dat_i, dat_o, signal_o


def demo():
    n = int(CYCLES * FS / TONE_HZ)
    samples = stimlib.sine_freq(n, FS, amplitude=0.5, freq=TONE_HZ)

    parsed_on = run_case(OUT / "iq_onres", samples, nco_freq_hz=TONE_HZ)
    t, dat_i, dat_o, signal_o_on = extract(parsed_on)

    parsed_off = run_case(OUT / "iq_detuned", samples, nco_freq_hz=TONE_HZ * 3.7)
    _, _, _, signal_o_off = extract(parsed_off)

    plotting.plot_traces(
        [
            (f"input dat_i: {TONE_HZ/1e6:.2f} MHz tone", t, dat_i, "volts (norm)"),
            ("demodulated signal_o (NCO on resonance)", t, signal_o_on, "volts (norm)"),
            ("demodulated signal_o (NCO detuned 3.7x)", t, signal_o_off, "volts (norm)"),
            ("modulator output dat_o", t, dat_o, "volts (norm)"),
        ],
        OUT / "iq_demod.png",
        title=f"IQ block demodulation  (tone={TONE_HZ/1e6:.2f} MHz)",
        xlabel="time [us]",
    )

    # On resonance the demodulated I-component has a genuine nonzero DC value
    # (|mean| large); detuned, it beats at the difference frequency and
    # averages toward zero over the record (|mean| small) -- this is the
    # textbook lock-in-amplifier signature. mean(|x|) is NOT a good
    # discriminator here since both cases have similar peak swing (with the
    # quadrature low-pass left at its power-on-reset "off" default, there's
    # no filtering to speak of -- only averaging over many cycles separates
    # the two cases).
    settle = int(0.3 * len(t))
    mag_on = abs(np.mean(signal_o_on[settle:]))
    mag_off = abs(np.mean(signal_o_off[settle:]))
    print(f"[IQ] |mean(signal_o)| on-resonance = {mag_on:.4f}, detuned = {mag_off:.4f}")
    ok = mag_on > 5 * mag_off and mag_on > 0.02
    print(f"[IQ] lock-in sanity check (on-resonance DC >> detuned DC): {'PASS' if ok else 'FAIL'}")


if __name__ == "__main__":
    demo()
