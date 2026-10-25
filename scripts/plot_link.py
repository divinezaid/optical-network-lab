"""Generate Stage 1 plots into plots/.

    python scripts/plot_link.py

1. constellations.png  - the three Gray-coded constellations, clean and noisy
2. ber_vs_osnr.png     - theory curves, Monte Carlo points, FEC threshold
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from linkmodel import (  # noqa: E402
    HD_FEC_THRESHOLD,
    Format,
    ber_from_osnr,
    constellation,
    modulate,
    osnr_to_snr_db,
    required_osnr_db,
    simulate_ber_osnr,
)

OUT = ROOT / "plots"

# One fixed colour per format (categorical slots 1-3), muted ink for text.
COLORS = {Format.QPSK: "#2a78d6", Format.QAM8: "#eb6834", Format.QAM16: "#1baf7a"}
INK, INK_MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"

plt.rcParams.update(
    {
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "axes.edgecolor": GRID,
        "axes.labelcolor": INK_MUTED,
        "axes.titlecolor": INK,
        "xtick.color": INK_MUTED,
        "ytick.color": INK_MUTED,
        "grid.color": GRID,
        "font.size": 10,
        "axes.spines.top": False,
        "axes.spines.right": False,
    }
)


def plot_constellations(path: Path, osnr_db: float = 22.0) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.3))
    rng = np.random.default_rng(0)
    snr = 10 ** (osnr_to_snr_db(osnr_db) / 10)
    sigma = np.sqrt(1 / snr / 2)

    for ax, fmt in zip(axes, Format):
        c = constellation(fmt)
        bits = rng.integers(0, 2, size=c.bits_per_symbol * 3000, dtype=np.int8)
        rx = modulate(bits, c) + sigma * (rng.standard_normal(3000) + 1j * rng.standard_normal(3000))

        ax.scatter(rx.real, rx.imag, s=2, color=COLORS[fmt], alpha=0.25, linewidths=0)
        ax.scatter(c.points.real, c.points.imag, s=40, color=INK, zorder=3)
        for p, label in zip(c.points, c.labels):
            ax.annotate(
                "".join(map(str, label)),
                (p.real, p.imag),
                textcoords="offset points",
                xytext=(0, 8),
                ha="center",
                fontsize=8,
                color=INK,
                fontfamily="monospace",
                bbox={"boxstyle": "round,pad=0.15", "facecolor": SURFACE, "edgecolor": "none", "alpha": 0.85},
                zorder=4,
            )
        ax.set_title(f"{fmt.value}  ({c.bits_per_symbol} bits/symbol)")
        ax.set_xlabel("In-phase (I)")
        ax.set_aspect("equal")
        ax.set_xlim(-1.9, 1.9)
        ax.set_ylim(-1.9, 1.9)
        ax.grid(True, linewidth=0.6)
    axes[0].set_ylabel("Quadrature (Q)")
    fig.suptitle(
        f"Gray-coded constellations, unit energy. Cloud: received symbols at OSNR {osnr_db:.0f} dB",
        color=INK_MUTED,
        fontsize=10,
    )
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def plot_ber_vs_osnr(path: Path) -> None:
    osnr = np.linspace(4, 26, 200)
    fig, ax = plt.subplots(figsize=(9, 5.6))

    ax.axhline(HD_FEC_THRESHOLD, color=INK_MUTED, linewidth=1, linestyle="--")
    ax.text(4.2, HD_FEC_THRESHOLD * 1.25, f"HD-FEC threshold {HD_FEC_THRESHOLD:.1e}", color=INK_MUTED, fontsize=9)

    for fmt in Format:
        color = COLORS[fmt]
        ax.semilogy(osnr, ber_from_osnr(fmt, osnr), color=color, linewidth=2, label=f"{fmt.value} theory")

        mc_osnr = np.arange(6, 25, 2.0)
        mc_osnr = mc_osnr[ber_from_osnr(fmt, mc_osnr) > 2e-5]  # keep runtime sane
        mc = [simulate_ber_osnr(fmt, o, min_errors=300, seed=1) for o in mc_osnr]
        ax.semilogy(
            mc_osnr,
            [r.ber for r in mc],
            "o",
            markersize=7,
            markerfacecolor=color,
            markeredgecolor=SURFACE,
            markeredgewidth=1.5,
            label=f"{fmt.value} Monte Carlo",
        )

        req = required_osnr_db(fmt)
        ax.plot([req, req], [1e-6, HD_FEC_THRESHOLD], color=color, linewidth=1, linestyle=":")
        ax.annotate(
            f"{fmt.value}\n{req:.1f} dB",
            (req, 1.4e-6),
            ha="center",
            fontsize=8,
            color=INK,
        )

    ax.set_ylim(1e-6, 0.5)
    ax.set_xlim(4, 26)
    ax.set_xlabel("OSNR (dB, 0.1 nm reference)")
    ax.set_ylabel("Pre-FEC bit error rate")
    ax.set_title("BER vs OSNR, 32 GBaud dual-polarisation, AWGN", loc="left")
    ax.grid(True, which="major", linewidth=0.6)
    ax.legend(frameon=False, fontsize=8, ncol=3, loc="upper right")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    plot_constellations(OUT / "constellations.png")
    plot_ber_vs_osnr(OUT / "ber_vs_osnr.png")
    print(f"wrote plots to {OUT}")


if __name__ == "__main__":
    main()
