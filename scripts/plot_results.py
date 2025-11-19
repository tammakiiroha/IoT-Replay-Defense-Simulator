"""Generate publication-ready plots (PNG/PDF/PGF) from simulation outputs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Iterable, List, Sequence
import math

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

ORDER = ["no_def", "rolling", "window", "challenge"]

# Enhanced styling to distinguish overlapping lines
STYLE_MAP = {
    "no_def":    {"color": "#d62728", "marker": "X", "linestyle": ":",  "label": "No Defense"},
    "rolling":   {"color": "#1f77b4", "marker": "o", "linestyle": "--", "label": "Rolling MAC"},
    "window":    {"color": "#ff7f0e", "marker": "s", "linestyle": "-",  "label": "Window"},
    "challenge": {"color": "#2ca02c", "marker": "^", "linestyle": "-.", "label": "Challenge-Resp"},
}

# Offsets to prevent overlap (jitter)
# Scale these based on the x-axis range in the plotting functions
OFFSET_MAP = {
    "no_def":    -1.5,
    "rolling":   -0.5,
    "window":     0.5,
    "challenge":  1.5,
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
        default=6.0,
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
    plt.style.use("seaborn-v0_8-whitegrid")
    base_font = "serif" if theme == "paper" else "DejaVu Sans"
    plt.rcParams.update(
        {
            "font.family": base_font,
            "figure.dpi": 300,
            "axes.titlesize": 12,
            "axes.labelsize": 11,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            "legend.fontsize": 10,
            "axes.titleweight": "bold",
            "axes.edgecolor": "#333333",
            "axes.linewidth": 1.0,
            "grid.alpha": 0.4,
            "grid.linestyle": "--",
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.05,
            "pgf.texsystem": "pdflatex",
            "pgf.rcfonts": False,
            "pgf.preamble": r"\usepackage{siunitx}\usepackage{sfmath}",
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


def save_figure(fig, fig_dir: Path, stem: str, formats: Sequence[str], dpi: int) -> None:
    for ext in {fmt.lower() for fmt in formats}:
        target = fig_dir / f"{stem}.{ext}"
        fig.savefig(target, dpi=dpi if ext in {"png", "jpg"} else None)
    plt.close(fig)


def apply_axes_style(ax) -> None:
    ax.grid(alpha=0.4, linestyle="--", linewidth=0.8)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)


def plot_baseline(data: List[Dict], width: float, save_kwargs: dict) -> None:
    data.sort(key=lambda e: ORDER.index(e["mode"]))
    modes = [entry["mode"] for entry in data]
    attack = percent_series(data, "avg_attack_rate")
    attack_std = percent_series(data, "std_attack_rate")
    
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
    subset_by_mode = {
        mode: sorted(
            [entry for entry in data if entry["mode"] == mode and entry["sweep_type"] == "p_loss"],
            key=lambda e: e["sweep_value"],
        )
        for mode in ORDER
    }
    
    active_modes = [mode for mode in ORDER if subset_by_mode.get(mode)]
    if not active_modes:
        return

    # Calculate jitter scale based on x-range
    all_x = [entry["sweep_value"] for entries in subset_by_mode.values() for entry in entries]
    if not all_x:
        return
    x_range = max(all_x) - min(all_x)
    # Jitter amount: 1.5% of total range per unit of offset
    jitter_unit = x_range * 0.015

    # Legitimate acceptance
    fig, ax = plt.subplots(figsize=(width, width * 0.7), layout="constrained")
    for mode, entries in subset_by_mode.items():
        if not entries:
            continue
        
        # Apply jitter
        raw_xs = [entry["sweep_value"] for entry in entries]
        offset = OFFSET_MAP.get(mode, 0) * jitter_unit
        xs = [x + offset for x in raw_xs]
        
        ys = percent_series(entries, "avg_legit_rate")
        yerr = percent_series(entries, "std_legit_rate")
        
        style = STYLE_MAP.get(mode, {})
        
        ax.errorbar(
            xs, ys, yerr=yerr, 
            marker=style.get("marker", "o"), 
            linestyle=style.get("linestyle", "-"),
            color=style.get("color", "#777"),
            label=style.get("label", mode),
            linewidth=2.0, markersize=6, capsize=3, alpha=0.9
        )
        
    ax.set_xlabel("Packet loss probability")
    ax.set_ylabel("Legitimate acceptance [%]")
    ax.set_ylim(75, 102)
    ax.set_title("Packet loss vs legitimate acceptance")
    ax.legend(ncol=2, loc="lower left", frameon=True, framealpha=0.9)
    apply_axes_style(ax)
    save_figure(fig, stem="p_loss_legit", **save_kwargs)

    # Replay success (log axis)
    fig, ax = plt.subplots(figsize=(width, width * 0.7), layout="constrained")
    for mode, entries in subset_by_mode.items():
        if not entries:
            continue
            
        raw_xs = [entry["sweep_value"] for entry in entries]
        offset = OFFSET_MAP.get(mode, 0) * jitter_unit
        xs = [x + offset for x in raw_xs]
        
        ys = [max(entry["avg_attack_rate"] * 100, 1e-3) for entry in entries]
        yerr = percent_series(entries, "std_attack_rate")
        
        style = STYLE_MAP.get(mode, {})
        
        ax.errorbar(
            xs, ys, yerr=yerr,
            marker=style.get("marker", "o"), 
            linestyle=style.get("linestyle", "-"),
            color=style.get("color", "#777"),
            label=style.get("label", mode),
            linewidth=2.0, markersize=6, capsize=3, alpha=0.9
        )
        
    ax.set_xlabel("Packet loss probability")
    ax.set_ylabel("Replay success [%] (log)")
    ax.set_yscale("log")
    ax.set_ylim(1e-3, 150)
    ax.set_title("Packet loss vs replay success")
    ax.legend(ncol=2, loc="lower right", frameon=True, framealpha=0.9)
    apply_axes_style(ax)
    save_figure(fig, stem="p_loss_attack", **save_kwargs)


def plot_preorder_curves(data: List[Dict], width: float, save_kwargs: dict) -> None:
    subset_by_mode = {
        mode: sorted(
            [entry for entry in data if entry["mode"] == mode and entry["sweep_type"] == "p_reorder"],
            key=lambda e: e["sweep_value"],
        )
        for mode in ORDER
    }
    
    active_modes = [mode for mode in ORDER if subset_by_mode.get(mode)]
    if not active_modes:
        return

    all_x = [entry["sweep_value"] for entries in subset_by_mode.values() for entry in entries]
    if not all_x:
        return
    x_range = max(all_x) - min(all_x)
    jitter_unit = x_range * 0.015

    # Legitimate acceptance only
    fig, ax = plt.subplots(figsize=(width, width * 0.7), layout="constrained")
    for mode, entries in subset_by_mode.items():
        if not entries:
            continue
            
        raw_xs = [entry["sweep_value"] for entry in entries]
        offset = OFFSET_MAP.get(mode, 0) * jitter_unit
        xs = [x + offset for x in raw_xs]
        
        ys = percent_series(entries, "avg_legit_rate")
        yerr = percent_series(entries, "std_legit_rate")
        
        style = STYLE_MAP.get(mode, {})
        
        ax.errorbar(
            xs, ys, yerr=yerr, 
            marker=style.get("marker", "o"), 
            linestyle=style.get("linestyle", "-"),
            color=style.get("color", "#777"),
            label=style.get("label", mode),
            linewidth=2.0, markersize=6, capsize=3, alpha=0.9
        )
        
    ax.set_xlabel("Packet reordering probability")
    ax.set_ylabel("Legitimate acceptance [%]")
    ax.set_title("Packet reordering vs legitimate acceptance")
    ax.legend(ncol=2, loc="lower left", frameon=True, framealpha=0.9)
    apply_axes_style(ax)
    save_figure(fig, stem="p_reorder_legit", **save_kwargs)


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
    legit_std = percent_series(subset, "std_legit_rate")
    attack = percent_series(subset, "avg_attack_rate")
    attack_std = percent_series(subset, "std_attack_rate")

    # Adjusted figsize to reduce bottom whitespace
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(width, width * 0.42), sharex=True, layout="constrained")

    ax1.bar(xs, legit, yerr=legit_std, capsize=4, color=STYLE_MAP["window"]["color"], edgecolor="#222", alpha=0.8, width=0.6)
    ax1.set_ylabel("Legitimate acceptance [%]")
    ax1.set_xlabel("Window size W")
    ax1.set_xticks(xs)
    ax1.set_xticklabels(x_labels)
    # Adjusted y-axis to show all data including W=1 (27.6%)
    ax1.set_ylim(0, 105)
    ax1.set_title("Usability")
    
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
    ax2.set_title("Security")
    
    for x, y in zip(xs, attack):
        ax2.text(x, y + max(attack) * 0.05, f"{y:.2f}%", ha="center", va="bottom", fontsize=9, fontweight="bold")
        
    apply_axes_style(ax2)

    fig.suptitle("Window size vs usability & security (p_loss=0.05, p_reorder=0.3)", fontsize=11)
    save_figure(fig, stem="window_tradeoff", **save_kwargs)


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
    
    if data_paths["p_reorder"].exists():
        plot_preorder_curves(load_json(data_paths["p_reorder"]), width, save_kwargs)

    if data_paths["window"].exists():
        plot_window_tradeoff(load_json(data_paths["window"]), width * 1.2, save_kwargs)

    emitted = ", ".join({fmt.lower() for fmt in args.formats})
    print(f"Saved figures to {fig_dir.resolve()} ({emitted})")


if __name__ == "__main__":
    main()
