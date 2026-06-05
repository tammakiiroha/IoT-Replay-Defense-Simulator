#!/usr/bin/env python3
"""Generate security-cost frontier benchmark figure."""
from __future__ import annotations

from pathlib import Path

from replay.contracts import SimulationSpec
from replay.services.simulation import simulate_batch


def main() -> int:
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise SystemExit("Install matplotlib or run `pip install -e '.[figures]'`.") from exc

    batch = simulate_batch(
        SimulationSpec(
            modes=["rolling", "window", "challenge", "hsw_cr", "oscore_like"],
            runs=80,
            seed=17,
            p_loss=0.1,
            p_reorder=0.1,
            window_size=8,
            num_legit=20,
            num_replay=50,
            command_set=["PING", "STATUS", "LOCK", "UNLOCK"],
            command_risk={"UNLOCK": 1.0, "LOCK": 0.7},
            target_commands=["UNLOCK"],
            paired=True,
        ),
        show_progress=False,
    )

    fig, ax = plt.subplots(figsize=(7, 4.2))
    for result in batch.results:
        security = 1.0 - result.avg_attack_rate
        ax.scatter(result.energy_proxy, security, s=70)
        ax.annotate(
            result.mode,
            (result.energy_proxy, security),
            xytext=(5, 5),
            textcoords="offset points",
            fontsize=8,
        )

    ax.set_title("Security-cost frontier")
    ax.set_xlabel("Energy proxy (lower is better)")
    ax.set_ylabel("Replay resistance: 1 - ASR")
    ax.set_ylim(-0.03, 1.03)
    ax.grid(True, alpha=0.25)
    output = Path("docs/figures/security_cost_frontier.png")
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
