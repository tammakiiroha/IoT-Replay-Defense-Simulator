# Experimental Parameters Configuration

**Version**: 1.0  
**Last Updated**: 2024  
**Related Code**: [`scripts/experiment_config.py`](scripts/experiment_config.py)  
**Technical Details**: [`PRESENTATION.zh.md` Lines 710-829](PRESENTATION.zh.md#L710-L829)

---

## Overview

This document provides a comprehensive specification of all experimental parameters used in this study. The parameter choices are designed to systematically evaluate defense mechanisms across a range of network conditions, from ideal to challenging scenarios.

---

## Core Parameters

### Fixed Parameters (All Experiments)

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `runs` | 200 | Monte Carlo iterations for 95% confidence level |
| `num_legit` | 20 | Legitimate packets per run (typical IoT communication cycle) |
| `num_replay` | 100 | Replay attack attempts per run (5:1 attack ratio) |
| `seed` | 42 | Fixed random seed for reproducibility |
| `attack_mode` | `post` | Post-run attack scheduling (Experiments 1-2) |
| `attacker_loss` | 0.0 | Ideal attacker assumption (no recording loss) |

### Variable Parameters (Experiment-Specific)

| Experiment | Variable | Range | Fixed Conditions | Output |
|------------|----------|-------|------------------|--------|
| Experiment 1 | `p_loss` | 0.0 - 0.30 (step 0.05) | `p_reorder=0.0` | Figure 1 |
| Experiment 2 | `p_reorder` | 0.0 - 0.30 (step 0.05) | `p_loss=0.10` | Figure 2 |
| Experiment 3 | `window_size` | 1, 3, 5, 7, 9, 15, 20 | `p_loss=0.15, p_reorder=0.15` | Figure 3 |

---

## Experiment 1: Packet Loss Impact

**Objective**: Evaluate defense mechanism usability under varying packet loss conditions.

**Configuration**:
```python
p_loss = [0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30]
p_reorder = 0.0
window_size = 5
attack_mode = "post"
runs = 200
seed = 42
```

**Parameter Range Design**:

| Loss Rate | Network Condition | Application Context |
|-----------|-------------------|---------------------|
| 0.0 (0%) | Ideal channel | Baseline performance evaluation |
| 0.05 (5%) | Good indoor | Short-range, minimal interference |
| 0.10 (10%) | Typical | Common IoT deployment scenario |
| 0.15 (15%) | Degraded | Moderate interference present |
| 0.20 (20%) | Poor | Industrial environment with obstacles |
| 0.25 (25%) | Severe | Heavy electromagnetic interference |
| 0.30 (30%) | Stress test | Upper bound for practical evaluation |

**Rationale for 0-30% Range**:
- Includes ideal baseline (0%) for theoretical performance comparison
- Covers typical IoT scenarios (5-15%)
- Extends to challenging conditions (15-30%) for robustness evaluation
- Beyond 30%, network becomes practically unusable (not relevant for defense evaluation)

**Expected Results**:
- No Defense: Avg Attack ≈ 100% (all loss rates)
- Rolling Counter: Avg Legit decreases significantly with loss
- Sliding Window: Avg Legit degrades more gradually
- Challenge-Response: Avg Legit slightly affected by communication overhead

**Reproduction**:
```bash
python scripts/run_sweeps.py \
  --runs 200 --seed 42 \
  --p-loss-values 0.0 0.05 0.10 0.15 0.20 0.25 0.30 \
  --p-loss-output results/p_loss_sweep.json
```

**Output Files**:
- Data: `results/p_loss_sweep.json`
- Figures: `figures/p_loss_legit.png`, `figures/p_loss_attack.png`

---

## Experiment 2: Packet Reordering Impact

**Objective**: Demonstrate sliding window's robustness to reordering and rolling counter's vulnerability.

**Configuration**:
```python
p_reorder = [0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30]
p_loss = 0.10
window_size = 5
attack_mode = "post"
runs = 200
seed = 42
```

**Why Fix p_loss = 0.10?**  
To isolate the impact of reordering, we fix packet loss at a representative 10% rate (typical IoT environment). This follows the single-variable control principle in experimental design.

**Parameter Range Design**:

| Reorder Rate | Network Topology | Characteristics |
|--------------|------------------|-----------------|
| 0.0 (0%) | Single-hop ideal | Direct communication, no buffering |
| 0.05 (5%) | Single-hop real | Minor MAC retransmission delays |
| 0.10 (10%) | 2-hop network | Buffer queue introduces some reordering |
| 0.15 (15%) | 3-hop network | Multi-hop forwarding with delay jitter |
| 0.20 (20%) | Multi-hop stressed | Significant delay variation |
| 0.25 (25%) | Complex topology | Multi-path routing, load imbalance |
| 0.30 (30%) | Stress test | Extreme reordering for robustness evaluation |

**Expected Results** (Key Finding):
- Rolling Counter: Avg Legit drops sharply (reordered packets rejected as replays)
  - 0% reordering: 100% usability
  - 30% reordering: ~40-60% usability
- Sliding Window: Avg Legit remains stable (designed to tolerate reordering)
  - 0-30% reordering: 90-100% usability maintained
- Challenge-Response: Slight degradation due to communication overhead

*This experiment reveals the fundamental limitation of strict counter-based defenses in real-world networks.*

**Reproduction**:
```bash
python scripts/run_sweeps.py \
  --runs 200 --seed 42 \
  --p-reorder-values 0.0 0.05 0.10 0.15 0.20 0.25 0.30 \
  --p-reorder-output results/p_reorder_sweep.json
```

**Output Files**:
- Data: `results/p_reorder_sweep.json`
- Figures: `figures/p_reorder_legit.png`, `figures/p_reorder_attack.png`

---

## Experiment 3: Window Size Tradeoff

**Objective**: Identify optimal sliding window size balancing security and usability.

**Configuration**:
```python
window_size = [1, 3, 5, 7, 9, 15, 20]
p_loss = 0.15
p_reorder = 0.15
attack_mode = "inline"
runs = 200
seed = 42
```

**Why Use Inline Attack Mode?**  
Inline attacks (replays injected during legitimate traffic) are more challenging to defend against than post-run attacks. This provides a more stringent evaluation of window size tradeoffs.

**Why p_loss = p_reorder = 0.15?**  
Moderate network stress (15% loss and reordering) creates realistic challenging conditions where the tradeoff between security and usability is most observable.

**Window Size Tradeoff Analysis**:

| Window Size | Security | Usability | Notes |
|-------------|----------|-----------|-------|
| 1 | Highest | Lowest | Strict ordering, any delay causes rejection |
| 3 | High | Low | Tolerates 2 packets out-of-order |
| **5** | **Balanced** | **Balanced** | **Recommended: good security + usability** |
| 7 | Good | Good | Higher tolerance, security still acceptable |
| 9 | Moderate | High | Good usability, security begins to degrade |
| 15 | Low | Very High | Window too large, replay window increases |
| 20 | Very Low | Highest | Approaches no-defense scenario |

**Expected Results**:
- Avg Legit: Increases with window size (W=1: ~80%, W=5: ~95%, W=20: ~98%)
- Avg Attack: Increases with window size (W=1: ~2%, W=5: ~5%, W=20: ~15%)
- Optimal Balance: W = 5-7 (Usability >95%, Attack Rate <10%)

**Reproduction**:
```bash
python scripts/run_sweeps.py \
  --runs 200 --seed 42 \
  --window-values 1 3 5 7 9 15 20 \
  --attack-mode inline \
  --window-output results/window_sweep.json
```

**Output Files**:
- Data: `results/window_sweep.json`
- Figures: `figures/window_tradeoff.png`

---

## Parameter Range Justification

### Statistical Considerations

**Monte Carlo Runs (n=200)**:
- Confidence Level: 95% (α = 0.05)
- Standard Error: ±2-3%
- Sufficient for observing statistically significant differences between defense mechanisms
- Performance: ~5.3 seconds for 200 runs (empirically measured)

**Legitimate Packets (n=20)**:
- Represents a typical IoT communication session (e.g., sensor reporting every 10 seconds for 3-5 minutes)
- Balances realism with computational efficiency
- Fixed across all experiments for fair comparison

**Replay Attempts (n=100)**:
- 5:1 attack-to-legitimate ratio represents a high-threat scenario
- Sufficient sample size for accurate attack success rate estimation
- Consistent with security evaluation best practices

### Network Parameter Ranges

**Important Note**: The specific numerical ranges used in this study (e.g., "0-30% packet loss") are **simulation parameters designed for systematic evaluation**, not direct measurements from any single literature source. These ranges were designed by:

1. **Literature Context**: Reviewing qualitative descriptions of short-range wireless network reliability in IEEE 802.15.4, LoRaWAN, and BLE deployments
2. **Coverage Principle**: Spanning from ideal to challenging conditions to fully characterize defense mechanism behavior
3. **Practical Relevance**: Focusing on ranges where networks remain usable (excluding extreme failure scenarios)

**Referenced Background Literature** (for qualitative context):
- IEEE 802.15.4/ZigBee: Baronti et al. (2007) - industrial environment variability
- LoRaWAN: Haxhibeqiri et al. (2018) - urban deployment challenges
- BLE: Gomez et al. (2012) - 2.4GHz interference effects
- Industrial WSN: Sha et al. (2017) - factory reliability studies

Detailed discussion: [`PRESENTATION.zh.md` Lines 710-829](PRESENTATION.zh.md#L710-L829)

---

## Reproducibility

All experiments use `seed=42` to ensure identical results across runs. The complete workflow:

1. Run parameter sweeps: `python scripts/run_sweeps.py --runs 200 --seed 42`
2. Generate figures: `python scripts/plot_results.py`
3. Export tables: `python scripts/export_tables.py`

Results are saved as JSON files in `results/` directory with full configuration metadata.

---

## Implementation

The parameters defined in this document are implemented in:
- Code Configuration: [`scripts/experiment_config.py`](scripts/experiment_config.py)
- Execution Script: [`scripts/run_sweeps.py`](scripts/run_sweeps.py)
- Channel Model: [`sim/channel.py`](sim/channel.py)

Test parameter configuration:
```bash
python scripts/experiment_config.py  # Prints parameter summary
```

---

## Version History

**v1.0** (2024)
- Initial parameter specification
- Three core experiments defined
- Statistical justification documented

---

## References

For detailed technical implementation and theoretical background, refer to:
- Main Documentation: [`PRESENTATION.zh.md`](PRESENTATION.zh.md)
- Project README: [`README.md`](README.md)
- Code Repository: [GitHub](https://github.com/tammakiiroha/Replay-simulation)
