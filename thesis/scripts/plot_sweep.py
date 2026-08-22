#!/usr/bin/env python3
"""Plot latency/throughput distributions vs offered sessions/s for one workload.

Our use case: open-loop session sweeps against a single replica. Each stage offers
a fixed sessions/s (the x-axis); we want to see where latency knees so we can state
a sustainable rate. We deliberately do NOT plot achieved-sessions/s as an outcome
(fragile, ambiguous unit); we plot the latency/throughput distribution vs the
OFFERED rate and let the knee speak.

Why box-and-whisker: a single p50/p99 line hides the spread. inference-perf already
emits a full percentile summary per stage (p1..p99.9, min/max/mean), so we render a
proper box per stage straight from those precomputed stats (matplotlib `bxp`, no raw
samples needed):
  * box   = p25 .. p75, median line at p50
  * whisk = p1 .. p99 (a wide tail without single-sample min/max noise; no fliers)
  * mean  = diamond marker

Three panels in a row: TTFT, inter-token latency, throughput.

The throughput panel plots BOTH input and output tokens/s on a dual y-axis. Which
one is the flat ceiling tells you the bottleneck without knowing the workload up
front: a prefill-bound workload (huge RAG prompts) plateaus on input tok/s while
output tok/s wobbles with output-length variance; a decode-bound workload plateaus
on output tok/s. We plot both so the reader reads the bottleneck straight off the
plateau. (input tok/s is ~40x output here, hence separate axes so both are legible.)

Key gotchas this script handles:
  * The request-lifecycle file's `load_summary.requested_rate`/`achieved_rate` are
    REQUEST rates, not session rates. The true offered sessions/s lives in the
    session-lifecycle file at `stage_metadata.session_rate`. We x-axis on that.
  * Stage 0 is a warmup (JIT absorption) and is EXCLUDED by default.
  * The x-axis is CATEGORICAL (one box per stage, evenly spaced) so boxes stay
    readable even when the offered rates are unevenly spaced; the tick label is the
    actual offered sessions/s.

Reads a results dir containing stage_<N>_lifecycle_metrics.json and
stage_<N>_session_lifecycle_metrics.json. Writes one PNG per workload.

Usage:
  plot_sweep.py <results_dir> [-o out.png] [--include-warmup] [--title NAME]
"""
import argparse
import glob
import json
import os
import re
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch


def _fmt(v):
    """Compact label for an annotated value (drops trailing zeros)."""
    if v is None:
        return ""
    if v >= 100:
        return f"{v:.0f}"
    return f"{v:.1f}"


# Legend proxies describing the (non-standard) box anatomy, drawn in neutral gray so
# they read as a schematic rather than binding to any one panel's series color.
def _box_legend_handles():
    g = "0.35"
    return [
        Line2D([0], [0], color="black", lw=1.5, label="median (p50)"),
        Line2D([0], [0], marker="D", color="none", markerfacecolor=g, markersize=6, label="mean"),
        Patch(facecolor=g, alpha=0.35, edgecolor=g, label="box: p25–p75"),
        Line2D([0], [0], color=g, lw=1.2, label="whiskers: p1–p99"),
    ]


def _bxp_stat(dist, label, scale=1.0):
    """Turn a precomputed percentile summary into a matplotlib bxp stat dict.

    dist is inference-perf's stats object (mean/median/pN/...). Returns None if the
    distribution is missing so the caller can leave a gap for that stage.

    Box = p25..p75, median at p50, whiskers span p1..p99 (a wide tail without the
    single-sample noise of min/max). We do NOT use fliers: p1/p99-as-fliers landed
    right on the whisker caps and were visually redundant.
    """
    if not dist:
        return None
    need = ("p25", "median", "p75", "p1", "p99")
    if any(dist.get(k) is None for k in need):
        return None
    return {
        "label": label,
        "med": dist["median"] * scale,
        "q1": dist["p25"] * scale,
        "q3": dist["p75"] * scale,
        "whislo": dist["p1"] * scale,
        "whishi": dist["p99"] * scale,
        "mean": (dist["mean"] * scale) if dist.get("mean") is not None else None,
        "fliers": [],
    }


def load_stages(results_dir, include_warmup):
    """Return per-stage dicts sorted by stage id, each with the offered sessions/s
    and the raw percentile distributions we render."""
    req_files = glob.glob(os.path.join(results_dir, "stage_*_lifecycle_metrics.json"))
    # Exclude the *_session_lifecycle_metrics.json siblings from this glob.
    req_files = [f for f in req_files if "session" not in os.path.basename(f)]
    stages = []
    for rf in req_files:
        m = re.search(r"stage_(\d+)_lifecycle_metrics\.json$", os.path.basename(rf))
        if not m:
            continue
        sid = int(m.group(1))
        sf = os.path.join(results_dir, f"stage_{sid}_session_lifecycle_metrics.json")
        req = json.load(open(rf))
        sess = json.load(open(sf)) if os.path.exists(sf) else {}

        # x-axis: OFFERED sessions/s (from the session file, not the request file).
        offered = (sess.get("stage_metadata") or {}).get("session_rate")
        if offered is None:
            offered = (req.get("load_summary") or {}).get("requested_rate")

        lat = (req.get("successes") or {}).get("latency") or {}
        thr = (req.get("successes") or {}).get("throughput") or {}

        stages.append(
            {
                "sid": sid,
                "offered": offered,
                "ttft": lat.get("time_to_first_token") or {},
                "itl": lat.get("inter_token_latency") or {},
                "out_tps": thr.get("output_tokens_per_sec"),
                "in_tps": thr.get("input_tokens_per_sec"),
            }
        )
    stages.sort(key=lambda s: s["sid"])
    if not include_warmup and stages:
        stages = [s for s in stages if s["sid"] != 0]  # stage 0 is warmup
    return stages


def _draw_box_panel(ax, stages, dist_key, scale, ylabel, title, color, logy=False):
    """Render one box-per-stage panel from precomputed percentiles.

    logy=True puts the y-axis on a log scale -- latency tails span ~2 orders of
    magnitude (an ~11ms ITL floor vs a >400ms saturated whisker), and a linear
    axis crushes the low-rate boxes flat against zero.
    """
    positions, stats, labels = [], [], []
    for i, s in enumerate(stages):
        label = f"{s['offered']:g}" if s["offered"] is not None else "?"
        st = _bxp_stat(s[dist_key], label, scale)
        labels.append(label)
        if st is not None:
            st["_pos"] = i
            positions.append(i)
            stats.append(st)

    if stats:
        bp = ax.bxp(
            stats,
            positions=positions,
            widths=0.6,
            showmeans=True,
            meanprops={"marker": "D", "markerfacecolor": color, "markeredgecolor": "none", "markersize": 5},
            medianprops={"color": "black", "linewidth": 1.5},
            boxprops={"facecolor": color, "alpha": 0.35, "edgecolor": color},
            whiskerprops={"color": color, "linewidth": 1.2},
            capprops={"color": color, "linewidth": 1.2},
            patch_artist=True,
        )

        # Annotate each median so the number is readable straight off the chart.
        for st in stats:
            ax.annotate(
                _fmt(st["med"]),
                xy=(st["_pos"], st["med"]),
                xytext=(0, 4),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=7,
                color="black",
            )

    ax.set_xticks(range(len(stages)))
    ax.set_xticklabels(labels)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.set_xlabel("sessions/s")
    if logy:
        ax.set_yscale("log")
    ax.grid(True, axis="y", alpha=0.3, which="both" if logy else "major")


def plot(stages, title, out):
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    fig.suptitle(title, fontsize=13)

    # TTFT: earliest knee (prefill / schedule-queue backup). Log-y for the tail.
    _draw_box_panel(axes[0], stages, "ttft", 1000.0, "TTFT (ms)", "Time to first token", "tab:blue", logy=True)
    # ITL: decode-batch saturation knee. Log-y for the tail.
    _draw_box_panel(axes[1], stages, "itl", 1000.0, "ITL (ms)", "Inter-token latency", "tab:orange", logy=True)

    # Throughput is a scalar per stage (no distribution), so lines read best. We
    # plot input AND output tokens/s on a dual y-axis: whichever plateaus is the
    # bottleneck (input -> prefill-bound, output -> decode-bound). The two differ by
    # ~40x for RAG workloads, so separate axes keep both legible. Output tok/s is
    # composition-sensitive (it tracks the output length of whichever sessions
    # cleared the queue within the window), so read its plateau, not its wobble.
    ax = axes[2]

    def _line(axis, key, color, marker):
        px = [i for i, s in enumerate(stages) if s.get(key) is not None]
        py = [s[key] for s in stages if s.get(key) is not None]
        axis.plot(px, py, marker + "-", color=color)
        for x, y in zip(px, py):
            axis.annotate(
                _fmt(y), xy=(x, y), xytext=(0, 5), textcoords="offset points",
                ha="center", va="bottom", fontsize=7, color=color,
            )
        return px, py

    in_color, out_color = "tab:purple", "tab:green"
    _, in_ys = _line(ax, "in_tps", in_color, "s")
    ax.set_ylabel("input tokens/s", color=in_color)
    ax.tick_params(axis="y", labelcolor=in_color)

    ax2 = ax.twinx()
    _, out_ys = _line(ax2, "out_tps", out_color, "o")
    ax2.set_ylabel("output tokens/s", color=out_color)
    ax2.tick_params(axis="y", labelcolor=out_color)

    ax.set_ylim(0, max(in_ys) * 1.1 if in_ys else None)
    ax2.set_ylim(0, max(out_ys) * 1.1 if out_ys else None)

    ax.set_xticks(range(len(stages)))
    ax.set_xticklabels([f"{s['offered']:g}" if s["offered"] is not None else "?" for s in stages])
    ax.set_title("Throughput (input vs output)")
    ax.set_xlabel("sessions/s")
    ax.grid(True, axis="y", alpha=0.3)

    # Shared box-anatomy legend below the panels (median values are annotated
    # in-place; this explains the box/whisker/flier percentile mapping).
    fig.legend(
        handles=_box_legend_handles(),
        loc="lower center",
        ncol=4,
        frameon=False,
        fontsize=9,
        bbox_to_anchor=(0.5, 0.0),
    )

    fig.tight_layout(rect=(0, 0.06, 1, 0.95))
    fig.savefig(out, dpi=130)
    offered = [s["offered"] for s in stages]
    print(f"wrote {out}  ({len(stages)} stages, offered sessions/s = {offered})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("results_dir", help="dir with stage_*_lifecycle_metrics.json")
    ap.add_argument("-o", "--out", default=None, help="output PNG (default: <dir>/sweep.png)")
    ap.add_argument("--include-warmup", action="store_true", help="keep stage 0")
    ap.add_argument("--title", default=None, help="plot title (default: dir name)")
    a = ap.parse_args()

    stages = load_stages(a.results_dir, a.include_warmup)
    if not stages:
        sys.exit(f"no stage metrics found in {a.results_dir}")
    out = a.out or os.path.join(a.results_dir, "sweep.png")
    title = a.title or os.path.basename(os.path.normpath(a.results_dir))
    plot(stages, title, out)


if __name__ == "__main__":
    main()
