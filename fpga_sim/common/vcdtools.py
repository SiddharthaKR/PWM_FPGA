"""Minimal, dependency-free VCD parser.

Reads $var declarations (building full hierarchical signal names from the
$scope stack) and value-change lines, and returns, per signal, the sparse
list of (time, raw_unsigned_value) changes. No external vcd-parsing package
required (numpy only).
"""

import re

import numpy as np

_TS_MULT = {"fs": 1e-15, "ps": 1e-12, "ns": 1e-9, "us": 1e-6, "ms": 1e-3, "s": 1.0}

_VECTOR_RE = re.compile(r"^[bB]([01xXzZ]+)\s+(\S+)$")


def parse_vcd(path, name_filter=None):
    """Parse a VCD file.

    name_filter: optional callable(full_name) -> bool to restrict which
    signals are materialized (saves memory on large dumps). If None, every
    signal is kept.

    Returns: dict full_name -> {"width": int, "times": np.ndarray[int64]
    (in VCD timescale units), "values": np.ndarray[int64] (raw unsigned),
    "timescale_s": float}
    """
    id_to_name = {}
    id_to_width = {}
    changes = {}
    scope_stack = []
    current_time = 0
    timescale_s = 1e-9
    expect_timescale = False

    with open(path, "r") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            c0 = line[0]
            if expect_timescale and c0 != "$":
                # $timescale's "<num><unit>" value is on its own line, e.g.:
                #   $timescale
                #       1ps
                #   $end
                m = re.search(r"(\d+)\s*([a-z]+)", line)
                if m:
                    num, unit = m.groups()
                    timescale_s = int(num) * _TS_MULT.get(unit, 1e-9)
                expect_timescale = False
                continue
            if c0 == "$":
                if line.startswith("$scope"):
                    parts = line.split()
                    scope_stack.append(parts[2])
                elif line.startswith("$upscope"):
                    if scope_stack:
                        scope_stack.pop()
                elif line.startswith("$var"):
                    parts = line.split()
                    width = int(parts[2])
                    vid = parts[3]
                    vname = parts[4]
                    full = ".".join(scope_stack + [vname])
                    if name_filter is None or name_filter(full):
                        id_to_name.setdefault(vid, full)
                        id_to_width.setdefault(vid, width)
                        changes.setdefault(vid, [])
                elif line.startswith("$timescale"):
                    # value may be on this same line ("$timescale 1ns $end")
                    # or on the following line (Icarus's multi-line style)
                    m = re.search(r"(\d+)\s*([a-z]+)", line)
                    if m:
                        num, unit = m.groups()
                        timescale_s = int(num) * _TS_MULT.get(unit, 1e-9)
                    else:
                        expect_timescale = True
                continue
            if c0 == "#":
                current_time = int(line[1:])
                continue
            if c0 in "01xXzZ":
                vid = line[1:]
                if vid in changes:
                    val = 1 if c0 == "1" else 0
                    changes[vid].append((current_time, val))
                continue
            m = _VECTOR_RE.match(line)
            if m:
                bits, vid = m.groups()
                if vid in changes:
                    bits_clean = bits.replace("x", "0").replace("X", "0").replace("z", "0").replace("Z", "0")
                    val = int(bits_clean, 2) if bits_clean else 0
                    changes[vid].append((current_time, val))

    result = {}
    for vid, name in id_to_name.items():
        pts = changes.get(vid, [])
        if not pts:
            continue
        times = np.array([p[0] for p in pts], dtype=np.int64)
        # uint64, not int64: some internal signals are a full 64 bits wide
        # (e.g. red_pitaya_product_sat.v's `product`), and a raw unsigned
        # bit pattern with the top bit set exceeds int64's range.
        values = np.array([p[1] for p in pts], dtype=np.uint64)
        result[name] = {
            "width": id_to_width[vid],
            "times": times,
            "values": values,
            "timescale_s": timescale_s,
        }
    return result


def hold_sample(signal, at_times):
    """zero-order-hold resample of a parsed signal's sparse changes onto `at_times`
    (array of VCD-timescale integer times, e.g. every posedge of clk)."""
    idx = np.searchsorted(signal["times"], at_times, side="right") - 1
    idx = np.clip(idx, 0, len(signal["values"]) - 1)
    return signal["values"][idx]


def decode_signed(raw_values, bits):
    """two's complement decode of raw unsigned ints of given bit width (up to 64)"""
    raw_values = np.asarray(raw_values, dtype=np.uint64)
    if bits >= 64:
        # bit-reinterpretation (not a value cast) gives correct two's
        # complement semantics without overflowing int64's range
        return raw_values.view(np.int64)
    half = np.uint64(1) << np.uint64(bits - 1)
    full = np.int64(1) << np.int64(bits)
    signed = raw_values.astype(np.int64)  # safe: values are < 2**63 since bits<64
    return np.where(raw_values >= half, signed - full, signed)


def decode_fixed(raw_values, bits, norm=1.0, signed=True):
    """decode raw register values into physical float using the same
    convention as pyrpl.attributes.FloatRegister.to_python: value = signed(raw)/norm
    """
    if signed:
        v = decode_signed(raw_values, bits)
    else:
        v = np.asarray(raw_values, dtype=np.int64) & ((1 << bits) - 1)
    return v.astype(np.float64) / norm


def find(parsed, suffix):
    """convenience: find the (first) full signal name ending with `suffix`
    (e.g. 'dut.error') among parsed VCD signals; raises KeyError if none/multiple ambiguous"""
    matches = [k for k in parsed if k.endswith(suffix)]
    if not matches:
        raise KeyError(f"no VCD signal found ending with {suffix!r}. Available: {sorted(parsed)[:20]}...")
    if len(matches) > 1:
        # prefer the shortest (most specific / least nested duplicate)
        matches.sort(key=len)
    return matches[0]
