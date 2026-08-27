"""Stimulus generators for FPGA block simulation.

All generators return int arrays in the range of a signed 14-bit ADC/DAC
sample: [-8192, 8191]. `to_hex_file` writes them in $readmemh-compatible
14-bit hex (two's complement) for a Verilog testbench to read with
`$readmemh` into a `reg [13:0] mem [0:N-1]`.
"""

import numpy as np

BITS = 14
FULL_SCALE = 2 ** (BITS - 1) - 1  # 8191, matches norm=2**13-1 used throughout pyrpl


def _clip(x):
    return np.clip(np.round(x), -(2 ** (BITS - 1)), 2 ** (BITS - 1) - 1).astype(np.int32)


def dc(n, value=0.5):
    """constant value, value in [-1, 1] of full scale"""
    return _clip(np.full(n, value * FULL_SCALE))


def step(n, amplitude=0.5, start=None):
    """zero, then jumps to `amplitude` (fraction of full scale) at sample `start`"""
    if start is None:
        start = n // 4
    x = np.zeros(n)
    x[start:] = amplitude * FULL_SCALE
    return _clip(x)


def impulse(n, amplitude=1.0, at=None):
    if at is None:
        at = n // 4
    x = np.zeros(n)
    x[at] = amplitude * FULL_SCALE
    return _clip(x)


def sine(n, amplitude=0.5, cycles=10.0, phase=0.0):
    """`cycles` full periods across the n-sample record"""
    t = np.arange(n)
    x = amplitude * FULL_SCALE * np.sin(2 * np.pi * cycles * t / n + phase)
    return _clip(x)


def sine_freq(n, fs, amplitude, freq, phase=0.0):
    """sine wave at physical frequency `freq` [Hz] given sample rate `fs` [Hz]"""
    t = np.arange(n) / fs
    x = amplitude * FULL_SCALE * np.sin(2 * np.pi * freq * t + phase)
    return _clip(x)


def chirp(n, amplitude=0.5, f_start_cycles=1.0, f_stop_cycles=200.0, log=True):
    """frequency sweep across n samples, expressed in cycles over the record
    (i.e. f_stop_cycles = f_stop_cycles full periods fit in n samples).
    Useful for extracting a frequency response in one simulation run via FFT.
    Instantaneous phase is obtained by numerically integrating (cumsum) the
    instantaneous frequency, which is robust for both log and linear sweeps.
    """
    t = np.arange(n) / n  # normalized time 0..1
    if log:
        k = np.log(f_stop_cycles / f_start_cycles)
        inst_freq = f_start_cycles * np.exp(k * t)  # cycles per full record
    else:
        inst_freq = f_start_cycles + (f_stop_cycles - f_start_cycles) * t
    # phase increment per sample = 2*pi*inst_freq/n ; integrate via cumsum
    phase = 2 * np.pi * np.cumsum(inst_freq) / n
    x = amplitude * FULL_SCALE * np.sin(phase)
    return _clip(x), inst_freq


def square(n, amplitude=0.5, cycles=5.0):
    t = np.arange(n)
    x = amplitude * FULL_SCALE * np.sign(np.sin(2 * np.pi * cycles * t / n + 1e-9))
    return _clip(x)


def noise(n, amplitude=0.2, seed=0):
    rng = np.random.default_rng(seed)
    x = amplitude * FULL_SCALE * rng.standard_normal(n)
    return _clip(x)


def to_hex_file(path, samples):
    """write samples ($readmemh-compatible, one 14-bit two's-complement hex value per line)"""
    samples = np.asarray(samples, dtype=np.int64)
    mask = (1 << BITS) - 1
    with open(path, "w") as f:
        for v in samples:
            f.write(f"{int(v) & mask:04x}\n")


def from_twos(raw, bits=BITS):
    """decode an unsigned int (or array) as a two's-complement signed value of `bits` width"""
    raw = np.asarray(raw, dtype=np.int64)
    half = 1 << (bits - 1)
    full = 1 << bits
    return np.where(raw >= half, raw - full, raw)
