# Aggregated metrics tables

This document contains the experimental results referenced in the main README.

## Packet-reorder sweep - legitimate acceptance (p_loss=0)

| p_reorder | Rolling (%) | Window (W=5) (%) |
| --- | --- | --- |
| 0.0 | 89.20% | 89.20% |
| 0.05 | 87.10% | 89.65% |
| 0.1 | 84.92% | 89.47% |
| 0.15 | 82.47% | 89.45% |
| 0.2 | 80.47% | 89.22% |
| 0.25 | 78.67% | 89.20% |
| 0.3 | 77.15% | 89.50% |

**Source**: `results/p_reorder_sweep.json`

## Packet-loss sweep - legitimate acceptance (p_reorder=0)

| p_loss | Rolling (%) | Window (W=5) (%) |
| --- | --- | --- |
| 0.00 | 100.00% | 100.00% |
| 0.05 | 94.47% | 94.47% |
| 0.10 | 89.20% | 89.20% |
| 0.15 | 84.22% | 84.22% |
| 0.20 | 80.65% | 80.65% |
| 0.25 | 75.80% | 75.80% |
| 0.30 | 71.35% | 71.35% |

**Source**: `results/p_loss_sweep.json`

## Window sweep (Stress test: p_loss=0.15, p_reorder=0.15, inline attack)

| Window W | Legitimate (%) | Replay success (%) |
| --- | --- | --- |
| 1 | 80.03% | 4.49% |
| 3 | 85.17% | 7.91% |
| 5 | 85.17% | 9.91% |
| 7 | 85.17% | 11.47% |
| 9 | 85.17% | 12.21% |
| 15 | 85.17% | 13.92% |
| 20 | 85.17% | 14.07% |

**Source**: `results/window_sweep.json`

## Ideal channel baseline (post attack, runs = 500, p_loss = 0)

| Mode | Legitimate (%) | Replay success (%) |
| --- | --- | --- |
| no_def | 100.00% | 100.00% |
| rolling | 100.00% | 0.00% |
| window | 100.00% | 0.00% |
| challenge | 100.00% | 0.00% |

**Source**: `results/ideal_p0.json`
## Trace-driven inline scenario (real command trace, runs = 300, p_loss = 0)

| Mode | Legitimate (%) | Replay success (%) |
| --- | --- | --- |
| no_def | 100.00% | 100.00% |
| rolling | 100.00% | 0.00% |
| window | 100.00% | 0.00% |
| challenge | 100.00% | 0.00% |

**Source**: `results/trace_inline.json`