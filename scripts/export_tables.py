"""Export simulation JSON summaries as Markdown tables."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

RESULTS_DIR = Path("results")
OUTPUT = Path("docs/metrics_tables.md")
ORDER = ["no_def", "rolling", "window", "challenge"]
MODE_LABELS = {
    "no_def": "no_def",
    "rolling": "rolling",
    "window": "window",
    "challenge": "challenge",
}


def load(path: Path) -> List[Dict]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def make_preorder_table() -> str:
    """Generate p_reorder sweep table (Rolling vs Window only)."""
    try:
        data = load(RESULTS_DIR / "p_reorder_sweep.json")
    except FileNotFoundError:
        return ""
    
    header = "| p_reorder | Rolling (%) | Window (W=5) (%) |\n| --- | --- | --- |"
    rows: List[str] = []
    
    for p in sorted({entry["sweep_value"] for entry in data if entry["sweep_type"] == "p_reorder"}):
        rolling_entry = next((e for e in data if e["sweep_value"] == p and e["mode"] == "rolling"), None)
        window_entry = next((e for e in data if e["sweep_value"] == p and e["mode"] == "window"), None)
        
        if rolling_entry and window_entry:
            rows.append(
                f"| {p:.1f} | {pct(rolling_entry['avg_legit_rate'])} | {pct(window_entry['avg_legit_rate'])} |"
            )
    
    if not rows:
        return ""
    
    return "## Packet-reorder sweep - legitimate acceptance (p_loss=0)\n\n" + "\n".join([header, *rows]) + "\n\n**Source**: `results/p_reorder_sweep.json`\n"


def make_ploss_tables() -> str:
    """Generate p_loss sweep tables."""
    try:
        data = load(RESULTS_DIR / "p_loss_sweep.json")
    except FileNotFoundError:
        return ""
    
    # Simplified to Rolling vs Window only
    header = "| p_loss | Rolling (%) | Window (W=5) (%) |\n| --- | --- | --- |"
    rows: List[str] = []
    
    for p in sorted({entry["sweep_value"] for entry in data if entry["sweep_type"] == "p_loss"}):
        rolling_entry = next((e for e in data if e["sweep_value"] == p and e["mode"] == "rolling"), None)
        window_entry = next((e for e in data if e["sweep_value"] == p and e["mode"] == "window"), None)
        
        if rolling_entry and window_entry:
            rows.append(
                f"| {p:.2f} | {pct(rolling_entry['avg_legit_rate'])} | {pct(window_entry['avg_legit_rate'])} |"
            )
    
    if not rows:
        return ""
    
    return "## Packet-loss sweep - legitimate acceptance (p_reorder=0)\n\n" + "\n".join([header, *rows]) + "\n\n**Source**: `results/p_loss_sweep.json`\n"


def make_window_table() -> str:
    """Generate window size sweep table."""
    try:
        data = load(RESULTS_DIR / "window_sweep.json")
    except FileNotFoundError:
        return ""
    
    rows: List[str] = []
    header = "| Window W | Legitimate (%) | Replay success (%) |\n| --- | --- | --- |"
    
    subset = [e for e in data if e["mode"] == "window" and e["sweep_type"] == "window"]
    subset.sort(key=lambda e: e["sweep_value"])
    
    for entry in subset:
        rows.append(
            "| {0:d} | {1:.2f}% | {2:.2f}% |".format(
                int(entry["sweep_value"]), 
                entry["avg_legit_rate"] * 100, 
                entry["avg_attack_rate"] * 100
            )
        )
    
    if not rows:
        return ""
    
    return "## Window sweep (Stress test: p_loss=0.05, p_reorder=0.3)\n\n" + "\n".join([header, *rows]) + "\n\n**Source**: `results/window_sweep.json`\n"


def make_baseline_tables() -> str:
    """Generate baseline and trace-driven tables."""
    output = []
    
    # Ideal channel baseline
    try:
        data = load(RESULTS_DIR / "ideal_p0.json")
        header = "| Mode | Legitimate (%) | Replay success (%) |\n| --- | --- | --- |"
        rows = []
        for mode in ORDER:
            entry = next((e for e in data if e["mode"] == mode), None)
            if entry:
                rows.append(
                    f"| {mode} | {pct(entry['avg_legit_rate'])} | {pct(entry['avg_attack_rate'])} |"
                )
        if rows:
            output.append("## Ideal channel baseline (post attack, runs = 500, p_loss = 0)\n\n" + "\n".join([header, *rows]) + "\n\n**Source**: `results/ideal_p0.json`")
    except FileNotFoundError:
        pass
    
    # Trace-driven
    try:
        data = load(RESULTS_DIR / "trace_inline.json")
        header = "| Mode | Legitimate (%) | Replay success (%) |\n| --- | --- | --- |"
        rows = []
        for mode in ORDER:
            entry = next((e for e in data if e["mode"] == mode), None)
            if entry:
                rows.append(
                    f"| {mode} | {pct(entry['avg_legit_rate'])} | {pct(entry['avg_attack_rate'])} |"
                )
        if rows:
            output.append("## Trace-driven inline scenario (real command trace, runs = 300, p_loss = 0)\n\n" + "\n".join([header, *rows]) + "\n\n**Source**: `results/trace_inline.json`")
    except FileNotFoundError:
        pass
    
    return "\n".join(output)


def main() -> None:
    sections = [
        "# Aggregated metrics tables",
        "\nThis document contains the experimental results referenced in the main README.\n",
        make_preorder_table(),
        make_ploss_tables(),
        make_window_table(),
        make_baseline_tables(),
    ]
    
    # Filter out empty sections
    content = "\n".join(s for s in sections if s.strip())
    
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(content, encoding="utf-8")
    print(f"Wrote markdown tables to {OUTPUT}")


if __name__ == "__main__":
    main()
