# Aggregated metrics tables

This document contains the experimental results referenced in the main README.

## Packet-reorder sweep - legitimate acceptance (p_loss=0)

| p_reorder | Rolling (%) | Window (W=5) (%) |
| --- | --- | --- |
| 0.0 | 90.28% | 90.28% |
| 0.1 | 87.10% | 89.85% |
| 0.1 | 84.80% | 90.05% |
| 0.1 | 83.00% | 90.25% |
| 0.2 | 80.83% | 90.42% |
| 0.2 | 78.88% | 90.72% |
| 0.3 | 76.80% | 90.60% |

**Source**: `results/p_reorder_sweep.json`

## Packet-loss sweep - legitimate acceptance (p_reorder=0)

| p_loss | Rolling (%) | Window (W=5) (%) |
| --- | --- | --- |
| 0.00 | 100.00% | 100.00% |
| 0.05 | 95.30% | 95.30% |
| 0.10 | 90.28% | 90.28% |
| 0.15 | 85.65% | 85.65% |
| 0.20 | 80.22% | 80.22% |
| 0.25 | 75.30% | 74.92% |
| 0.30 | 70.30% | 69.53% |

**Source**: `results/p_loss_sweep.json`

## Window sweep (Stress test: p_loss=0.15, p_reorder=0.15, inline attack)

| Window W | Legitimate (%) | Replay success (%) |
| --- | --- | --- |
| 1 | 25.87% | 7.28% |
| 3 | 85.03% | 6.46% |
| 5 | 85.45% | 7.71% |
| 7 | 85.45% | 8.74% |
| 9 | 85.45% | 9.56% |
| 15 | 85.45% | 11.09% |
| 20 | 85.45% | 11.58% |

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