# Aggregated metrics tables


### Packet-loss sweep - legitimate acceptance

| p_loss | no_def | rolling | window | challenge |
| --- | --- | --- | --- | --- |
| 0.00 | 100.00% | 100.00% | 100.00% | 100.00% |
| 0.01 | 99.05% | 99.05% | 99.05% | 98.98% |
| 0.05 | 94.92% | 94.92% | 94.92% | 94.62% |
| 0.10 | 89.70% | 89.70% | 89.70% | 89.57% |
| 0.20 | 79.60% | 79.60% | 79.58% | 79.70% |

### Packet-loss sweep - replay success

| p_loss | no_def | rolling | window | challenge |
| --- | --- | --- | --- | --- |
| 0.00 | 100.00% | 0.00% | 0.00% | 0.00% |
| 0.01 | 98.54% | 0.00% | 0.00% | 0.00% |
| 0.05 | 94.61% | 0.03% | 0.03% | 0.00% |
| 0.10 | 89.73% | 0.10% | 0.10% | 0.00% |
| 0.20 | 80.15% | 0.47% | 0.50% | 0.00% |


### Window sweep (p_loss = 0.05, post attack)

| Window W | Legitimate (%) | Replay success (%) |
| --- | --- | --- |
| 1 | 62.32% | 2.8467% |
| 3 | 94.88% | 0.0533% |
| 5 | 95.07% | 0.0567% |
| 7 | 95.02% | 0.0333% |
| 9 | 94.67% | 0.0467% |

### Ideal channel baseline (post attack, runs = 500, p_loss = 0)

| Mode | Legitimate (%) | Replay success (%) | Source |
| --- | --- | --- | --- |
| no_def | 100.00% | 100.00% | `results/ideal_p0.json` |
| rolling | 100.00% | 0.00% | `results/ideal_p0.json` |
| window (W=5) | 100.00% | 0.00% | `results/ideal_p0.json` |
| challenge | 100.00% | 0.00% | `results/ideal_p0.json` |

### Trace-driven inline scenario (real command trace, runs = 300, p_loss = 0)

| Mode | Legitimate (%) | Replay success (%) | Source |
| --- | --- | --- | --- |
| no_def | 100.00% | 100.00% | `results/trace_inline.json` |
| rolling | 100.00% | 0.00% | `results/trace_inline.json` |
| window (W=5) | 100.00% | 0.00% | `results/trace_inline.json` |
| challenge | 100.00% | 0.00% | `results/trace_inline.json` |
