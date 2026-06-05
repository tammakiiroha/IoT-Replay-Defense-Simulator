#!/usr/bin/env python3
"""
Simulation vs Hardware Comparison Tool

Compares results from Monte Carlo simulation with physical hardware experiments
to validate the simulation model and generate publication-ready figures.

Features:
- Load and parse both simulation and hardware results
- Statistical comparison with confidence intervals
- Generate comparison figures (PNG, PDF, PGF)
- Export comparison tables for LaTeX

Usage:
    python compare_sim_vs_hw.py
    python compare_sim_vs_hw.py --sim-file results/p_loss_sweep.json --hw-file ../results/experiment_*.json
    python compare_sim_vs_hw.py --generate-latex
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from glob import glob

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# Project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class DataPoint:
    """A single data point with statistics."""
    x_value: float          # e.g., p_loss, window_size
    mean: float
    std: float
    ci95_lower: float = 0.0
    ci95_upper: float = 0.0
    n_samples: int = 1

    def __post_init__(self):
        # Calculate 95% CI if not provided
        if self.ci95_lower == 0 and self.ci95_upper == 0:
            if self.n_samples > 1:
                # t-value approximation for 95% CI
                t_val = 1.96 if self.n_samples > 30 else 2.0
                margin = t_val * self.std / (self.n_samples ** 0.5)
                # 限制在 [0, 1] 范围内（适用于比率数据）
                self.ci95_lower = max(0.0, self.mean - margin)
                self.ci95_upper = min(1.0, self.mean + margin)
            else:
                # 单样本无方差估计，避免后续 errorbar 出现负误差
                self.ci95_lower = self.mean
                self.ci95_upper = self.mean


@dataclass
class DataSeries:
    """A series of data points for one experimental condition."""
    name: str               # e.g., "window_w5"
    mode: str               # e.g., "window"
    metric: str             # e.g., "legit_rate", "attack_rate"
    source: str             # "simulation" or "hardware"
    points: List[DataPoint]

    def x_values(self) -> List[float]:
        return [p.x_value for p in self.points]

    def means(self) -> List[float]:
        return [p.mean for p in self.points]

    def stds(self) -> List[float]:
        return [p.std for p in self.points]


# =============================================================================
# Data Loaders
# =============================================================================

def load_simulation_results(path: str) -> Dict[str, Any]:
    """Load simulation results from JSON file."""
    with open(path) as f:
        return json.load(f)


def load_hardware_results(pattern: str) -> List[Dict[str, Any]]:
    """Load hardware results from JSON files matching pattern."""
    files = glob(pattern)
    results = []
    for f in sorted(files):
        with open(f) as fp:
            results.append(json.load(fp))
    return results


def _extract_sim_experiments(data: Any) -> List[Dict[str, Any]]:
    """Normalize simulation payloads to a flat list of experiment dicts."""
    if isinstance(data, list):
        return [entry for entry in data if isinstance(entry, dict)]
    if isinstance(data, dict):
        experiments = data.get("experiments")
        if isinstance(experiments, list):
            return [entry for entry in experiments if isinstance(entry, dict)]
        results = data.get("results")
        if isinstance(results, list):
            return [entry for entry in results if isinstance(entry, dict)]
    return []


def _resolve_x_value(exp: Dict[str, Any], sweep_type: str, x_key: str) -> float:
    """Pick the best available x-axis value for this sweep type."""
    if x_key in exp:
        return exp.get(x_key, 0)
    if "sweep_value" in exp:
        return exp.get("sweep_value", 0)
    return 0


def _first_present(exp: Dict[str, Any], *keys: str, default: float = 0.0) -> float:
    """Return the first present metric key, preferring canonical schema names."""
    for key in keys:
        if key in exp:
            return exp.get(key, default)
    return default


def parse_simulation_sweep(data: Any, sweep_type: str = "p_loss") -> Dict[str, DataSeries]:
    """
    Parse simulation sweep results into DataSeries.

    Args:
        data: Raw JSON data from simulation
        sweep_type: "p_loss", "p_reorder", or "window"

    Returns:
        Dictionary of DataSeries keyed by "{mode}_{metric}"
    """
    series_dict: Dict[str, DataSeries] = {}

    # Expected structure from run_sweeps.py
    # {"experiments": [{"mode": "window", "p_loss": 0.1, "legit_accept_rate": 0.9, ...}]}

    experiments = _extract_sim_experiments(data)

    # Group by mode
    modes_data: Dict[str, List[Dict]] = {}
    for exp in experiments:
        mode = exp.get("mode", "unknown")
        if mode not in modes_data:
            modes_data[mode] = []
        modes_data[mode].append(exp)

    # Create series for each mode and metric
    for mode, exps in modes_data.items():
        # Sort by sweep parameter
        if sweep_type == "p_loss":
            exps.sort(key=lambda e: e.get("p_loss", 0))
            x_key = "p_loss"
        elif sweep_type == "p_reorder":
            exps.sort(key=lambda e: e.get("p_reorder", 0))
            x_key = "p_reorder"
        else:  # window
            exps.sort(key=lambda e: e.get("window_size", 0))
            x_key = "window_size"

        # Legit rate series
        legit_points = []
        for exp in exps:
            x = _resolve_x_value(exp, sweep_type, x_key)
            mean = _first_present(
                exp,
                "avg_legit_rate",
                "avg_legit_accept_rate",
                "legit_accept_rate",
                "legit_rate",
            )
            std = _first_present(
                exp,
                "std_legit_rate",
                "std_legit_accept_rate",
                "legit_accept_rate_std",
            )
            n = exp.get("num_runs", exp.get("runs", 200))
            legit_points.append(DataPoint(x, mean, std, n_samples=n))

        series_dict[f"{mode}_legit"] = DataSeries(
            name=f"{mode}_legit",
            mode=mode,
            metric="legit_rate",
            source="simulation",
            points=legit_points
        )

        # Attack rate series
        attack_points = []
        for exp in exps:
            x = _resolve_x_value(exp, sweep_type, x_key)
            mean = _first_present(
                exp,
                "avg_attack_rate",
                "avg_attack_success_rate",
                "attack_success_rate",
                "attack_rate",
            )
            std = _first_present(
                exp,
                "std_attack_rate",
                "std_attack_success_rate",
                "attack_success_rate_std",
            )
            n = exp.get("num_runs", exp.get("runs", 200))
            attack_points.append(DataPoint(x, mean, std, n_samples=n))

        series_dict[f"{mode}_attack"] = DataSeries(
            name=f"{mode}_attack",
            mode=mode,
            metric="attack_rate",
            source="simulation",
            points=attack_points
        )

    return series_dict


def parse_hardware_results(data_list: List[Dict]) -> Dict[str, DataSeries]:
    """
    Parse hardware experiment results into DataSeries.

    Hardware results are typically per-configuration, not sweeps.
    We aggregate multiple experiment files if available.
    """
    series_dict: Dict[str, DataSeries] = {}

    # Aggregate results by config
    aggregated: Dict[str, List[Dict]] = {}

    for data in data_list:
        for result in data.get("results", []):
            key = result.get("config_name", f"{result.get('mode')}_w{result.get('window_size', 0)}")
            if key not in aggregated:
                aggregated[key] = []
            aggregated[key].append(result)

    # Create data points
    for config_name, results in aggregated.items():
        mode = results[0].get("mode", "unknown")

        # Calculate aggregate statistics
        legit_rates = [
            _first_present(r, "avg_legit_rate", "avg_legit_accept_rate", "legit_accept_rate")
            for r in results
        ]
        attack_rates = [
            _first_present(r, "avg_attack_rate", "avg_attack_success_rate", "attack_success_rate")
            for r in results
        ]

        legit_mean = statistics.mean(legit_rates) if legit_rates else 0
        legit_std = statistics.pstdev(legit_rates) if len(legit_rates) > 1 else 0
        attack_mean = statistics.mean(attack_rates) if attack_rates else 0
        attack_std = statistics.pstdev(attack_rates) if len(attack_rates) > 1 else 0

        window_size = results[0].get("window_size", 0)

        # For hardware, x_value could be window_size or just an index
        legit_point = DataPoint(window_size, legit_mean, legit_std, n_samples=len(results))
        attack_point = DataPoint(window_size, attack_mean, attack_std, n_samples=len(results))

        series_dict[f"{config_name}_legit"] = DataSeries(
            name=f"{config_name}_legit",
            mode=mode,
            metric="legit_rate",
            source="hardware",
            points=[legit_point]
        )

        series_dict[f"{config_name}_attack"] = DataSeries(
            name=f"{config_name}_attack",
            mode=mode,
            metric="attack_rate",
            source="hardware",
            points=[attack_point]
        )

    return series_dict


# =============================================================================
# Visualization
# =============================================================================

# Color scheme
COLORS = {
    "no_def": "#e74c3c",      # Red
    "rolling": "#f39c12",     # Orange
    "window": "#3498db",      # Blue
    "challenge": "#2ecc71",   # Green
}

MODE_LABELS = {
    "no_def": "No Defense",
    "rolling": "Rolling Counter",
    "window": "Sliding Window",
    "challenge": "Challenge-Response",
}


def plot_comparison(
    sim_series: Dict[str, DataSeries],
    hw_series: Dict[str, DataSeries],
    metric: str = "legit_rate",
    x_label: str = "Packet Loss Rate",
    title: str = "Simulation vs Hardware Comparison",
    output_path: Optional[str] = None,
    x_scale: float = 1.0,
):
    """
    Create a comparison plot with simulation curves and hardware data points.
    """
    fig, ax = plt.subplots(figsize=(10, 6))

    # Plot simulation curves (dashed lines)
    for key, series in sim_series.items():
        if series.metric != metric:
            continue

        mode = series.mode
        color = COLORS.get(mode, "#888888")
        label = MODE_LABELS.get(mode, mode)

        x = [p.x_value * x_scale for p in series.points]
        y = [p.mean * 100 for p in series.points]
        yerr_low = [p.mean * 100 - p.ci95_lower * 100 for p in series.points]
        yerr_high = [p.ci95_upper * 100 - p.mean * 100 for p in series.points]

        # Plot line
        ax.plot(x, y, '--', color=color, linewidth=2, alpha=0.7,
                label=f"{label} (Sim)")

        # Add confidence band
        ax.fill_between(x,
                        [p.ci95_lower * 100 for p in series.points],
                        [p.ci95_upper * 100 for p in series.points],
                        color=color, alpha=0.1)

    # Plot hardware points (markers with error bars)
    for key, series in hw_series.items():
        if series.metric != metric:
            continue

        mode = series.mode
        color = COLORS.get(mode, "#888888")
        label = MODE_LABELS.get(mode, mode)

        for point in series.points:
            x = point.x_value * x_scale
            y = point.mean * 100
            yerr = [[max(0.0, point.mean * 100 - point.ci95_lower * 100)],
                    [max(0.0, point.ci95_upper * 100 - point.mean * 100)]]

            ax.errorbar(x, y, yerr=yerr, fmt='o', color=color,
                        markersize=10, capsize=5, capthick=2,
                        label=f"{label} (HW)" if point == series.points[0] else None)

    ax.set_xlabel(x_label, fontsize=12)
    y_label = "Legitimate Acceptance Rate (%)" if metric == "legit_rate" else "Attack Success Rate (%)"
    ax.set_ylabel(y_label, fontsize=12)
    ax.set_title(title, fontsize=14)

    ax.grid(True, alpha=0.3)
    ax.legend(loc='best', fontsize=10)

    # Set axis limits
    ax.set_xlim(left=0)
    ax.set_ylim(0, 105)

    plt.tight_layout()

    if output_path:
        # Save in multiple formats
        base_path = Path(output_path).with_suffix('')
        plt.savefig(f"{base_path}.png", dpi=150, bbox_inches='tight')
        plt.savefig(f"{base_path}.pdf", bbox_inches='tight')
        print(f"Saved: {base_path}.png, {base_path}.pdf")
    else:
        plt.show()

    plt.close()


def plot_bar_comparison(
    sim_data: Dict[str, float],
    hw_data: Dict[str, Tuple[float, float]],  # (mean, std)
    metric_name: str = "Legitimate Acceptance Rate (%)",
    title: str = "Defense Mode Comparison",
    output_path: Optional[str] = None
):
    """
    Create a grouped bar chart comparing simulation and hardware results.
    """
    modes = list(sim_data.keys())
    x = np.arange(len(modes))
    width = 0.35

    fig, ax = plt.subplots(figsize=(10, 6))

    # Simulation bars
    sim_values = [sim_data[m] * 100 for m in modes]
    bars1 = ax.bar(x - width/2, sim_values, width, label='Simulation',
                   color='#3498db', alpha=0.8)

    # Hardware bars with error bars
    hw_means = [hw_data.get(m, (0, 0))[0] * 100 for m in modes]
    hw_stds = [hw_data.get(m, (0, 0))[1] * 100 for m in modes]
    bars2 = ax.bar(x + width/2, hw_means, width, yerr=hw_stds,
                   label='Hardware', color='#e74c3c', alpha=0.8,
                   capsize=5)

    ax.set_xlabel('Defense Mode', fontsize=12)
    ax.set_ylabel(metric_name, fontsize=12)
    ax.set_title(title, fontsize=14)
    ax.set_xticks(x)
    ax.set_xticklabels([MODE_LABELS.get(m, m) for m in modes], rotation=15, ha='right')
    ax.legend()

    ax.set_ylim(0, 105)
    ax.grid(True, alpha=0.3, axis='y')

    # Add value labels on bars
    for bar, val in zip(bars1, sim_values):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                f'{val:.1f}', ha='center', va='bottom', fontsize=9)

    for bar, val in zip(bars2, hw_means):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                f'{val:.1f}', ha='center', va='bottom', fontsize=9)

    plt.tight_layout()

    if output_path:
        base_path = Path(output_path).with_suffix('')
        plt.savefig(f"{base_path}.png", dpi=150, bbox_inches='tight')
        plt.savefig(f"{base_path}.pdf", bbox_inches='tight')
        print(f"Saved: {base_path}.png, {base_path}.pdf")
    else:
        plt.show()

    plt.close()


# =============================================================================
# LaTeX Export
# =============================================================================

def generate_latex_table(
    sim_data: Dict[str, Dict[str, float]],
    hw_data: Dict[str, Dict[str, Tuple[float, float]]],
    output_path: Optional[str] = None
) -> str:
    """
    Generate a LaTeX table comparing simulation and hardware results.
    """
    latex = r"""
\begin{table}[htbp]
\centering
\caption{Simulation vs Hardware Experiment Results}
\label{tab:sim_vs_hw}
\begin{tabular}{lcccc}
\toprule
\multirow{2}{*}{Defense Mode} & \multicolumn{2}{c}{Legit Accept Rate (\%)} & \multicolumn{2}{c}{Attack Success Rate (\%)} \\
\cmidrule(lr){2-3} \cmidrule(lr){4-5}
 & Simulation & Hardware & Simulation & Hardware \\
\midrule
"""

    modes = ["no_def", "rolling", "window", "challenge"]

    for mode in modes:
        label = MODE_LABELS.get(mode, mode)

        sim_legit = sim_data.get(mode, {}).get("legit_rate", 0) * 100
        sim_attack = sim_data.get(mode, {}).get("attack_rate", 0) * 100

        hw_legit_mean, hw_legit_std = hw_data.get(mode, {}).get("legit_rate", (0, 0))
        hw_attack_mean, hw_attack_std = hw_data.get(mode, {}).get("attack_rate", (0, 0))

        hw_legit_str = f"${hw_legit_mean*100:.1f} \\pm {hw_legit_std*100:.1f}$"
        hw_attack_str = f"${hw_attack_mean*100:.1f} \\pm {hw_attack_std*100:.1f}$"

        latex += f"{label} & {sim_legit:.1f} & {hw_legit_str} & {sim_attack:.1f} & {hw_attack_str} \\\\\n"

    latex += r"""
\bottomrule
\end{tabular}
\end{table}
"""

    if output_path:
        with open(output_path, 'w') as f:
            f.write(latex)
        print(f"Saved LaTeX table: {output_path}")

    return latex


# =============================================================================
# Main Analysis
# =============================================================================

def run_comparison_analysis(
    sim_file: str,
    hw_pattern: str,
    output_dir: str,
    sweep_type: str = "p_loss"
):
    """
    Run full comparison analysis pipeline.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    print("="*60)
    print("Simulation vs Hardware Comparison Analysis")
    print("="*60)

    # Load data
    print(f"\nLoading simulation data: {sim_file}")
    if Path(sim_file).exists():
        sim_data = load_simulation_results(sim_file)
        sim_series = parse_simulation_sweep(sim_data, sweep_type)
        print(f"  Found {len(sim_series)} simulation series")
    else:
        print(f"  Warning: Simulation file not found")
        sim_series = {}

    print(f"\nLoading hardware data: {hw_pattern}")
    hw_files = glob(hw_pattern)
    if hw_files:
        hw_data = load_hardware_results(hw_pattern)
        hw_series = parse_hardware_results(hw_data)
        print(f"  Found {len(hw_files)} hardware files, {len(hw_series)} series")
    else:
        print(f"  Warning: No hardware files found")
        hw_series = {}

    if not sim_series and not hw_series:
        print("\nNo data to compare. Run experiments first.")
        return

    # Generate comparison plots
    if sim_series or hw_series:
        print("\nGenerating comparison plots...")

        x_label_map = {
            "p_loss": "Packet Loss Rate (%)",
            "p_reorder": "Packet Reorder Rate (%)",
            "window": "Window Size",
        }
        x_scale = 100.0 if sweep_type in {"p_loss", "p_reorder"} else 1.0
        x_label = x_label_map.get(sweep_type, "Parameter")

        # Legit rate comparison
        plot_comparison(
            sim_series, hw_series,
            metric="legit_rate",
            x_label=x_label,
            title="Legitimate Acceptance Rate: Simulation vs Hardware",
            output_path=str(output_path / "sim_vs_hw_legit"),
            x_scale=x_scale,
        )

        # Attack rate comparison
        plot_comparison(
            sim_series, hw_series,
            metric="attack_rate",
            x_label=x_label,
            title="Attack Success Rate: Simulation vs Hardware",
            output_path=str(output_path / "sim_vs_hw_attack"),
            x_scale=x_scale,
        )

    # Print summary statistics
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)

    print("\nSimulation Results:")
    for key, series in sorted(sim_series.items()):
        if series.points:
            avg_mean = statistics.mean([p.mean for p in series.points])
            print(f"  {key}: avg={avg_mean:.1%}")

    print("\nHardware Results:")
    for key, series in sorted(hw_series.items()):
        if series.points:
            for p in series.points:
                print(f"  {key}: mean={p.mean:.1%} ± {p.std:.1%}")

    print(f"\nOutput saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Compare simulation and hardware experiment results"
    )

    parser.add_argument("--sim-file", type=str,
                        default="results/p_loss_sweep.json",
                        help="Path to simulation results JSON")
    parser.add_argument("--hw-pattern", type=str,
                        default="physical_experiment/results/experiment_*.json",
                        help="Glob pattern for hardware result files")
    parser.add_argument("--output-dir", type=str,
                        default="figures",
                        help="Output directory for figures")
    parser.add_argument("--sweep-type", type=str,
                        choices=["p_loss", "p_reorder", "window"],
                        default="p_loss",
                        help="Type of parameter sweep")
    parser.add_argument("--generate-latex", action="store_true",
                        help="Generate LaTeX table")

    args = parser.parse_args()

    # Resolve paths relative to project root
    sim_file = PROJECT_ROOT / args.sim_file
    hw_pattern = str(PROJECT_ROOT / args.hw_pattern)
    output_dir = PROJECT_ROOT / args.output_dir

    run_comparison_analysis(
        sim_file=str(sim_file),
        hw_pattern=hw_pattern,
        output_dir=str(output_dir),
        sweep_type=args.sweep_type
    )


if __name__ == "__main__":
    main()
