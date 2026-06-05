"""Generate publication-style plots (PNG/PDF/PGF) from simulation outputs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence
import math

import matplotlib
matplotlib.use("Agg")  # Force non-interactive backend to prevent macOS crash
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.lines import Line2D

ORDER = ["no_def", "rolling", "window", "challenge"]

# Monochrome styling for thesis/paper figures.  Distinguish modes by line
# pattern and marker, not by color, so the figures survive grayscale printing.
STYLE_MAP = {
    "no_def": {
        "color": "#000000",
        "marker": "x",
        "linestyle": ":",
        "linewidth": 1.0,
        "label": "No defense",
    },
    "rolling": {
        "color": "#000000",
        "marker": "o",
        "linestyle": "--",
        "linewidth": 1.15,
        "label": "Rolling MAC",
    },
    "window": {
        "color": "#000000",
        "marker": "s",
        "linestyle": "-",
        "linewidth": 1.25,
        "label": "Window",
    },
    "challenge": {
        "color": "#000000",
        "marker": "^",
        "linestyle": "-.",
        "linewidth": 1.1,
        "label": "Challenge-resp.",
    },
}

MARKER_KWARGS = {
    "markersize": 4.2,
    "markerfacecolor": "white",
    "markeredgewidth": 0.8,
    "markevery": 1,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render LaTeX-friendly plots for the thesis.")
    parser.add_argument("--baseline-json", default="results/ideal_p0.json", help="Baseline JSON file.")
    parser.add_argument("--ploss-json", default="results/p_loss_sweep.json", help="Packet-loss sweep JSON file.")
    parser.add_argument("--preorder-json", default="results/p_reorder_sweep.json", help="Packet-reorder sweep JSON file.")
    parser.add_argument("--window-json", default="results/window_sweep.json", help="Window sweep JSON file.")
    parser.add_argument("--fig-dir", default="figures", help="Destination directory for figures.")
    parser.add_argument(
        "--formats",
        nargs="+",
        default=["png", "pdf", "pgf"],
        help="Image formats to emit (use pgf for LaTeX).",
    )
    parser.add_argument(
        "--column-width",
        type=float,
        default=4.8,
        help="Figure width in inches (match LaTeX column width).",
    )
    parser.add_argument(
        "--scale",
        type=float,
        default=1.0,
        help="Multiply the column width for larger, two-column layouts.",
    )
    parser.add_argument("--dpi", type=int, default=400, help="Raster DPI used for PNG outputs.")
    parser.add_argument(
        "--use-tex",
        action="store_true",
        help="Enable LaTeX text rendering (requires a TeX installation).",
    )
    parser.add_argument(
        "--theme",
        choices=["paper", "slides"],
        default="paper",
        help="Styling preset. 'paper' tightens fonts for print.",
    )
    parser.add_argument(
        "--ploss-layout",
        choices=["combined", "facet"],
        default="combined",
        help="How to visualize packet-loss curves: single chart or per-mode facets.",
    )
    return parser.parse_args()


def configure_style(theme: str, use_tex: bool) -> None:
    plt.style.use("seaborn-v0_8-white")
    base_font = "serif" if theme == "paper" else "DejaVu Sans"
    plt.rcParams.update(
        {
            "font.family": base_font,
            "font.serif": ["Times New Roman", "Times", "Nimbus Roman", "DejaVu Serif"],
            "mathtext.fontset": "stix",
            "figure.dpi": 300,
            "axes.titlesize": 9,
            "axes.labelsize": 9,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "legend.fontsize": 7.5,
            "axes.titleweight": "normal",
            "axes.edgecolor": "#000000",
            "axes.linewidth": 1.1,
            "xtick.major.width": 1.0,
            "ytick.major.width": 1.0,
            "xtick.major.size": 4,
            "ytick.major.size": 4,
            "xtick.minor.width": 0.8,
            "ytick.minor.width": 0.8,
            "xtick.minor.size": 2.5,
            "ytick.minor.size": 2.5,
            "legend.frameon": False,
            "lines.solid_capstyle": "round",
            "lines.dash_capstyle": "round",
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.02,
            "pgf.texsystem": "pdflatex",
            "pgf.rcfonts": False,
            "pgf.preamble": r"\usepackage{siunitx}",
        }
    )
    if use_tex:
        plt.rcParams["text.usetex"] = True
        plt.rcParams["font.family"] = "serif"


def load_json(path: Path) -> List[Dict]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def percent_series(entries: Iterable[Dict], key: str) -> List[float]:
    return [entry[key] * 100 for entry in entries]


def standard_error_series(entries: Iterable[Dict], std_key: str, n: int = 200) -> List[float]:
    """Convert standard deviation to standard error (std/sqrt(n)) and scale to percent."""
    return [entry[std_key] * 100 / math.sqrt(n) for entry in entries]


def save_figure(fig, fig_dir: Path, stem: str, formats: Sequence[str], dpi: int) -> None:
    for ext in {fmt.lower() for fmt in formats}:
        target = fig_dir / f"{stem}.{ext}"
        fig.savefig(target, dpi=dpi if ext in {"png", "jpg"} else None)
    plt.close(fig)


def apply_axes_style(ax, *, right: bool = False, top: bool = False) -> None:
    ax.grid(False)
    ax.spines["top"].set_visible(top)
    ax.spines["right"].set_visible(right)
    ax.tick_params(axis="both", which="both", direction="out", color="black")


def format_probability_axis(ax, xmax: float = 0.30) -> None:
    ax.set_xlim(-0.005, xmax + 0.005)
    ax.xaxis.set_major_locator(ticker.MultipleLocator(0.05))
    ax.xaxis.set_major_formatter(ticker.FormatStrFormatter("%.2f"))
    ax.xaxis.set_minor_locator(ticker.MultipleLocator(0.025))


def set_percent_ticks(ax, major_step: int = 5) -> None:
    ax.yaxis.set_major_locator(ticker.MultipleLocator(major_step))
    ax.yaxis.set_major_formatter(ticker.FormatStrFormatter("%d"))


def mode_entries(data: List[Dict], sweep_type: str) -> Dict[str, List[Dict]]:
    return {
        mode: sorted(
            [entry for entry in data if entry["mode"] == mode and entry["sweep_type"] == sweep_type],
            key=lambda e: e["sweep_value"],
        )
        for mode in ORDER
    }


def draw_metric_series(ax, entries_by_mode: Dict[str, List[Dict]], value_key: str, *, log_floor: Optional[float] = None) -> None:
    for mode in ORDER:
        entries = entries_by_mode.get(mode, [])
        if not entries:
            continue
        style = STYLE_MAP[mode]
        xs = [entry["sweep_value"] for entry in entries]
        if log_floor is None:
            ys = percent_series(entries, value_key)
        else:
            ys = [max(entry[value_key] * 100, log_floor) for entry in entries]
        ax.plot(
            xs,
            ys,
            color=style["color"],
            linestyle=style["linestyle"],
            linewidth=style["linewidth"],
            marker=style["marker"],
            label=style["label"],
            **MARKER_KWARGS,
        )


def finish_metric_axis(ax, xlabel: str, ylabel: str, legend_loc: str, *, ymax: Optional[float] = None) -> None:
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    format_probability_axis(ax)
    if ymax is not None:
        ax.set_ylim(top=ymax)
    ax.legend(loc=legend_loc, ncol=1, handlelength=2.8, borderaxespad=0.4)
    apply_axes_style(ax)


def plot_baseline(data: List[Dict], width: float, save_kwargs: dict) -> None:
    data.sort(key=lambda e: ORDER.index(e["mode"]))
    modes = [entry["mode"] for entry in data]
    attack = percent_series(data, "avg_attack_rate")
    attack_std = standard_error_series(data, "std_attack_rate")
    
    # Use colors from STYLE_MAP
    colors = [STYLE_MAP.get(mode, {}).get("color", "#666666") for mode in modes]

    fig, ax = plt.subplots(figsize=(width, width * 0.5), layout="constrained")
    bars = ax.barh(modes, attack, xerr=attack_std, capsize=4, color=colors, edgecolor="#222", alpha=0.8, height=0.6)
    ax.set_xlabel("Replay success rate [%]")
    ax.set_xlim(left=0, right=max(attack) + 5)
    ax.set_title("Ideal channel baseline (p_loss = 0)")
    
    # Update y-tick labels to use pretty names
    ax.set_yticks(range(len(modes)))
    ax.set_yticklabels([STYLE_MAP.get(m, {}).get("label", m) for m in modes])
    
    apply_axes_style(ax)

    for bar, value in zip(bars, attack):
        ax.text(value + 0.5, bar.get_y() + bar.get_height() / 2, f"{value:.1f}%", va="center", ha="left", fontweight="bold")

    save_figure(fig, stem="baseline_attack", **save_kwargs)


def plot_ploss_curves(data: List[Dict], width: float, save_kwargs: dict, layout: str = "combined") -> None:
    subset_by_mode = mode_entries(data, "p_loss")
    if not any(subset_by_mode.values()):
        return

    # Legitimate acceptance
    fig, ax = plt.subplots(figsize=(width, width * 0.62), layout="constrained")
    draw_metric_series(ax, subset_by_mode, "avg_legit_rate")
    ax.set_ylim(65, 102)
    set_percent_ticks(ax, 5)
    finish_metric_axis(
        ax,
        r"Packet loss probability, $p_{\mathrm{loss}}$",
        "Legitimate Acceptance Rate (LAR) [%]",
        "lower left",
    )
    save_figure(fig, stem="p_loss_legit", **save_kwargs)

    # Replay success (log axis)
    fig, ax = plt.subplots(figsize=(width, width * 0.62), layout="constrained")
    draw_metric_series(ax, subset_by_mode, "avg_attack_rate", log_floor=1e-3)
    ax.set_yscale("log")
    ax.set_ylim(1e-3, 150)
    ax.yaxis.set_major_locator(ticker.LogLocator(base=10, numticks=7))
    finish_metric_axis(
        ax,
        r"Packet loss probability, $p_{\mathrm{loss}}$",
        "Attack Success Rate (ASR) [%]",
        "lower left",
    )
    save_figure(fig, stem="p_loss_attack", **save_kwargs)


def plot_preorder_curves(data: List[Dict], width: float, save_kwargs: dict) -> None:
    subset_by_mode = mode_entries(data, "p_reorder")
    if not any(subset_by_mode.values()):
        return

    # Legitimate acceptance
    fig, ax = plt.subplots(figsize=(width, width * 0.62), layout="constrained")
    draw_metric_series(ax, subset_by_mode, "avg_legit_rate")
    ax.set_ylim(60, 95)
    set_percent_ticks(ax, 5)
    finish_metric_axis(
        ax,
        r"Packet reordering probability, $p_{\mathrm{reorder}}$",
        "Legitimate Acceptance Rate (LAR) [%]",
        "lower left",
    )
    save_figure(fig, stem="p_reorder_legit", **save_kwargs)

    # Replay success (log axis)
    fig, ax = plt.subplots(figsize=(width, width * 0.62), layout="constrained")
    draw_metric_series(ax, subset_by_mode, "avg_attack_rate", log_floor=1e-3)
    ax.set_yscale("log")
    ax.set_ylim(1e-3, 150)
    ax.yaxis.set_major_locator(ticker.LogLocator(base=10, numticks=7))
    finish_metric_axis(
        ax,
        r"Packet reordering probability, $p_{\mathrm{reorder}}$",
        "Attack Success Rate (ASR) [%]",
        "lower left",
    )
    save_figure(fig, stem="p_reorder_attack", **save_kwargs)


def plot_window_tradeoff(data: List[Dict], width: float, save_kwargs: dict) -> None:
    subset = [
        entry for entry in data if entry["mode"] == "window" and entry.get("sweep_type") == "window"
    ]
    subset.sort(key=lambda e: e["sweep_value"])
    if not subset:
        return
    
    # Categorical x-axis for window sizes is fine here as they are discrete integers
    x_values = [entry["sweep_value"] for entry in subset]
    x_labels = [str(val) for val in x_values]
    xs = range(len(x_values))
    
    legit = percent_series(subset, "avg_legit_rate")
    legit_std = standard_error_series(subset, "std_legit_rate")
    attack = percent_series(subset, "avg_attack_rate")
    attack_std = standard_error_series(subset, "std_attack_rate")

    # Adjusted figsize to reduce bottom whitespace
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(width, width * 0.42), sharex=True, layout="constrained")

    ax1.bar(xs, legit, yerr=legit_std, capsize=4, color=STYLE_MAP["window"]["color"], edgecolor="#222", alpha=0.8, width=0.6)
    ax1.set_ylabel("Legitimate acceptance [%]")
    ax1.set_xlabel("Window size W")
    ax1.set_xticks(xs)
    ax1.set_xticklabels(x_labels)
    # Adjusted y-axis to show all data including W=1 (27.6%)
    ax1.set_ylim(0, 105)
    ax1.set_title("Usability (LAR)")
    
    # Only show labels for bars above 50% to avoid clutter
    for x, y in zip(xs, legit):
        if y > 50:
            ax1.text(x, y + 1, f"{y:.1f}%", ha="center", va="bottom", fontsize=9, fontweight="bold")
        else:
            # For low values, show label inside the bar or just above
            ax1.text(x, y + 2, f"{y:.1f}%", ha="center", va="bottom", fontsize=9, fontweight="bold", color="red")
        
    apply_axes_style(ax1)

    ax2.bar(xs, attack, yerr=attack_std, capsize=4, color="#9467bd", edgecolor="#222", alpha=0.8, width=0.6)
    ax2.set_ylabel("Replay success [%]")
    ax2.set_xlabel("Window size W")
    ax2.set_xticks(xs)
    ax2.set_xticklabels(x_labels)
    ax2.set_ylim(0, max(attack) * 1.3)  # Adjusted to provide proper headroom
    ax2.set_title("Security (ASR)")
    
    for x, y in zip(xs, attack):
        ax2.text(x, y + max(attack) * 0.05, f"{y:.2f}%", ha="center", va="bottom", fontsize=9, fontweight="bold")
        
    apply_axes_style(ax2)

    fig.suptitle("Window size vs usability and security (p_loss=0.15, p_reorder=0.15, inline)", fontsize=11)
    save_figure(fig, stem="window_tradeoff", **save_kwargs)


def plot_dual_sweep(
    data: List[Dict],
    width: float,
    save_kwargs: dict,
    *,
    sweep_type: str,
    xlabel: str,
    stem: str,
    lar_ylim: tuple[float, float],
) -> None:
    """Plot LAR and ASR together without heavy labels or boxed callouts."""
    subset_by_mode = mode_entries(data, sweep_type)
    if not any(subset_by_mode.values()):
        return

    fig, ax1 = plt.subplots(figsize=(width, width * 0.62), layout="constrained")
    ax2 = ax1.twinx()

    for mode in ORDER:
        entries = subset_by_mode.get(mode, [])
        if not entries:
            continue
        style = STYLE_MAP[mode]
        xs = [entry["sweep_value"] for entry in entries]
        lar = percent_series(entries, "avg_legit_rate")
        asr = [max(entry["avg_attack_rate"] * 100, 1e-3) for entry in entries]

        ax1.plot(
            xs,
            lar,
            color=style["color"],
            linestyle=style["linestyle"],
            linewidth=style["linewidth"],
            marker=style["marker"],
            **MARKER_KWARGS,
        )
        ax2.plot(
            xs,
            asr,
            color="#666666",
            linestyle=style["linestyle"],
            linewidth=max(style["linewidth"] - 0.15, 0.8),
            marker=style["marker"],
            alpha=0.85,
            **MARKER_KWARGS,
        )

    ax1.set_xlabel(xlabel)
    ax1.set_ylabel("Legitimate Acceptance Rate (LAR) [%]")
    ax1.set_ylim(*lar_ylim)
    set_percent_ticks(ax1, 5)
    format_probability_axis(ax1)

    ax2.set_ylabel("Attack Success Rate (ASR) [%]")
    ax2.set_yscale("log")
    ax2.set_ylim(1e-3, 150)
    ax2.yaxis.set_major_locator(ticker.LogLocator(base=10, numticks=7))

    mode_handles = [
        Line2D(
            [0],
            [0],
            color="black",
            linestyle=STYLE_MAP[mode]["linestyle"],
            linewidth=STYLE_MAP[mode]["linewidth"],
            marker=STYLE_MAP[mode]["marker"],
            markerfacecolor="white",
            markeredgewidth=0.8,
            markersize=4.2,
            label=STYLE_MAP[mode]["label"],
        )
        for mode in ORDER
        if subset_by_mode.get(mode)
    ]
    metric_handles = [
        Line2D([0], [0], color="black", linestyle="-", linewidth=1.2, label="LAR"),
        Line2D([0], [0], color="#666666", linestyle="-", linewidth=1.2, label="ASR"),
    ]
    legend = ax1.legend(
        handles=mode_handles + metric_handles,
        loc="lower left",
        ncol=2,
        handlelength=2.5,
        columnspacing=1.2,
        borderaxespad=0.4,
    )
    ax1.add_artist(legend)

    apply_axes_style(ax1, right=False)
    apply_axes_style(ax2, right=True)
    ax2.spines["left"].set_visible(False)
    save_figure(fig, stem=stem, **save_kwargs)


def plot_ploss_dual(data: List[Dict], width: float, save_kwargs: dict) -> None:
    plot_dual_sweep(
        data,
        width,
        save_kwargs,
        sweep_type="p_loss",
        xlabel=r"Packet loss probability, $p_{\mathrm{loss}}$",
        stem="p_loss_dual",
        lar_ylim=(65, 102),
    )


def plot_preorder_dual(data: List[Dict], width: float, save_kwargs: dict) -> None:
    plot_dual_sweep(
        data,
        width,
        save_kwargs,
        sweep_type="p_reorder",
        xlabel=r"Packet reordering probability, $p_{\mathrm{reorder}}$",
        stem="p_reorder_dual",
        lar_ylim=(60, 95),
    )


def main() -> None:
    args = parse_args()
    configure_style(args.theme, args.use_tex)

    fig_dir = Path(args.fig_dir)
    fig_dir.mkdir(parents=True, exist_ok=True)

    data_paths = {
        "baseline": Path(args.baseline_json),
        "p_loss": Path(args.ploss_json),
        "p_reorder": Path(args.preorder_json),
        "window": Path(args.window_json),
    }

    save_kwargs = {"fig_dir": fig_dir, "formats": args.formats, "dpi": args.dpi}
    width = args.column_width * args.scale

    if data_paths["baseline"].exists():
        plot_baseline(load_json(data_paths["baseline"]), width, save_kwargs)
    
    if data_paths["p_loss"].exists():
        plot_ploss_curves(load_json(data_paths["p_loss"]), width, save_kwargs, layout=args.ploss_layout)
        plot_ploss_dual(load_json(data_paths["p_loss"]), width, save_kwargs)
    
    if data_paths["p_reorder"].exists():
        plot_preorder_curves(load_json(data_paths["p_reorder"]), width, save_kwargs)
        plot_preorder_dual(load_json(data_paths["p_reorder"]), width, save_kwargs)

    if data_paths["window"].exists():
        plot_window_tradeoff(load_json(data_paths["window"]), width * 1.2, save_kwargs)

    emitted = ", ".join({fmt.lower() for fmt in args.formats})
    print(f"Saved figures to {fig_dir.resolve()} ({emitted})")


if __name__ == "__main__":
    main()
