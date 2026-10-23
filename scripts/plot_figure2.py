#!/usr/bin/env python3
"""Draw Figure 2 of the paper (leak diffusion and Chair strictness) from paper_exps.json."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

BLUE, ORANGE, RED, GREY = "#3A78C9", "#E08A2E", "#C4505A", "#7F7F7F"
SHADE = "#E6E6E6"

plt.rcParams.update(
    {
        "font.family": "STIXGeneral",
        "mathtext.fontset": "stix",
        "font.size": 9,
        "axes.labelsize": 10,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "legend.fontsize": 8,
        "axes.linewidth": 0.8,
        "lines.linewidth": 1.8,
        "lines.markersize": 6,
        "lines.markeredgewidth": 0.8,
        "lines.markeredgecolor": "#222222",
        "pdf.fonttype": 42,
    }
)


def styled_axes():
    # Both panels share one fixed size so that they scale identically in the paper.
    fig, ax = plt.subplots(figsize=(3.4, 2.3), layout="constrained")
    ax.grid(True, linestyle="--", linewidth=0.6, color="#CCCCCC")
    ax.set_axisbelow(True)
    return fig, ax


def legend_on_top(ax, ncol):
    ax.figure.legend(
        loc="outside upper center",
        ncol=ncol,
        frameon=False,
        handlelength=2.2,
        columnspacing=1.0,
        handletextpad=0.4,
    )


def diffusion(curve: list[dict], out: Path) -> None:
    days = [c["day"] for c in curve]
    pct = lambda key: [100 * c["aware"].get(key, 0.0) for c in curve]
    fig, ax = styled_axes()
    ax.axvspan(4.5, 6.5, color=SHADE, zorder=0)
    ax.text(5.5, 45, "weekend\n(no sitting)", ha="center", va="center", fontsize=8, color="#666666")
    ax.plot(days, pct("member"), "-o", color=BLUE, label="Members")
    ax.plot(days, pct("press"), "-s", color=ORANGE, label="Press")
    ax.plot(days, pct("government"), "-^", color=RED, label="Ministers")
    ax.plot(days, pct("institutional"), "--D", color=GREY, markersize=5.5, label="Chair / griffier")
    ax.set_xlim(-0.3, max(days) + 0.3)
    ax.set_ylim(-3, 105)
    ax.set_xticks(days)
    ax.set_yticks(range(0, 101, 20))
    ax.set_xlabel("Day of the S1 week")
    ax.set_ylabel("Aware of the leak (%)")
    legend_on_top(ax, ncol=4)
    fig.savefig(out)
    plt.close(fig)


def strictness(rows: list[dict], out: Path) -> None:
    levels = sorted({r["chair_strictness"] for r in rows})
    xs = list(range(len(levels)))
    fig, ax = styled_axes()
    default = levels.index(1.0)
    ax.axvspan(default - 0.3, default + 0.3, color=SHADE, zorder=0)
    series = [(0.05, "-o", BLUE), (0.18, "--s", ORANGE)]
    top = 0.0
    for distort, style, color in series:
        ys = []
        for s in levels:
            hit = [r for r in rows if r["chair_strictness"] == s and abs(r["distort"] - distort) < 1e-9]
            ys.append(100 * hit[0]["floor_mention"] if hit else float("nan"))
        top = max(top, max(ys))
        ax.plot(xs, ys, style, color=color, label=f"distortion {distort:g}")
    ymax = max(5.0, top * 1.15)
    ax.set_ylim(-0.06 * ymax, ymax)
    ax.text(default, ymax * 0.95, "default", ha="center", va="top", fontsize=8, color="#666666")
    ax.set_xticks(xs)
    ax.set_xticklabels([f"{s:g}" + r"$\times$" for s in levels])
    ax.set_xlim(-0.4, len(levels) - 0.6)
    ax.set_xlabel("Chair strictness")
    ax.set_ylabel("Floor mention (%)")
    legend_on_top(ax, ncol=2)
    fig.savefig(out)
    plt.close(fig)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--src", default="runs/kamer/paper_exps.json")
    p.add_argument("--out-dir", default="WWW2027_Parliamentary_Debate/figure")
    args = p.parse_args()
    data = json.loads(Path(args.src).read_text(encoding="utf-8"))
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    diffusion(data["curves"]["full"], out / "fig_diffusion.pdf")
    strictness(data["interventions"], out / "fig_strictness.pdf")
    print("wrote", out / "fig_diffusion.pdf", "and", out / "fig_strictness.pdf")


if __name__ == "__main__":
    main()
