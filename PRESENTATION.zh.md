# 重放攻击仿真工具包 - 技术演示

**演示者**: Romeitou  
**项目地址**: https://github.com/tammakiiroha/Replay-simulation  
**编程语言**: Python 3.11+  
**许可证**: MIT

---

## 目录

1. [项目概述](#1-项目概述)
2. [防御机制](#2-防御机制)
3. [评估指标](#3-评估指标)
4. [实验结果](#4-实验结果)
5. [关键发现](#5-关键发现)
6. [技术实现](#6-技术实现)
7. [参考文献](#7-参考文献)

---

## 1. 项目概述

### 1.1 目的

对无线控制系统（IoT设备、智能家居、工业控制）中针对重放攻击的**四种防御机制**进行定量评估的仿真工具包。

### 1.2 问题陈述

**挑战**:
- 攻击者可以截获并重放无线命令
- 在实际条件下（丢包、乱序）哪种防御机制性能最优尚不明确

**本项目贡献**:
- 在真实信道条件下进行定量评估
- 可视化安全性与可用性的权衡
- 使用1500行Python代码实现完全可重现

---

## 2. 防御机制

### 2.1 无防御（基线）

```
发送方: cmd="UNLOCK", 无计数器
  → 接收方: 接受任何命令
  → 攻击者: 可以无限次重放
```

**结果**: 100%攻击成功率

### 2.2 滚动计数器 + MAC

```
发送方: (cmd="UNLOCK", counter=5, MAC)
  → 接收方: 仅接受 counter > last_counter 的帧
  → 攻击者: 旧帧被拒绝
```

**局限**: 包乱序会导致合法帧被丢弃

### 2.3 滑动窗口

```
发送方: (cmd="UNLOCK", counter=5, MAC)
  → 接收方: 接受 counter ∈ [last - W, last + W] 的帧
  → 使用位掩码跟踪已接收的包
```

**优势**: 处理包乱序的同时防止重放

### 2.4 挑战-响应

```
接收方 → 发送方: nonce=0xABCD
发送方 → 接收方: (cmd, MAC(cmd + nonce))
```

**优势**: 最强安全性
**局限**: 需要双向通信

---

## 3. 评估指标

### 3.1 可用性指标

**合法接受率**:
```
可用性 = (接受的合法帧数 / 总合法帧数) × 100%
```

**目标**: >95% (行业标准)

### 3.2 安全性指标

**攻击成功率**:
```
安全风险 = (接受的攻击帧数 / 总攻击尝试数) × 100%
```

**目标**: <1% (可接受风险)

---

## 4. 实验结果

### 4.1 丢包对可用性的影响

| 防御机制 | p_loss=0.0 | p_loss=0.1 | p_loss=0.3 |
|---------|------------|------------|------------|
| 无防御 | 100.0% | 100.0% | 100.0% |
| 滚动计数器 | 100.0% | 99.5% | 98.2% |
| 滑动窗口 | 100.0% | 99.6% | 98.5% |
| 挑战-响应 | 100.0% | 89.2% | 67.4% |

**观察**: 挑战-响应因双向通信开销受丢包影响最大。

### 4.2 包乱序对可用性的影响

| 防御机制 | p_reorder=0.0 | p_reorder=0.2 | p_reorder=0.4 |
|---------|---------------|---------------|---------------|
| 滚动计数器 | 99.8% | 84.2% | 68.5% |
| 滑动窗口 | 99.8% | 98.1% | 96.7% |

**观察**: 即使在40%包乱序的情况下，滑动窗口仍能保持>95%的可用性，而滚动计数器降至68.5%。

### 4.3 窗口大小权衡

*实验条件: p_loss=0.05, p_reorder=0.3*

| 窗口大小 (W) | 可用性 | 攻击成功率 |
|-------------|--------|-----------|
| 1           | 27.6%  | 4.510%    |
| 3           | 95.1%  | 0.220%    |
| 5           | 95.1%  | 0.300%    |
| 10          | 95.2%  | 0.485%    |

**推荐**: W=3 或 W=5 提供最佳平衡

---

## 5. 关键发现

### 5.1 主要结论

1. **滚动计数器的局限**: 在包乱序环境下可用性下降15%
2. **滑动窗口的优势**: 保持95%可用性，攻击成功率0.3% (W=3-5)
3. **挑战-响应的权衡**: 最强安全性但需要双向通信

### 5.2 实用建议

| 系统特性 | 推荐防御机制 |
|---------|-------------|
| 单向通信，稳定网络 | 滚动计数器 |
| 单向通信，不稳定网络 | **滑动窗口 (W=5)** |
| 双向通信，高安全要求 | 挑战-响应 |

---

## 6. 技术实现

### 6.1 滑动窗口算法

```python
class ReceiverState:
    last_counter: int = -1
    received_mask: int = 0  # 窗口位掩码

def verify_with_window(counter: int, state: ReceiverState, W: int) -> bool:
    if state.last_counter < 0:
        state.last_counter = counter
        state.received_mask = 1
        return True
    
    diff = counter - state.last_counter
    
    if diff > 0:  # 新帧，推进窗口
        if diff <= W:
            offset = diff - 1
            if state.received_mask & (1 << offset):
                return False  # 检测到重放
            state.received_mask |= (1 << offset)
        state.received_mask = (state.received_mask >> diff) | 1
        state.last_counter = counter
        return True
    
    elif diff <= -W:  # 太旧
        return False
    
    else:  # 在窗口内
        offset = -diff
        if state.received_mask & (1 << offset):
            return False  # 检测到重放
        state.received_mask |= (1 << offset)
        return True
```

### 6.2 蒙特卡洛仿真

```python
def run_experiment(config: SimulationConfig) -> AggregateStats:
    results = []
    for run_id in range(config.num_runs):
        seed = config.base_seed + run_id
        stats = run_single_trial(config, seed)
        results.append(stats)
    
    return compute_aggregate(results)
```

**可靠性**: 每个配置进行200-500次试验（95%置信区间）

---

## 7. 参考文献

[1] Perrig, A., Szewczyk, R., Tygar, J. D., Wen, V., & Culler, D. E. (2002). SPINS: Security Protocols for Sensor Networks. *Wireless Networks*, 8(5), 521-534.

[2] Kent, S., & Seo, K. (2005). Security Architecture for the Internet Protocol. RFC 4301, Internet Engineering Task Force.

[3] Bellare, M., Canetti, R., & Krawczyk, H. (1996). Keying Hash Functions for Message Authentication. In *Advances in Cryptology—CRYPTO'96*, pp. 1-15. Springer.

[4] Needham, R. M., & Schroeder, M. D. (1978). Using Encryption for Authentication in Large Networks of Computers. *Communications of the ACM*, 21(12), 993-999.

[5] Tanenbaum, A. S., & Wetherall, D. J. (2011). *Computer Networks* (5th ed.). Prentice Hall.

[6] Syverson, P. (1994). A Taxonomy of Replay Attacks. In *Proceedings of Computer Security Foundations Workshop VII*, pp. 187-191. IEEE.

[7] Rescorla, E. (2018). The Transport Layer Security (TLS) Protocol Version 1.3. RFC 8446, IETF.

---

## 总结

### 项目贡献

1. 对4种防御机制进行统一评估
2. 真实信道建模（丢包、乱序）
3. 定量评估（200-500次蒙特卡洛试验）
4. 完全可重现（固定种子、开源）
5. 出版级可视化和文档

### 联系方式

- GitHub: https://github.com/tammakiiroha/Replay-simulation
- 许可证: MIT

**感谢您的关注！**

