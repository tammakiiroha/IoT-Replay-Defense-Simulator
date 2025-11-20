# Aggregated metrics tables

This document contains the experimental results referenced in the main README.

## Packet-reorder sweep - legitimate acceptance (p_loss=0)

| p_reorder | Rolling (%) | Window (W=5) (%) |
| --- | --- | --- |
| 0.0 | 100.00% | 100.00% |
| 0.1 | 94.23% | 99.98% |
| 0.3 | 84.32% | 99.90% |
| 0.5 | 78.38% | 99.88% |
| 0.7 | 78.78% | 99.97% |

**Source**: `results/p_reorder_sweep.json`

## Packet-loss sweep - legitimate acceptance (p_reorder=0)

| p_loss | Rolling (%) | Window (W=5) (%) |
| --- | --- | --- |
| 0.00 | 100.00% | 100.00% |
| 0.01 | 98.93% | 98.93% |
| 0.05 | 94.93% | 94.93% |
| 0.10 | 90.23% | 90.23% |
| 0.20 | 80.27% | 80.08% |

**Source**: `results/p_loss_sweep.json`

## Window sweep (Stress test: p_loss=0.05, p_reorder=0.3)

| Window W | Legitimate (%) | Replay success (%) |
| --- | --- | --- |
| 1 | 24.97% | 4.86% |
| 3 | 94.35% | 0.23% |
| 5 | 94.72% | 0.29% |
| 10 | 94.72% | 0.56% |

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