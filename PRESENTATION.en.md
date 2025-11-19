# Replay Attack Simulation Toolkit - Technical Presentation

**Presenter**: Romeitou  
**Project URL**: https://github.com/tammakiiroha/Replay-simulation  
**Language**: Python 3.11+  
**License**: MIT

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Defense Mechanisms](#2-defense-mechanisms)
3. [Evaluation Metrics](#3-evaluation-metrics)
4. [Experimental Results](#4-experimental-results)
5. [Key Findings](#5-key-findings)
6. [Technical Implementation](#6-technical-implementation)
7. [References](#7-references)

---

## 1. Project Overview

### 1.1 Purpose

A simulation toolkit for quantitative evaluation of **four defense mechanisms** against replay attacks in wireless control systems (IoT devices, smart homes, industrial control).

### 1.2 Problem Statement

**Challenge**:
- Attackers can intercept and replay wireless commands
- Uncertain which defense mechanism performs best under realistic conditions (packet loss, reordering)

**Our Contribution**:
- Quantitative evaluation under realistic channel conditions
- Visualization of security-usability tradeoffs
- Fully reproducible with 1500 lines of Python code

---

## 2. Defense Mechanisms

### 2.1 No Defense (Baseline)

```
Sender: cmd="UNLOCK", no_counter
  → Receiver: accepts any command
  → Attacker: can replay infinitely
```

**Result**: 100% attack success rate

### 2.2 Rolling Counter + MAC

```
Sender: (cmd="UNLOCK", counter=5, MAC)
  → Receiver: accepts if counter > last_counter
  → Attacker: old frames rejected
```

**Limitation**: Packet reordering causes legitimate frame drops

### 2.3 Sliding Window

```
Sender: (cmd="UNLOCK", counter=5, MAC)
  → Receiver: accepts counter ∈ [last - W, last + W]
  → Uses bitmask to track received packets
```

**Advantage**: Handles packet reordering while preventing replays

### 2.4 Challenge-Response

```
Receiver → Sender: nonce=0xABCD
Sender → Receiver: (cmd, MAC(cmd + nonce))
```

**Advantage**: Strongest security
**Limitation**: Requires bidirectional communication

---

## 3. Evaluation Metrics

### 3.1 Usability Metric

**Legitimate Acceptance Rate**:
```
usability = (accepted_legit_frames / total_legit_frames) × 100%
```

**Target**: >95% (industry standard)

### 3.2 Security Metric

**Attack Success Rate**:
```
security_risk = (accepted_attack_frames / total_attack_attempts) × 100%
```

**Target**: <1% (acceptable risk)

---

## 4. Experimental Results

### 4.1 Impact of Packet Loss on Usability

| Defense Mechanism | p_loss=0.0 | p_loss=0.1 | p_loss=0.3 |
|-------------------|------------|------------|------------|
| No Defense        | 100.0%     | 100.0%     | 100.0%     |
| Rolling Counter   | 100.0%     | 99.5%      | 98.2%      |
| Sliding Window    | 100.0%     | 99.6%      | 98.5%      |
| Challenge-Response| 100.0%     | 89.2%      | 67.4%      |

**Observation**: Challenge-Response is most affected by packet loss due to bidirectional communication overhead.

### 4.2 Impact of Packet Reordering on Usability

| Defense Mechanism | p_reorder=0.0 | p_reorder=0.2 | p_reorder=0.4 |
|-------------------|---------------|---------------|---------------|
| Rolling Counter   | 99.8%         | 84.2%         | 68.5%         |
| Sliding Window    | 99.8%         | 98.1%         | 96.7%         |

**Observation**: Sliding window maintains >95% usability even with 40% packet reordering, while rolling counter drops to 68.5%.

### 4.3 Window Size Tradeoff

*Experimental conditions: p_loss=0.05, p_reorder=0.3*

| Window Size (W) | Usability | Attack Success Rate |
|-----------------|-----------|---------------------|
| 1               | 27.6%     | 4.510%              |
| 3               | 95.1%     | 0.220%              |
| 5               | 95.1%     | 0.300%              |
| 10              | 95.2%     | 0.485%              |

**Recommendation**: W=3 or W=5 provides optimal balance

---

## 5. Key Findings

### 5.1 Main Conclusions

1. **Rolling Counter limitation**: 15% usability drop under packet reordering
2. **Sliding Window advantage**: Maintains 95% usability with 0.3% attack success rate (W=3-5)
3. **Challenge-Response tradeoff**: Strongest security but requires bidirectional communication

### 5.2 Practical Recommendations

| System Characteristics | Recommended Defense |
|-----------------------|---------------------|
| Unidirectional, stable network | Rolling Counter |
| Unidirectional, unstable network | **Sliding Window (W=5)** |
| Bidirectional, high security requirement | Challenge-Response |

---

## 6. Technical Implementation

### 6.1 Sliding Window Algorithm

```python
class ReceiverState:
    last_counter: int = -1
    received_mask: int = 0  # Bitmask for window

def verify_with_window(counter: int, state: ReceiverState, W: int) -> bool:
    if state.last_counter < 0:
        state.last_counter = counter
        state.received_mask = 1
        return True
    
    diff = counter - state.last_counter
    
    if diff > 0:  # New frame, advance window
        if diff <= W:
            offset = diff - 1
            if state.received_mask & (1 << offset):
                return False  # Replay detected
            state.received_mask |= (1 << offset)
        state.received_mask = (state.received_mask >> diff) | 1
        state.last_counter = counter
        return True
    
    elif diff <= -W:  # Too old
        return False
    
    else:  # Within window
        offset = -diff
        if state.received_mask & (1 << offset):
            return False  # Replay detected
        state.received_mask |= (1 << offset)
        return True
```

### 6.2 Monte Carlo Simulation

```python
def run_experiment(config: SimulationConfig) -> AggregateStats:
    results = []
    for run_id in range(config.num_runs):
        seed = config.base_seed + run_id
        stats = run_single_trial(config, seed)
        results.append(stats)
    
    return compute_aggregate(results)
```

**Reliability**: 200-500 trials per configuration (95% confidence interval)

---

## 7. References

[1] Perrig, A., Szewczyk, R., Tygar, J. D., Wen, V., & Culler, D. E. (2002). SPINS: Security Protocols for Sensor Networks. *Wireless Networks*, 8(5), 521-534.

[2] Kent, S., & Seo, K. (2005). Security Architecture for the Internet Protocol. RFC 4301, Internet Engineering Task Force.

[3] Bellare, M., Canetti, R., & Krawczyk, H. (1996). Keying Hash Functions for Message Authentication. In *Advances in Cryptology—CRYPTO'96*, pp. 1-15. Springer.

[4] Needham, R. M., & Schroeder, M. D. (1978). Using Encryption for Authentication in Large Networks of Computers. *Communications of the ACM*, 21(12), 993-999.

[5] Tanenbaum, A. S., & Wetherall, D. J. (2011). *Computer Networks* (5th ed.). Prentice Hall.

[6] Syverson, P. (1994). A Taxonomy of Replay Attacks. In *Proceedings of Computer Security Foundations Workshop VII*, pp. 187-191. IEEE.

[7] Rescorla, E. (2018). The Transport Layer Security (TLS) Protocol Version 1.3. RFC 8446, IETF.

---

## Summary

### Project Contributions

1. Unified evaluation of 4 defense mechanisms
2. Realistic channel modeling (packet loss, reordering)
3. Quantitative evaluation (200-500 Monte Carlo trials)
4. Fully reproducible (fixed seeds, open source)
5. Publication-quality visualizations and documentation

### Contact

- GitHub: https://github.com/tammakiiroha/Replay-simulation
- License: MIT

**Thank you for your attention!**

