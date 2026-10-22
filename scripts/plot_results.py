#!/usr/bin/env python3
"""Write Figure 2 (rumour diffusion) as SVG from emergence JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean, pstdev


def band(xs):
    if not xs:
        return 0.0, 0.0
    mu = mean(xs)
    sd = pstdev(xs) if len(xs) > 1 else 0.0
    return mu, 1.96 * sd / (len(xs) ** 0.5) if len(xs) > 1 else (mu, 0.0)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("src")
    p.add_argument("--out", default="figs/diffusion.svg")
    args = p.parse_args()
    runs = json.loads(Path(args.src).read_text(encoding="utf-8"))
    hours = min(len(r["hourly"]) for r in runs)
    series = {"enslaved": [], "free_coloured": [], "institutional": []}
    for h in range(hours):
        for g in series:
            vals = [r["hourly"][h].get("aware", {}).get(g, 0.0) for r in runs]
            series[g].append(band(vals))

    w, ht = 720, 440
    pad_l, pad_r, pad_t, pad_b = 58, 24, 48, 56
    inner_w, inner_h = w - pad_l - pad_r, ht - pad_t - pad_b
    colors = {"enslaved": "#2F5D8A", "free_coloured": "#2E8B57", "institutional": "#6B6B6B"}
    labels = {"enslaved": "enslaved", "free_coloured": "free coloured", "institutional": "institutional"}

    def xy(h, mu):
        x = pad_l + h * inner_w / max(1, hours - 1)
        y = pad_t + (1 - mu) * inner_h
        return x, y

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{ht}" font-family="Inter, DejaVu Sans, sans-serif">',
        f'<rect width="{w}" height="{ht}" fill="#f7f5f0"/>',
        f'<text x="{w/2}" y="28" text-anchor="middle" font-size="15" font-weight="600">'
        "Rumour diffusion after the Salt Cove sloop is set to loading</text>",
        f'<line x1="{pad_l}" y1="{ht-pad_b}" x2="{w-pad_r}" y2="{ht-pad_b}" stroke="#333"/>',
        f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{ht-pad_b}" stroke="#333"/>',
    ]
    for frac, lab in ((0, "0"), (0.5, "0.5"), (1, "1.0")):
        y = pad_t + (1 - frac) * inner_h
        parts.append(f'<line x1="{pad_l-4}" y1="{y}" x2="{w-pad_r}" y2="{y}" stroke="#ddd"/>')
        parts.append(f'<text x="{pad_l-8}" y="{y+4}" text-anchor="end" font-size="11">{lab}</text>')
    # market-day markers: first Sunday is hour 139+12 from Mon 05:00 ≈ 151; we snap at 24*6=144
    for day in (6, 13):
        h = min(hours - 1, day * 24)
        x, _ = xy(h, 0)
        parts.append(f'<line x1="{x}" y1="{pad_t}" x2="{x}" y2="{ht-pad_b}" stroke="#C0392B" stroke-dasharray="4 4" opacity=".6"/>')
        parts.append(f'<text x="{x+4}" y="{pad_t+12}" font-size="10" fill="#C0392B">market</text>')
    for i, (g, pts) in enumerate(series.items()):
        d = []
        for h, (mu, _ci) in enumerate(pts):
            x, y = xy(h, mu)
            d.append(f"{x:.1f},{y:.1f}")
        parts.append(
            f'<polyline fill="none" stroke="{colors[g]}" stroke-width="2.4" points="{" ".join(d)}"/>'
        )
        parts.append(
            f'<rect x="{w-210}" y="{64+i*20}" width="12" height="12" fill="{colors[g]}"/>'
            f'<text x="{w-194}" y="{74+i*20}" font-size="13">{labels[g]}</text>'
        )
    parts.append(f'<text x="{w/2}" y="{ht-18}" text-anchor="middle" font-size="12">in-world hours from rumour seed (N=25, 5 seeds)</text>')
    parts.append(
        f'<text x="16" y="{ht/2}" transform="rotate(-90 16 {ht/2})" text-anchor="middle" font-size="12">share of agents aware of the sloop</text>'
    )
    parts.append("</svg>")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(parts), encoding="utf-8")
    print("wrote", out)


if __name__ == "__main__":
    main()
