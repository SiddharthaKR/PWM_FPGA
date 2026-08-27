"""Physical-unit <-> raw fixed-point register conversion.

pyrpl's real Python driver (pyrpl/attributes.py FloatRegister/GainRegister,
instantiated per-block in pyrpl/hardware_modules/*.py) cannot be imported
directly here without a Qt binding (qtpy) installed, since pyrpl/__init__.py
unconditionally imports QtWidgets for the GUI. Importing pyrpl's hardware
module classes would drag in the whole GUI stack just to read a few
constants, which is fragile in a headless simulation environment.

Instead, this module re-implements the *exact* same formulas, each with a
comment pointing at the pyrpl source line it mirrors, so the register writes
produced here are numerically identical to what the real MonitorClient would
send to hardware. If pyrpl's driver code changes these formulas, this file
must be updated to match.

Two's-complement encode/decode replicates
pyrpl/attributes.py:555 FloatRegister.to_python / :568 from_python.
"""

import numpy as np


def encode_signed(value_float, bits, norm):
    """python float -> raw unsigned register int (two's complement of `bits` width)
    mirrors FloatRegister.from_python, pyrpl/attributes.py:568-587
    """
    v = int(round(float(value_float) * norm))
    vmax = 2 ** (bits - 1) - 1
    vmin = -(2 ** (bits - 1))
    v = max(vmin, min(vmax, v))
    if v < 0:
        v += 2**bits
    return v & ((1 << bits) - 1)


def decode_signed(raw_int, bits, norm):
    """raw register int -> python float, mirrors FloatRegister.to_python,
    pyrpl/attributes.py:555-566
    """
    v = int(raw_int) & ((1 << bits) - 1)
    if v >= 2 ** (bits - 1):
        v -= 2**bits
    return float(v) / norm


# ---------------------------------------------------------------------------
# PID block, mirrors pyrpl/hardware_modules/pid.py (class Pid)
# ---------------------------------------------------------------------------
class PidRegs:
    ADDR_IVAL = 0x100
    ADDR_SETPOINT = 0x104
    ADDR_KP = 0x108
    ADDR_KI = 0x10C
    ADDR_KD = 0x110
    ADDR_FILTER = 0x120
    ADDR_MIN = 0x124
    ADDR_MAX = 0x128
    ADDR_PAUSE_DIFF = 0x12C

    PSR = 12  # pid.py:261
    ISR = 32  # pid.py:263
    DSR = 10  # pid.py:265
    GAINBITS = 24  # pid.py:267

    @classmethod
    def setpoint(cls, volts):
        return encode_signed(volts, 14, 2**13)  # pid.py:276

    @classmethod
    def p(cls, gain):
        return encode_signed(gain, cls.GAINBITS, 2**cls.PSR)  # pid.py:281

    @classmethod
    def i(cls, unity_gain_freq_hz):
        # pid.py:282-287 : norm = 2**ISR * 2*pi * 8e-9 (8ns = 1 clock cycle @ 125MHz)
        norm = 2**cls.ISR * 2.0 * np.pi * 8e-9
        return encode_signed(unity_gain_freq_hz, cls.GAINBITS, norm)

    @classmethod
    def min_voltage(cls, volts):
        return encode_signed(volts, 14, 2**13)  # pid.py:278

    @classmethod
    def max_voltage(cls, volts):
        return encode_signed(volts, 14, 2**13)  # pid.py:279

    @staticmethod
    def transfer_function(frequencies_hz, p, i, delay_cycles=3):
        """Analytic open-loop transfer function of the PID (no input filter),
        reimplemented standalone from pid.py:439-482
        (Pid._pid_transfer_function + Pid._delay_transfer_function), since
        pid.py cannot be imported here (see module docstring).
        """
        f = np.asarray(frequencies_hz, dtype=complex)
        tf = i / (f * 1j) * np.exp(-1j * 8e-9 * f * 2 * np.pi)  # pid.py:450-453
        tf += p  # pid.py:456
        delay = delay_cycles * 8e-9  # pid.py:478 (module_delay_cycle * 8e-9)
        tf *= np.exp(-1j * delay * f * 2 * np.pi)
        return tf


# ---------------------------------------------------------------------------
# IQ block, mirrors pyrpl/hardware_modules/iq.py (class Iq)
# ---------------------------------------------------------------------------
class IqRegs:
    ADDR_PHASE = 0x104
    ADDR_FREQUENCY = 0x108
    ADDR_G1 = 0x110
    ADDR_G2 = 0x114
    ADDR_G3 = 0x118
    ADDR_G4 = 0x11C

    PHASEBITS = 32  # iq.py:367
    GAINBITS = 18  # iq.py:368
    SHIFTBITS = 8  # iq.py:371 (used as norm exponent for g1..g4 below)

    @classmethod
    def frequency(cls, freq_hz, fs=125e6):
        # FrequencyRegister: raw = round(freq/fs * 2**PHASEBITS), phase accumulator
        raw = int(round(float(freq_hz) / fs * 2**cls.PHASEBITS)) & (2**cls.PHASEBITS - 1)
        return raw

    @classmethod
    def phase(cls, degrees):
        # PhaseRegister: raw = round(degrees/360 * 2**PHASEBITS)
        raw = int(round(float(degrees) / 360.0 * 2**cls.PHASEBITS)) & (2**cls.PHASEBITS - 1)
        return raw

    @classmethod
    def gain(cls, value):
        # GainRegister(bits=GAINBITS, norm=2**SHIFTBITS) -- iq.py:391 (_g1) etc.
        return encode_signed(value, cls.GAINBITS, 2**cls.SHIFTBITS)


class IirRegs:
    """red_pitaya_iir_block.v register map, reverse-engineered directly from
    the RTL (iir.py's Python driver only exposes on/bypass/loops -- the
    coefficient RAM has no Python-side register descriptor at all; it's
    written by a separate coefficient-upload code path in iir.py that we
    don't replicate here).
    """

    ADDR_LOOPS = 0x100
    ADDR_ON_SHORTCUT = 0x104  # bit0=on, bit1=shortcut

    IIRSHIFT = 29  # coefficient fixed-point binary point (red_pitaya_iir_block.v default IIRSHIFT=29)

    @staticmethod
    def coeff_addr(stage, which):
        """address of the LOW 32-bit word of coefficient `which` ('b0','b1','a1','a2')
        for biquad `stage`. The HIGH word (addr+4) is computed by the RTL but
        discarded (truncated away) since IIRBITS==32 by default, so it does
        not need to be written.
        """
        offset = {"b0": 0, "b1": 2, "a1": 4, "a2": 6}[which]
        word_index = 8 * stage + offset
        return 0x8000 + word_index * 4

    @classmethod
    def coeff_raw(cls, value):
        return encode_signed(value, 32, 2**cls.IIRSHIFT)

    # Empirically measured (see run_iir.py): with `loops=1` (a single active
    # biquad, no time-multiplexing with other stages), red_pitaya_iir_block.v
    # is NOT able to produce a fresh filtered sample every clock cycle. The
    # round-robin engine is architecturally built to time-share the multiply
    # -accumulate pipeline across up to IIRSTAGES=14 independently-configured
    # biquads; a single active stage's own feedback write-back
    # (`y1_i[stage2] <= y_full`) trails its own read (`y1a <= y1_i[stage0]`)
    # by multiple pipeline cycles, so *consecutive* input samples read a
    # stale (not-yet-updated) feedback value 2 cycles out of every 3, and the
    # filter only actually advances by one true sample every 3 clock cycles.
    # This is invisible in the DC gain (which came out exactly right: 1.0),
    # only in the *time constant*, which is why it wasn't obvious from a
    # naive "does the output move in the right direction" check. Effective
    # sample rate for a single loops=1 stage is therefore fs/3, not fs.
    EFFECTIVE_SAMPLE_DIVIDER = 3

    @classmethod
    def onehot_pole_lowpass(cls, fc_hz, fs=125e6):
        """coefficients (b0, b1, a1, a2) for the simplest possible IIR this
        hardware can realize: a single-pole low-pass y[n] = b0*x[n] + a1*y[n-1]
        (b1=a2=0), with the standard exponential-smoothing formula, designed
        against the module's *effective* sample rate (see
        EFFECTIVE_SAMPLE_DIVIDER above) rather than the raw clock rate. Since
        the hardware's y_sum is a straight SUM of a1*y1 + a2*y2 + b0*x0 + b1*x1
        (no implicit sign flip -- confirmed by reading red_pitaya_iir_block.v's
        `assign y_sum = p_ay1 + p_ay2 + p_bx0 + p_bx1;`), a1 here is used
        directly as the positive feedback coefficient alpha, unlike the
        textbook a[1] convention (y = b0 x0 - a1_textbook y1) which would need
        a1 = -a1_textbook.
        """
        fs_eff = fs / cls.EFFECTIVE_SAMPLE_DIVIDER
        alpha = np.exp(-2 * np.pi * fc_hz / fs_eff)
        return dict(b0=1 - alpha, b1=0.0, a1=alpha, a2=0.0)

    @classmethod
    def onepole_lowpass_transfer_function(cls, frequencies_hz, fc_hz, fs=125e6):
        """analytic z-domain transfer function of the same one-pole filter,
        H(z) = (1-alpha) / (1 - alpha*z^-1), evaluated on the unit circle at
        the module's effective sample rate."""
        fs_eff = fs / cls.EFFECTIVE_SAMPLE_DIVIDER
        alpha = np.exp(-2 * np.pi * fc_hz / fs_eff)
        f = np.asarray(frequencies_hz, dtype=complex)
        z_inv = np.exp(-1j * 2 * np.pi * f / fs_eff)
        return (1 - alpha) / (1 - alpha * z_inv)


class TrigRegs:
    """red_pitaya_trigger_block.v register map, matches trig.py's
    threshold/hysteresis (0x118/0x11C, both FloatRegister(bits=14,norm=2**13))."""

    ADDR_ARM = 0x100  # any write pulses "rearm" -> armed=1 for one cycle
    ADDR_AUTO_REARM = 0x104  # bit0=auto_rearm, bit1=phase_abs
    ADDR_TRIGGER_SOURCE = 0x108  # bit0=trigger on positive slope, bit1=negative slope
    ADDR_OUTPUT_SELECT = 0x10C  # 0=TTL (trig_o replicated on dat_o), 1=PHASE
    ADDR_THRESHOLD = 0x118
    ADDR_HYSTERESIS = 0x11C

    @staticmethod
    def volts(value):
        return encode_signed(value, 14, 2**13)


class AsgRegs:
    """red_pitaya_asg.v register map (channel A), reverse-engineered from the
    RTL -- asg.py's Python driver computes `frequency`/`_counter_step` etc.
    from a much richer setup() API (waveform name, table auto-sizing) that we
    don't replicate; this mirrors just the raw registers needed to load a
    fixed table and play it back continuously at a chosen frequency.
    """

    RSZ = 14  # table address bits -> up to 2**14 = 16384 samples
    ADDR_CTRL = 0x0  # bits[2:0]=trig_src (5=always/free-running), bits[12:4]=flags (bit4=wrap)
    ADDR_AMP_DC = 0x4  # bits[13:0]=amp (unsigned, norm 2**13), bits[29:16]=dc (signed, norm 2**13)
    ADDR_SIZE = 0x8
    ADDR_OFFSET = 0xC
    ADDR_STEP = 0x10
    ADDR_TABLE_BASE = 0x10000  # + 4*sample_index, one 14-bit sample per 32-bit word

    TRIG_SRC_ALWAYS = 5
    FLAG_WRAP_BIT = 4  # periodic wraparound (vs. one-shot)

    @classmethod
    def ctrl_word(cls, trig_src=TRIG_SRC_ALWAYS, wrap=True):
        return (trig_src & 0x7) | ((1 << cls.FLAG_WRAP_BIT) if wrap else 0)

    @classmethod
    def size_word(cls, table_length):
        # phase accumulator wraps when accumulated phase exceeds this value;
        # top RSZ bits are the integer table index of the *last* valid sample
        return (table_length - 1) << 16

    @classmethod
    def step_word(cls, play_freq_hz, table_length, fs=125e6):
        # advance (table_length * play_freq_hz / fs) table-index-units per
        # clock, in the same <<16 fixed-point scale as size_word
        return int(round(table_length * play_freq_hz / fs * 2**16))

    @classmethod
    def amp_word(cls, gain, dc=0.0):
        amp_raw = int(round(gain * 2**13)) & 0x3FFF  # unsigned 14-bit
        dc_raw = encode_signed(dc, 14, 2**13) & 0x3FFF
        return amp_raw | (dc_raw << 16)


class ScopeRegs:
    """red_pitaya_scope.v register map, reverse-engineered from the RTL
    (matches the addresses also visible in scope.py: threshold=0x8,
    hysteresis=0x20, trigger_debounce=0x90, decimation=0x14).
    """

    ADDR_CTRL = 0x0  # bit0=SW ARM (self-clearing pulse), bit1=SW RESET, bit3=adc_we_keep
    ADDR_TRIG_SRC = 0x4  # bits[3:0]: 1=manual (also fires immediately if wdata==1), 2/3=ch A rising/falling, ...
    ADDR_THRESHOLD_A = 0x8
    ADDR_DELAY = 0x10  # set_dly: post-trigger sample count before capture stops
    ADDR_DECIMATION = 0x14
    ADDR_HYSTERESIS_A = 0x20
    ADDR_AVERAGE_EN = 0x28
    ADDR_CH1_BASE = 0x10000
    ADDR_CH2_BASE = 0x20000

    TRIG_SRC_MANUAL = 1
    TRIG_SRC_CH_A_RISING = 2

    @staticmethod
    def volts(value):
        return encode_signed(value, 14, 2**13)


class DspCrossbarRegs:
    """red_pitaya_dsp.v crossbar routing, matches pyrpl/hardware_modules/dsp.py
    DSP_INPUTS numbering exactly (module number == the value input_select is
    set to, to route FROM that module)."""

    PID0, PID1, PID2, TRIG, IIR, IQ0, IQ1, IQ2 = range(8)
    ASG1, ASG2 = 8, 9
    ADC1, ADC2, DAC1, DAC2 = 10, 11, 12, 13
    OFF, OUT1, OUT2, BOTH = 0, 1, 2, 3

    @staticmethod
    def module_base(module_number):
        return module_number * 0x10000

    @classmethod
    def addr_input_select(cls, module_number):
        return cls.module_base(module_number) + 0x00

    @classmethod
    def addr_output_select(cls, module_number):
        return cls.module_base(module_number) + 0x04

    @classmethod
    def addr_local(cls, module_number, local_offset):
        """address of a register *inside* a submodule (e.g. PID's own 0x108
        kp register), at DSP-crossbar module `module_number`."""
        return cls.module_base(module_number) + local_offset


def dummy_module_reg_writes(**kwargs):
    """not used directly; placeholder documenting that every *_writes list
    below is a plain list of (address, raw_uint32_value) tuples consumed by
    the Verilog write_reg16/write_reg32 tasks."""
    return list(kwargs.items())
