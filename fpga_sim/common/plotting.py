"""Shared matplotlib helpers for the FPGA block simulation harness."""

import matplotlib

matplotlib.use("Agg")  # headless: always save PNG, never try to open a window
import matplotlib.pyplot as plt
import numpy as np


def plot_traces(traces, out_path, title=None, xlabel="time [samples]"):
    """traces: ordered dict/list of (label, x_array, y_array, ylabel) tuples.
    Creates one subplot per trace, sharing the x-axis, and saves a PNG.
    """
    n = len(traces)
    fig, axes = plt.subplots(n, 1, figsize=(9, 2.2 * n), sharex=True)
    if n == 1:
        axes = [axes]
    for ax, (label, x, y, ylabel) in zip(axes, traces):
        ax.plot(x, y, lw=1.0)
        ax.set_ylabel(ylabel)
        ax.set_title(label, fontsize=10, loc="left")
        ax.grid(True, alpha=0.3)
    axes[-1].set_xlabel(xlabel)
    if title:
        fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    print(f"saved plot: {out_path}")


def plot_bode(freqs_hz, complex_response, out_path, title=None, model_freqs_hz=None, model_response=None):
    fig, (ax_mag, ax_phase) = plt.subplots(2, 1, figsize=(8, 6), sharex=True)
    mag_db = 20 * np.log10(np.maximum(np.abs(complex_response), 1e-12))
    phase_deg = np.angle(complex_response, deg=True)
    ax_mag.semilogx(freqs_hz, mag_db, ".", ms=3, label="simulated")
    ax_phase.semilogx(freqs_hz, phase_deg, ".", ms=3, label="simulated")
    if model_response is not None:
        model_mag = 20 * np.log10(np.maximum(np.abs(model_response), 1e-12))
        model_phase = np.angle(model_response, deg=True)
        mf = model_freqs_hz if model_freqs_hz is not None else freqs_hz
        ax_mag.semilogx(mf, model_mag, "-", lw=1.5, label="analytic model")
        ax_phase.semilogx(mf, model_phase, "-", lw=1.5, label="analytic model")
        ax_mag.legend()
        ax_phase.legend()
    ax_mag.set_ylabel("magnitude [dB]")
    ax_mag.grid(True, which="both", alpha=0.3)
    ax_phase.set_ylabel("phase [deg]")
    ax_phase.set_xlabel("frequency [Hz]")
    ax_phase.grid(True, which="both", alpha=0.3)
    if title:
        fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    print(f"saved plot: {out_path}")
