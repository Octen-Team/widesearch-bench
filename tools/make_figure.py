#!/usr/bin/env python3
"""
WideSearch-Bench results figure.

Layout (option 3):
  Row 1 : [ absolute Entity-F1, pooled + strict, marginal 95% CI ] [ paired ΔF1 vs broad_search ]
  Row 2 : [ end-to-end latency ] [ downstream tokens ] [ search-API cost ]

The two F1 panels answer different questions on purpose:
  - left  : how good is each arm (marginal CIs -> read the level)
  - right : is the gap real (paired CIs -> read the significance)
Overlapping marginal intervals on the left do NOT contradict a significant
paired delta on the right; the paired test removes per-question difficulty
variance, which is most of the marginal spread.

Usage:  python3 make_figure.py [--out PATH]
"""

import argparse

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch

# ----------------------------------------------------------------------------
# DATA  — everything below is transcribed from results/
# ----------------------------------------------------------------------------

ARMS = ["Octen\nbroad_search", "Parallel\nturbo agent", "Exa\ninstant agent", "Tavily\nbasic agent"]
SHORT = ["Octen", "Parallel", "Exa", "Tavily"]

F1_POOLED = [0.548, 0.533, 0.521, 0.505]
F1_STRICT = [0.545, 0.503, 0.490, 0.480]

LATENCY_S = [8.4, 41.1, 40.5, 46.1]
TOKENS = [8043, 19327, 19679, 20088]
COST_PER_1K = [8.0, 7.8, 54.1, 62.8]

# Paired deltas vs broad_search, pooled gold: (point, ci_lo, ci_hi, holm_p)
PAIRED_POOLED = {
    "Parallel": (0.015, -0.014, 0.045, 0.31),
    "Exa":      (0.028, -0.006, 0.060, 0.20),
    "Tavily":   (0.044, +0.012, 0.075, 0.028),
}
# Strict gold deltas (point estimates only; Holm p <= 0.007 for all three)
PAIRED_STRICT_POINT = {"Parallel": 0.042, "Exa": 0.055, "Tavily": 0.065}

# ---------------------------------------------------------------------------
# >>> REPLACE THESE <<<
# Per-arm MARGINAL 95% bootstrap CIs for pooled F1, as half-widths.
# These are placeholders derived from an assumed per-question sd of 0.30 at
# n=313 (SE ~ 0.017 -> +-0.033). Paste your real values and set
# PLACEHOLDER_CIS = False to drop the watermark.
PLACEHOLDER_CIS = False
# real per-arm marginal 95% bootstrap CI half-widths (10k resamples over 313 items)
CI_POOLED_HALFWIDTH = [0.032, 0.034, 0.035, 0.035]
CI_STRICT_HALFWIDTH = [0.034, 0.035, 0.036, 0.035]
# ---------------------------------------------------------------------------

TEAL = "#0F8A80"
TEAL_LIGHT = "#7CC5BE"
GREY = "#6B7280"
GREY_LIGHT = "#C3C8D0"
INK = "#1F2933"
RULE = "#D7DBE0"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 9,
    "axes.edgecolor": RULE,
    "axes.labelcolor": INK,
    "text.color": INK,
    "xtick.color": INK,
    "ytick.color": INK,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
})


def style(ax, title, subtitle=None):
    ax.set_title(title, fontsize=10.5, fontweight="bold", loc="left", pad=14 if subtitle else 8)
    if subtitle:
        ax.text(0, 1.02, subtitle, transform=ax.transAxes, fontsize=8,
                color=GREY, va="bottom", ha="left")
    ax.tick_params(length=0)
    ax.grid(axis="y", color=RULE, lw=0.7, alpha=0.8)
    ax.set_axisbelow(True)


def bar_panel(ax, values, title, subtitle, fmt, ylim_pad=1.28):
    colors = [TEAL] + [GREY_LIGHT] * 3
    bars = ax.bar(range(4), values, color=colors, width=0.62,
                  edgecolor="white", linewidth=0.8)
    bars[0].set_edgecolor(TEAL)
    for x, v in zip(range(4), values):
        ax.text(x, v * 1.03, fmt(v), ha="center", va="bottom",
                fontsize=8.5, fontweight="bold" if x == 0 else "normal",
                color=TEAL if x == 0 else INK)
    ax.set_xticks(range(4))
    ax.set_xticklabels(SHORT, fontsize=8.5)
    ax.set_ylim(0, max(values) * ylim_pad)
    style(ax, title, subtitle)


def main(out_path):
    fig = plt.figure(figsize=(13.2, 7.4))
    gs = fig.add_gridspec(
        2, 3, height_ratios=[1.15, 1.0], width_ratios=[1.55, 0.95, 0.95],
        hspace=0.52, wspace=0.34,
        left=0.055, right=0.968, top=0.855, bottom=0.075,
    )

    # ---------------- Panel A: absolute F1, pooled + strict -----------------
    axA = fig.add_subplot(gs[0, 0:2])
    x = np.arange(4)
    w = 0.34
    ebar = dict(elinewidth=1.2, capsize=3.5, capthick=1.2, ecolor=INK, alpha=0.85)

    axA.bar(x - w / 2, F1_POOLED, w, yerr=CI_POOLED_HALFWIDTH,
            color=[TEAL] + [GREY_LIGHT] * 3, edgecolor="white", linewidth=0.8,
            error_kw=ebar, label="pooled gold")
    axA.bar(x + w / 2, F1_STRICT, w, yerr=CI_STRICT_HALFWIDTH,
            color=[TEAL_LIGHT] + [GREY] * 3, edgecolor="white", linewidth=0.8,
            hatch="///", error_kw=ebar, label="strict gold")

    for xi, (p, s) in enumerate(zip(F1_POOLED, F1_STRICT)):
        axA.text(xi - w / 2, p + CI_POOLED_HALFWIDTH[xi] + 0.008, f"{p:.3f}",
                 ha="center", fontsize=8, fontweight="bold" if xi == 0 else "normal")
        axA.text(xi + w / 2, s + CI_STRICT_HALFWIDTH[xi] + 0.008, f"{s:.3f}",
                 ha="center", fontsize=8, color=GREY)

    axA.set_xticks(x)
    axA.set_xticklabels(ARMS, fontsize=8.5)
    axA.set_ylabel("Entity-F1")
    axA.set_ylim(0, 0.68)
    style(axA, "Answer quality  —  Entity-F1",
          "bars = mean; error bars = marginal 95% bootstrap CI (see note)")
    axA.legend(handles=[
        Patch(facecolor=TEAL, label="pooled gold"),
        Patch(facecolor=TEAL_LIGHT, hatch="///", label="strict gold"),
    ], loc="upper right", frameon=False, fontsize=8.5, ncol=2)

    # ---------------- Panel B: paired deltas --------------------------------
    axB = fig.add_subplot(gs[0, 2])
    order = ["Parallel", "Exa", "Tavily"]
    ypos = np.arange(len(order))[::-1]

    axB.axvline(0, color=INK, lw=1.0, alpha=0.6, zorder=1)
    for yi, name in zip(ypos, order):
        pt, lo, hi, p = PAIRED_POOLED[name]
        sig = p < 0.05
        col = TEAL if sig else GREY
        axB.plot([lo, hi], [yi, yi], color=col, lw=2.6, solid_capstyle="round", zorder=3)
        axB.plot([pt], [yi], "o", color=col, ms=7, zorder=4,
                 markeredgecolor="white", markeredgewidth=1.1)
        axB.plot([PAIRED_STRICT_POINT[name]], [yi], "D", color=col, ms=5,
                 alpha=0.55, zorder=4, markeredgecolor="white", markeredgewidth=0.8)
        axB.text(hi + 0.006, yi, f"{'*' if sig else 'n.s.'}  p={p:.2f}",
                 va="center", fontsize=8, color=col,
                 fontweight="bold" if sig else "normal")

    axB.set_yticks(ypos)
    axB.set_yticklabels([f"vs {n}" for n in order], fontsize=8.5)
    axB.set_xlabel("ΔF1  (broad_search − competitor)")
    axB.set_xlim(-0.048, 0.130)
    axB.set_xticks([-0.025, 0.0, 0.025, 0.05, 0.075])
    axB.set_xticklabels(["−.025", "0", ".025", ".05", ".075"], fontsize=8)
    axB.grid(axis="x", color=RULE, lw=0.7, alpha=0.8)
    axB.grid(axis="y", visible=False)
    axB.set_axisbelow(True)
    axB.tick_params(length=0)
    axB.set_title("Is the gap real?  —  paired test", fontsize=10.5,
                  fontweight="bold", loc="left", pad=14)
    axB.text(0, 1.02, "● pooled (95% CI, Holm-corrected)   ◆ strict, point est.",
             transform=axB.transAxes, fontsize=8, color=GREY, va="bottom")

    # ---------------- Row 2 --------------------------------------------------
    axC = fig.add_subplot(gs[1, 0])
    bar_panel(axC, LATENCY_S, "End-to-end latency",
              "seconds per question, 5-way concurrency  ·  structural",
              lambda v: f"{v:.1f}s")
    axC.set_ylabel("seconds")

    axD = fig.add_subplot(gs[1, 1])
    bar_panel(axD, TOKENS, "Downstream tokens",
              "client-side only  ·  structural",
              lambda v: f"{v/1000:.1f}K")
    axD.set_ylabel("tokens per question")

    axE = fig.add_subplot(gs[1, 2])
    bar_panel(axE, COST_PER_1K, "Search-API cost",
              "USD / 1k questions, PAYG  ·  rate card",
              lambda v: f"${v:.1f}")
    axE.set_ylabel("USD / 1k questions")

    # ---------------- Titles + notes ----------------------------------------
    fig.text(0.055, 0.955, "WideSearch-Bench: one broad search vs. an agent loop",
             fontsize=15, fontweight="bold", ha="left")
    fig.text(0.055, 0.915,
             "313 enumeration questions · same answering model (gpt-5-mini), prompt and scorer · "
             "~8 real queries per question in every arm",
             fontsize=9, color=GREY, ha="left")

    fig.text(0.055, 0.012,
             "Note: error bars in the left panel are marginal 95% CIs; significance comes from the paired test on the right, "
             "where overlap of marginal intervals does not imply a null result.",
             fontsize=8, color=GREY, ha="left")

    if PLACEHOLDER_CIS:
        fig.text(0.5, 0.5, "PREVIEW\nmarginal CIs are placeholders",
                 fontsize=44, color="#E11D48", alpha=0.16, ha="center", va="center",
                 rotation=24, fontweight="bold", zorder=99)

    fig.savefig(out_path, dpi=200, facecolor="white")
    fig.savefig(out_path.replace(".png", ".svg"), facecolor="white")
    print("wrote", out_path, "and", out_path.replace(".png", ".svg"))
    if PLACEHOLDER_CIS:
        print("WARNING: PLACEHOLDER_CIS is True — marginal error bars are NOT your real numbers.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="figures/widesearch_results.png")
    main(ap.parse_args().out)
