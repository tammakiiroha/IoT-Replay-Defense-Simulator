# Replay Attack Simulation Toolkit

This toolkit reproduces the replay-attack evaluation plan described in the project brief. It models multiple receiver configurations under a record-and-replay adversary and reports both security (attack success) and usability (legitimate acceptance) metrics.

## Features
- **Protocol variants**: no defense, rolling counter + MAC, rolling counter + acceptance window, and a nonce-based challenge–response baseline.
- **Role models**: sender, lossy channel, receiver with persistent state, and an attacker that records and replays observed frames.
- **Metrics**: per-run legitimate acceptance rate and attack success rate, plus aggregated averages and standard deviations across Monte Carlo runs.
- **Command sources**: random commands from a default toy set or a trace file captured from a real controller.
- **Attacker scheduling**: choose between post-run burst replay or inline injection during legitimate traffic.
- **Outputs**: human-readable tables on stdout, JSON dumps for plotting, and automation helpers for parameter sweeps.

## Quick start
```bash
python3 main.py --runs 200 --num-legit 20 --num-replay 100 --p-loss 0.05 --window-size 5
```

The command above evaluates all three modes (no defense, rolling, window) for the specified packet-loss probability. The table columns align with the metrics defined in the thesis outline.

## CLI reference
Key options exposed by `main.py`:

| Flag | Description |
|------|-------------|
| `--modes` | Space-separated list of modes to evaluate (`no_def`, `rolling`, `window`, `challenge`). |
| `--runs` | Number of Monte Carlo repetitions per mode (default: 200). |
| `--num-legit` | Legitimate transmissions per run. |
| `--num-replay` | Replay attempts per run. |
| `--p-loss` | Packet-loss probability applied to both legitimate and injected frames. |
| `--window-size` | Acceptance-window width when mode `window` is active. |
| `--commands-file` | Path to a newline-delimited command trace captured from real hardware. |
| `--mac-length` | Truncated MAC length (hex chars), allowing sensitivity studies w.r.t. tag size. |
| `--shared-key` | Shared secret used by sender/receiver to derive MACs. |
| `--attacker-loss` | Probability that the attacker fails to record a legitimate frame. |
| `--seed` | Global RNG seed; set to fix Monte Carlo runs for reproducibility. |
| `--attack-mode` | Replay scheduling strategy: `post` or `inline`. |
| `--inline-attack-prob` | For inline mode, probability of inserting an attack after a legitimate frame. |
| `--inline-attack-burst` | Maximum inline replay attempts per legitimate frame. |
| `--challenge-nonce-bits` | Nonce length (bits) used by the challenge–response mode. |
| `--output-json` | Path to save aggregate metrics in JSON for plotting or tables. |

Example with a trace file and JSON export:
```bash
python3 main.py \
  --modes rolling window \
  --runs 500 \
  --num-legit 30 \
  --num-replay 200 \
  --p-loss 0.1 \
  --window-size 7 \
  --commands-file traces/real_log.txt \
  --output-json results/p_loss_0p1.json
```

## Trace file format
Provide one command token per line; empty lines and `#` comments are ignored. Tokens may be textual (e.g., `FWD`) or numeric opcodes that match the protocol you reverse-engineered.

```
# sample trace
FWD
FWD
LEFT
RIGHT
STOP
```

Sample file: `traces/sample_trace.txt` can be used directly with `--commands-file`.

## Parameter sweeps
Use `scripts/run_sweeps.py` to generate thesis-ready datasets for packet-loss and window-size studies:

```bash
python3 scripts/run_sweeps.py \
  --runs 300 \
  --modes rolling window challenge \
  --p-loss-values 0 0.01 0.05 0.1 0.2 \
  --window-values 1 3 5 7 9 \
  --attack-mode inline \
  --inline-attack-prob 0.4 \
  --commands-file traces/sample_trace.txt
```

The script writes two JSON files (`results/p_loss_sweep.json` and `results/window_sweep.json`) that can be imported into notebooks or plotting tools. Each record captures the sweep type, sweep value, mode, and the aggregated metrics (mean/σ of legitimate and attack success rates).
Use `--window-size-base` to decide which window size is used for the windowed receiver during the `p_loss` sweep, and `--window-values` to override per-window experiments.

## Extending experiments
- **Parameter sweeps**: automate via `scripts/run_sweeps.py` or craft custom sweeps by invoking `run_many_experiments` from notebooks.
- **Alternative attacker models**: adjust inline probabilities/bursts or extend `AttackMode` for additional strategies (e.g., targeted command flooding).
- **Challenge-response baseline**: included as `Mode.CHALLENGE`, serving as a high-security reference point to discuss implementation trade-offs.

## Project structure
```
.
├── main.py              # CLI entry point
├── sim/
│   ├── attacker.py      # Replay attacker logic
│   ├── channel.py       # Lossy channel helper
│   ├── commands.py      # Command sets and trace loader
│   ├── experiment.py    # Single and multi-run orchestration
│   ├── receiver.py      # Receiver verification routines (rolling/window/challenge)
│   ├── security.py      # MAC helper
│   ├── sender.py        # Sender frame builder
│   └── types.py         # Shared enums and dataclasses (modes, attack modes, configs)
├── scripts/
│   └── run_sweeps.py    # Automation helper for p_loss/window scans
├── traces/
│   └── sample_trace.txt # Example command sequence captured from an operator
└── README.md
```

## Using the results in the thesis
1. Document the experimental parameters (`num_legit`, `num_replay`, `p_loss`, `window_size`, MAC length).
2. Copy the table outputs or the JSON aggregates into your thesis tables/figures.
3. Highlight trade-offs: compare `window` configurations across packet-loss rates, contrast inline vs post-run attack models, and use the `challenge` mode as an upper-bound reference for security vs implementation cost.

This repository now aligns with the nine-step simulation plan. Adjust the configuration to mirror your real-world measurements, rerun the CLI, and incorporate the numbers into the report.
