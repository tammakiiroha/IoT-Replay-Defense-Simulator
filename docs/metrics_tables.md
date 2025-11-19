# Aggregated metrics tables

This document contains the experimental results referenced in the main README.

## Packet-reorder sweep - legitimate acceptance (p_loss=0)

| p_reorder | Rolling (%) | Window (W=5) (%) |
| --- | --- | --- |
| 0.0 | 100.00% | 100.00% |
| 0.1 | 93.55% | 100.00% |
| 0.3 | 84.47% | 99.88% |
| 0.5 | 77.62% | 99.88% |
| 0.7 | 78.33% | 99.90% |

**Source**: `results/p_reorder_sweep.json`

## Packet-loss sweep - legitimate acceptance (p_reorder=0)

| p_loss | Rolling (%) | Window (W=5) (%) |
| --- | --- | --- |
| 0.00 | 100.00% | 100.00% |
| 0.01 | 98.97% | 98.97% |
| 0.05 | 94.88% | 94.88% |
| 0.10 | 89.90% | 89.90% |
| 0.20 | 79.53% | 79.53% |

**Source**: `results/p_loss_sweep.json`

## Window sweep (Stress test: p_loss=0.05, p_reorder=0.3)

| Window W | Legitimate (%) | Replay success (%) |
| --- | --- | --- |
| 1 | 27.65% | 4.51% |
| 3 | 95.10% | 0.22% |
| 5 | 95.08% | 0.30% |
| 10 | 95.22% | 0.48% |

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