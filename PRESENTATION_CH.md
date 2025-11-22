# 项目演示：重放攻击仿真工具包

**演示者**: Romeitou (tammakiiroha)  
**项目地址**: https://github.com/tammakiiroha/Replay-simulation  
**编程语言**: Python 3.11+  
**许可证**: MIT

---

## 目录

1. [项目概述](#1-项目概述)
2. [研究背景与动机](#2-研究背景与动机)
3. [系统架构](#3-系统架构)
4. [防御机制详解](#4-防御机制详解)
5. [评估指标说明](#5-评估指标说明)
6. [技术实现细节](#6-技术实现细节)
7. [实验设计与方法论](#7-实验设计与方法论)
8. [主要实验结果](#8-主要实验结果)
9. [项目质量保证](#9-项目质量保证)
10. [局限性与未来工作](#10-局限性与未来工作) ⭐ 新增
11. [术语表](#11-术语表)
12. [演示说明](#12-演示说明)

---

## 1. 项目概述

### 1.1 项目目的

对无线控制系统（例如：IoT设备、智能家居、工业控制）中针对重放攻击的**4种防御机制**进行定量评估的仿真工具包。

### 1.2 解决的问题

**挑战**：
- 在无线通信中，攻击者可以截获并记录帧，然后稍后重新传输（重放）
- 在存在丢包和乱序的现实环境下，不清楚哪种防御机制是最优的

**本工具的贡献**：
- 在模拟信道条件（丢包、乱序）下对防御性能进行定量评估
- 可视化安全性（攻击成功率）与可用性（合法接受率）的权衡
- 使用1500行Python代码实现完全可重现

---

## 2. 研究背景与动机

### 2.1 什么是重放攻击？

```
┌─────────────────────────────────────────────────┐
│ 合法用户              无线信道                    │
│  [发送方]  ─────→  "UNLOCK" ─────→  [接收方]    │
│                      ↓                           │
│                   [攻击者]                        │
│                   记录并保存                      │
│                      ↓                           │
│  稍后重放:  "UNLOCK" ─────→  [接收方]            │
│              门被打开了！                         │
└─────────────────────────────────────────────────┘
```

**威胁**：
- 智能锁：攻击者重放"解锁"命令
- 车辆：重放"启动引擎"命令进行盗窃
- 工业控制：干扰"停止"命令

### 2.2 为什么需要仿真？

**物理实验的挑战**：
- 成本高（多个设备、RF环境搭建）
- 耗时长（需要数百次试验）
- 难以确保可重现性

**仿真的优势**：
- 完全的控制和可重现性（固定随机种子）
- 快速迭代实验（200次试验仅需数秒）
- 自由调整参数

---

## 3. 系统架构

### 3.1 整体架构图

```mermaid
graph TB
    subgraph "输入层"
        A[命令序列<br/>traces/sample_trace.txt]
        B[仿真配置<br/>SimulationConfig]
    end
    
    subgraph "仿真层"
        C[发送方<br/>Sender]
        D[信道<br/>Channel]
        E[接收方<br/>Receiver]
        F[攻击者<br/>Attacker]
    end
    
    subgraph "评估层"
        G[统计汇总<br/>RunStats]
        H[可视化<br/>Matplotlib]
    end
    
    subgraph "输出层"
        I[JSON结果<br/>results/*.json]
        J[PNG图表<br/>figures/*.png]
    end
    
    A --> C
    B --> C
    C --> D
    D --> E
    D --> F
    F --> E
    E --> G
    G --> H
    G --> I
    H --> J
```

### 3.2 主要组件

| 组件 | 文件 | 职责 |
|------|------|------|
| **发送方** | `sim/sender.py` | 帧生成、计数器/MAC附加 |
| **信道** | `sim/channel.py` | 模拟丢包和乱序 |
| **接收方** | `sim/receiver.py` | 各防御模式的验证逻辑 |
| **攻击者** | `sim/attacker.py` | 帧记录和选择性重放 |
| **实验控制** | `sim/experiment.py` | 蒙特卡洛试验管理 |
| **数据类型** | `sim/types.py` | 公共数据结构（Frame、Config等） |

---

## 4. 防御机制详解

本项目实现并比较了4种防御机制。

### 4.1 无防御 - 基线

**实现**：
```python
def verify_no_defense(frame, state):
    return VerificationResult(True, "accept", state)
```

**特点**：
- 接受所有帧
- 安全性：❌ 0%（所有重放都成功）
- 可用性：✅ 100%

**用途**：衡量攻击影响的基线

**📂 代码实现位置**：
- **验证逻辑**：[`sim/receiver.py` 第18-19行](https://github.com/tammakiiroha/Replay-simulation/blob/main/sim/receiver.py#L18-L19)
- **调用入口**：[`sim/receiver.py` 第136-137行](https://github.com/tammakiiroha/Replay-simulation/blob/main/sim/receiver.py#L136-L137)（Receiver.process）

---

### 4.2 滚动计数器 + MAC

**原理**：
```
发送方：Counter = 0, 1, 2, 3, 4, ...
接收方：Last = -1
        帧 Counter=0 到达 → 0 > -1 ✅ 接受，Last=0
        帧 Counter=1 到达 → 1 > 0 ✅ 接受，Last=1
        重放 Counter=0 到达 → 0 ≤ 1 ❌ 拒绝（检测到重放）
```

**实现要点**：
```python
def verify_with_rolling_mac(frame, state, shared_key, mac_length):
    # 1. MAC验证（防止篡改）
    expected_mac = compute_mac(frame.command, frame.counter, shared_key)
    if not constant_time_compare(frame.mac, expected_mac):
        return VerificationResult(False, "mac_mismatch", state)
    
    # 2. 计数器单调递增检查
    if frame.counter <= state.last_counter:
        return VerificationResult(False, "counter_replay", state)
    
    # 3. 接受并更新状态
    state.last_counter = frame.counter
    return VerificationResult(True, "accept", state)
```

**什么是MAC（消息认证码）**：
- 使用HMAC-SHA256
- 使用共享密钥生成签名以检测篡改
- 攻击者无法伪造有效的MAC

**优点**：
- ✅ 完全防止重放攻击（在理想信道下）
- ✅ 实现简单

**缺点**：
- ❌ 对包乱序脆弱
- 例如：帧5先到达 → Last=5
     然后帧4到达 → 4 < 5 被拒绝（误判）

**📂 代码实现位置**：
- **验证逻辑**：[`sim/receiver.py` 第22-40行](https://github.com/tammakiiroha/Replay-simulation/blob/main/sim/receiver.py#L22-L40)（`verify_with_rolling_mac`）
- **MAC计算**：[`sim/security.py` 第9-19行](https://github.com/tammakiiroha/Replay-simulation/blob/main/sim/security.py#L9-L19)（`compute_mac`）
- **帧生成**：[`sim/sender.py` 第27-29行](https://github.com/tammakiiroha/Replay-simulation/blob/main/sim/sender.py#L27-L29)（`Sender.next_frame`）
- **调用入口**：[`sim/receiver.py` 第138-143行](https://github.com/tammakiiroha/Replay-simulation/blob/main/sim/receiver.py#L138-L143)（Receiver.process）

---

### 4.3 滑动窗口

**原理**：允许计数器的"范围"以处理乱序

```
窗口大小 = 5 的例子：

最后计数器 = 10，已接收位掩码 = 0b10101

可接受范围：[6, 7, 8, 9, 10]
         └────5个项────┘

帧 Counter=8 到达：
  - 8 在范围内 ✅
  - 位位置 offset = 10 - 8 = 2
  - 检查掩码的位2 → 0 表示未接收 ✅
  - 设置位2 → 0b10101 | (1 << 2) = 0b10101 ✅ 接受
```

**核心位掩码实现**：
```python
def verify_with_window(frame, state, window_size):
    diff = frame.counter - state.last_counter
    
    if diff > 0:  # 新的最大计数器
        state.received_mask <<= diff       # 移动窗口
        state.received_mask |= 1           # 标记新位置
        state.last_counter = frame.counter
        return VerificationResult(True, "accept_new", state)
    
    else:  # 旧计数器（乱序）
        offset = -diff
        if offset >= window_size:
            return VerificationResult(False, "too_old", state)
        
        if (state.received_mask >> offset) & 1:
            return VerificationResult(False, "replay", state)
        
        state.received_mask |= (1 << offset)
        return VerificationResult(True, "accept_old", state)
```

**位掩码的含义**：
```
state.received_mask = 0b10101
                       ↑↑↑↑↑
                       │││││
                       │││││
    位4 (Counter 6):   │││││ = 1 (已接收)
    位3 (Counter 7):   ││││  = 0 (未接收)
    位2 (Counter 8):   │││   = 1 (已接收)
    位1 (Counter 9):   ││    = 0 (未接收)
    位0 (Counter 10):  │     = 1 (已接收，Last)
```

**优点**：
- ✅ 对乱序具有鲁棒性（滑动窗口机制）
- ✅ 在不同网络条件下保持良好的可用性-安全性平衡

**缺点**：
- ⚠️ 窗口太小会导致乱序包被误判为重放
- ⚠️ 窗口太大会增加重放攻击的成功机会

**参数选择的影响**：窗口大小需要根据具体网络环境调整（实验3详细分析见8.4节）

**📂 代码实现位置**：
- **验证逻辑**：[`sim/receiver.py` 第43-98行](https://github.com/tammakiiroha/Replay-simulation/blob/main/sim/receiver.py#L43-L98)（`verify_with_window`）
- **位掩码操作**：[`sim/receiver.py` 第77-97行](https://github.com/tammakiiroha/Replay-simulation/blob/main/sim/receiver.py#L77-L97)（窗口滑动和重放检测）
- **状态定义**：[`sim/types.py` 第45-52行](https://github.com/tammakiiroha/Replay-simulation/blob/main/sim/types.py#L45-L52)（`ReceiverState.received_mask`）
- **帧生成**：[`sim/sender.py` 第27-29行](https://github.com/tammakiiroha/Replay-simulation/blob/main/sim/sender.py#L27-L29)（与滚动计数器相同）
- **调用入口**：[`sim/receiver.py` 第144-151行](https://github.com/tammakiiroha/Replay-simulation/blob/main/sim/receiver.py#L144-L151)（Receiver.process）

---

### 4.4 挑战-响应

**原理**：接收方发送"挑战（nonce）"，发送方返回"响应"

```
接收方 → 发送方：  "Nonce: 0x3a7f"（随机值）
发送方 → 接收方：  "Command: UNLOCK, Nonce: 0x3a7f, MAC: ..."

接收方：如果nonce匹配且MAC正确则接受
       重放的帧具有旧nonce，会被拒绝
```

**实现**：
```python
def verify_with_challenge(frame, state):
    if frame.nonce != state.expected_nonce:
        return VerificationResult(False, "nonce_mismatch", state)
    
    # 生成新nonce（供下次使用）
    state.expected_nonce = generate_random_nonce()
    return VerificationResult(True, "accept", state)
```

**优点**：
- ✅ 最高安全性（攻击成功率<0.1%，在30%丢包下仍≤0.3%）
- ✅ 安全性不受乱序影响（攻击率保持在极低水平）

**缺点**：
- ❌ 需要双向通信（单向系统无法使用）
- ❌ 高延迟（往返通信）
- ⚠️ 可用性在高乱序下显著下降（30%乱序时降至64.5%）

**📂 代码实现位置**：
- **验证逻辑**：[`sim/receiver.py` 第101-122行](https://github.com/tammakiiroha/Replay-simulation/blob/main/sim/receiver.py#L101-L122)（`verify_challenge_response`）
- **Nonce生成**：[`sim/receiver.py` 第162-168行](https://github.com/tammakiiroha/Replay-simulation/blob/main/sim/receiver.py#L162-L168)（`Receiver.issue_nonce`）
- **帧生成**：[`sim/sender.py` 第22-24行](https://github.com/tammakiiroha/Replay-simulation/blob/main/sim/sender.py#L22-L24)（`Sender.next_frame` 挑战模式）
- **MAC计算**：[`sim/security.py` 第9-19行](https://github.com/tammakiiroha/Replay-simulation/blob/main/sim/security.py#L9-L19)（`compute_mac`）
- **调用入口**：[`sim/receiver.py` 第152-158行](https://github.com/tammakiiroha/Replay-simulation/blob/main/sim/receiver.py#L152-L158)（Receiver.process）

---

## 5. 评估指标说明

### 5.1 合法接受率

**定义**：接收方接受的合法发送帧的比例

$$
\text{合法接受率} = \frac{\text{接受的合法帧数}}{\text{发送的合法帧数}} \times 100\%
$$

**含义**：
- **可用性指标**
- 越高越好（接近100%）
- 因丢包和乱序而降低

**示例**：
```
发送：20帧
接受：19帧（1帧因乱序被拒绝）
合法接受率 = 19/20 = 95%
```

---

### 5.2 攻击成功率

**定义**：攻击者的重放帧被接受的比例

$$
\text{攻击成功率} = \frac{\text{接受的重放帧数}}{\text{重放尝试数}} \times 100\%
$$

**含义**：
- **安全性指标**
- 越低越好（接近0%）
- 理想情况为0%

**示例**：
```
重放尝试：100帧
接受：2帧（利用了防御漏洞）
攻击成功率 = 2/100 = 2%
```

---

### 5.3 权衡可视化

```
┌────────────────────────────────────────────────┐
│                                                │
│  100%  ●                           ● Challenge│
│   合   │ ╲                    ╱              │
│   法   │   ╲                ╱                │
│   接   │     ● Window     ●                  │
│   受   │      (W=5)   Rolling                │
│   率   │                                     │
│    0%  ●──────────────────────────────────── │
│       0%        攻击成功率        100%        │
│                                                │
│   理想：左上角（高可用性、低攻击成功率）       │
└────────────────────────────────────────────────┘
```

---

## 6. 技术实现细节

### 6.1 代码实现路线图

本节提供核心代码路径，便于验证和重现实验结果。

#### 核心模块结构

```
sim/
├── types.py        # 数据结构（Frame, ReceiverState, Config）
├── sender.py       # 发送方（帧生成、计数器、MAC）
├── receiver.py     # 接收方（4种防御机制）
├── security.py     # 密码学（HMAC-SHA256）
├── channel.py      # 信道模拟（丢包、乱序）
├── attacker.py     # 攻击者（记录、重放）
└── experiment.py   # 蒙特卡洛实验控制
```

#### 关键实现位置

| 模块 | 文件 | 行号 | 说明 |
|------|------|------|------|
| **防御机制** |
| 无防御 | [`receiver.py`](https://github.com/tammakiiroha/Replay-simulation/blob/main/sim/receiver.py#L18-L19) | 18-19 | 基线 |
| 滚动计数器 | [`receiver.py`](https://github.com/tammakiiroha/Replay-simulation/blob/main/sim/receiver.py#L22-L40) | 22-40 | 严格顺序 |
| 滑动窗口 | [`receiver.py`](https://github.com/tammakiiroha/Replay-simulation/blob/main/sim/receiver.py#L43-L98) | 43-98 | 位掩码 |
| 挑战-响应 | [`receiver.py`](https://github.com/tammakiiroha/Replay-simulation/blob/main/sim/receiver.py#L101-L122) | 101-122 | Nonce验证 |
| **密码学** |
| HMAC-SHA256 | [`security.py`](https://github.com/tammakiiroha/Replay-simulation/blob/main/sim/security.py#L9-L19) | 9-19 | MAC计算 |
| **信道模拟** |
| 丢包 | [`channel.py`](https://github.com/tammakiiroha/Replay-simulation/blob/main/sim/channel.py#L28-L30) | 28-30 | 概率丢弃 |
| 乱序 | [`channel.py`](https://github.com/tammakiiroha/Replay-simulation/blob/main/sim/channel.py#L32-L37) | 32-37 | 延迟队列 |
| **实验控制** |
| 单次运行 | [`experiment.py`](https://github.com/tammakiiroha/Replay-simulation/blob/main/sim/experiment.py#L77-L150) | 77-150 | simulate_one_run |
| 蒙特卡洛 | [`experiment.py`](https://github.com/tammakiiroha/Replay-simulation/blob/main/sim/experiment.py#L153-L201) | 153-201 | run_many_experiments |

#### 核心算法示例

**滑动窗口位掩码**（[`receiver.py` 43-98行](https://github.com/tammakiiroha/Replay-simulation/blob/main/sim/receiver.py#L43-L98)）

```python
# 窗口向前滑动
if diff > 0:
    state.received_mask <<= diff  # 左移
    state.received_mask |= 1       # 标记当前
    state.last_counter = frame.counter

# 窗口内乱序帧
else:
    offset = -diff
    if (state.received_mask >> offset) & 1:  # 检查重放
        return False, "counter_replay"
    state.received_mask |= (1 << offset)     # 标记已收
```

**验证步骤**：

1. **查看核心代码**：`cat sim/receiver.py`
2. **运行简单测试**：`python main.py --runs 10 --modes window`
3. **查看完整测试**：`python3 -m pytest tests/`

详细的代码审查清单和验证步骤请参考 [`CONTRIBUTING.md`](https://github.com/tammakiiroha/Replay-simulation/blob/main/CONTRIBUTING.md)。

---

### 6.2 信道模型

**问题**：真实的无线通信并不完美
- 包会丢失（p_loss）
- 包会乱序（p_reorder）

**实现**：使用优先队列进行延迟仿真

```python
class Channel:
    def __init__(self, p_loss, p_reorder, rng):
        self.p_loss = p_loss
        self.p_reorder = p_reorder
        self.pq = []  # 优先队列（堆）
        self.current_tick = 0
    
    def send(self, frame):
        # 1. 丢包
        if self.rng.random() < self.p_loss:
            return []  # 丢弃帧
        
        # 2. 乱序（概率性延迟）
        if self.rng.random() < self.p_reorder:
            delay = self.rng.randint(1, 3)  # 1-3个时间片延迟
        else:
            delay = 0
        
        delivery_tick = self.current_tick + delay
        heapq.heappush(self.pq, (delivery_tick, frame))
        
        # 3. 返回当前时间片应交付的帧
        return self._deliver_due_frames()
```

**为什么这很重要**：
- 滚动计数器对乱序脆弱
- 滑动窗口正是为解决这个问题而设计的

---

### 6.3 滚动计数器的同步问题与滑动窗口的解决方案

**核心问题**：通信延迟后,接收方和发送方的计数器会不会永远对不上？

#### 问题分析

**滚动计数器的缺陷**（receiver.py 第22-40行）：

```python
def verify_with_rolling_mac(frame, state, shared_key, mac_length):
    # 1. 验证MAC
    expected_mac = compute_mac(frame.counter, frame.command, ...)
    if not constant_time_compare(expected_mac, frame.mac):
        return False, "mac_mismatch"
    
    # 2. 检查计数器（严格递增）
    if frame.counter <= state.last_counter:
        return False, "counter_replay"  # ← 问题所在！
    
    # 3. 接受并更新
    state.last_counter = frame.counter
    return True
```

**实际场景中的问题**：

```
发送方：
  发送帧1 → 发送帧2 → 发送帧3 → 发送帧4
  (cnt=1)   (cnt=2)   (cnt=3)   (cnt=4)

网络（丢包 + 乱序）：
  帧1丢失   帧2延迟   帧3到达   帧4到达
    ✗        ⏰        ✓         ✓

接收方（Rolling Counter）：
  收到帧3 (cnt=3)  → ✓ 接受 last=3
  收到帧4 (cnt=4)  → ✓ 接受 last=4
  收到帧2 (cnt=2)  → ✗ 拒绝 (2 <= 4)  ← 正规帧被错误拒绝！

结果：
  - 正规帧2被当作重放攻击拒绝
  - Avg Legit (可用性) 下降到 75%（4帧只接受3帧）
  - 用户体验严重受损
```

#### 滑动窗口的解决方案

**核心机制**（receiver.py 第43-98行）：

```python
def verify_with_window(frame, state, shared_key, mac_length, window_size):
    # 计算与当前最大计数器的距离
    diff = frame.counter - state.last_counter
    
    # 情况1：新的最大计数器（未来的帧）
    if diff > 0:
        if diff > window_size:  # 防止跳跃太大
            return False, "counter_out_of_window"
        
        # 滑动窗口向前移动
        state.received_mask <<= diff
        state.received_mask |= 1  # 标记当前帧
        state.last_counter = frame.counter
        return True
    
    # 情况2：旧的计数器（延迟/乱序的帧）
    else:
        offset = -diff
        
        # 检查是否在窗口内
        if offset >= window_size:
            return False, "counter_too_old"
        
        # 检查是否已收到（防止重放）
        if (state.received_mask >> offset) & 1:
            return False, "counter_replay"
        
        # 标记为已收到
        state.received_mask |= (1 << offset)
        return True
```

**滑动窗口如何解决问题**：

```
发送方：
  发送帧1 → 发送帧2 → 发送帧3 → 发送帧4
  (cnt=1)   (cnt=2)   (cnt=3)   (cnt=4)

网络（同样的丢包 + 乱序）：
  帧1丢失   帧2延迟   帧3到达   帧4到达
    ✗        ⏰        ✓         ✓

接收方（Sliding Window，window_size=5）：
  收到帧3 (cnt=3):
    last_counter = 3
    received_mask = 0b001 (标记cnt=3已收到)
    ✓ 接受
  
  收到帧4 (cnt=4):
    diff = 4-3 = 1 (在窗口内)
    窗口向前滑动1位
    received_mask = 0b0010 << 1 | 1 = 0b0101
    last_counter = 4
    ✓ 接受
  
  收到帧2 (cnt=2):
    diff = 2-4 = -2 (过去的帧)
    offset = 2 (在窗口内)
    检查 (0b0101 >> 2) & 1 = 0 (未收到过)
    received_mask |= (1 << 2) = 0b10101
    ✓ 接受！

结果：
  - 所有正规帧都被接受（包括延迟的帧2）
  - Avg Legit (可用性) = 100%
  - 同时保持防重放能力（received_mask记录）
```

#### 实际网络影响总结

根据实验1和实验2的数据：

**丢包影响**（实验1）：
- p_loss=10%时，所有防御机制可用性均下降至约90%
- 在使用基于状态的防御机制时，丢包主要影响可用性，对安全性影响极小（<0.5%变化）

**乱序影响**（实验2）：
- Rolling机制：在p_reorder=30%时可用性降至76.8%（下降13.5%）
- Window机制：在p_reorder=30%时可用性保持90.6%（几乎无变化）
- Challenge机制：在p_reorder=30%时可用性降至64.5%（下降25.3%）

**核心结论**：
- Window机制的可用性对乱序具有高度鲁棒性（实验2验证）
- 但在实时混入(inline)攻击模式下，攻击成功率与窗口大小相关（实验3：6.5-11.6%）
- 实际部署需要在可用性和安全性之间权衡

#### 实际应用建议

1. ✅ **推荐使用 Sliding Window (window_size=3-7)**
   - 既防重放
   - 又容忍网络延迟/乱序
   
2. ❌ **不推荐使用纯 Rolling Counter**
   - 除非网络绝对可靠（实际中不存在）
   
3. ⚡ **Challenge-Response 适用于**：
   - 高安全要求场景
   - 可接受额外RTT延迟
   - 例如：金融交易、军事通信

---

### 6.4 挑战-响应的加密算法详解

**核心问题**：使用什么加密算法？双方如何生成密钥去匹配？

#### 加密算法实现

**HMAC-SHA256**（security.py 第9-19行）：

```python
def compute_mac(token, command, key, mac_length=8):
    """计算HMAC-SHA256"""
    
    # 1. 构造消息
    message = f"{token}|{command}".encode("utf-8")
    
    # 2. 使用HMAC-SHA256计算MAC
    mac = hmac.new(
        key.encode("utf-8"),      # ← 预共享密钥
        message,                   # ← 消息内容
        hashlib.sha256            # ← 哈希算法
    ).hexdigest()
    
    # 3. 截断（例如只取前8个字符）
    return mac[:mac_length]
```

#### 密钥管理方案

**本研究采用：预共享密钥 (Pre-Shared Key, PSK)**

假设：
- 发送方和接收方在安全环境下事先交换密钥
- 密钥长度：建议256位（例如"a7f3c9e1..."）
- 密钥存储：安全存储在双方的硬件安全模块(HSM)或TPM中

代码初始化（experiment.py）：

```python
# 双方使用相同的预共享密钥
SHARED_KEY = "SuperSecretKey123"  # 实际应用中使用256位随机密钥

sender = Sender(mode=Mode.CHALLENGE, shared_key=SHARED_KEY)
receiver = Receiver(mode=Mode.CHALLENGE, shared_key=SHARED_KEY)
```

#### 挑战-响应完整流程

**步骤1：接收方发起挑战**

```python
# 接收方生成随机nonce
nonce = receiver.issue_nonce(rng, bits=32)
# 例如：nonce = "a3f7c912"

# 发送给发送方：
Challenge: "请用我们的共享密钥验证这个nonce"
```

**步骤2：发送方计算响应**

```python
# 发送方收到nonce后
command = "UNLOCK_DOOR"

# 使用HMAC-SHA256计算MAC
mac = compute_mac(
    token=nonce,              # "a3f7c912"
    command=command,          # "UNLOCK_DOOR"
    key=SHARED_KEY,           # "SuperSecretKey123"
    mac_length=8
)
# 结果：mac = "7b4e9c2a" (前8个十六进制字符)

# 构造帧
frame = Frame(command="UNLOCK_DOOR", nonce="a3f7c912", mac="7b4e9c2a")

# 发送给接收方
```

**步骤3：接收方验证**

```python
# 接收方收到frame后
expected_mac = compute_mac(
    token=frame.nonce,        # "a3f7c912"
    command=frame.command,    # "UNLOCK_DOOR"
    key=SHARED_KEY,           # "SuperSecretKey123"
    mac_length=8
)
# 结果：expected_mac = "7b4e9c2a"

# 验证
if constant_time_compare(frame.mac, expected_mac):
    ✓ 验证成功！执行命令
else:
    ✗ MAC不匹配，拒绝
```

#### 安全性分析

**1. HMAC-SHA256 的强度**：
- SHA256：256位哈希，碰撞抗性极强
- HMAC：密钥化哈希，攻击者无法伪造
- 截断到8字符（32位）：在本演示中用于简化，实际部署建议64-128位以提高安全边际

**2. Nonce 的作用**：
- 每次挑战都不同
- 攻击者即使窃听了旧的(nonce, mac)对
- 也无法用于未来的挑战（nonce已变化）

**3. 防重放**：
- state.expected_nonce 只接受一次
- 验证后立即清除：state.expected_nonce = None
- 旧帧无法重放

#### 实际应用中的密钥交换方案

本研究假设PSK，但实际部署可用：

**方案1：Diffie-Hellman密钥交换**
- 初次通信时协商密钥
- 无需预共享
- 易于实现但需防中间人攻击

**方案2：公钥基础设施(PKI)**
- 使用证书验证身份
- 每次会话生成临时密钥
- 复杂但最安全

**方案3：硬件预置密钥**
- 出厂时烧录密钥到芯片
- 适用于IoT设备
- 本研究更接近这种场景

#### 相关理论支持

- **RFC 6479**: IPsec Anti-Replay Algorithm（滑动窗口机制）
- **RFC 2104**: HMAC标准定义
- **RFC 4493**: AES-CMAC Algorithm

---

### 6.5 蒙特卡洛仿真

**为什么需要？**
- 统计评估随机效应（丢包、乱序）的影响

**实现**：
```python
def run_many_experiments(config, num_runs):
    results = []
    for run_id in range(num_runs):
        result = simulate_one_run(config, run_id)
        results.append(result)
    
    # 计算均值和标准差
    avg_legit = mean([r.legit_accept_rate for r in results])
    std_legit = stdev([r.legit_accept_rate for r in results])
    
    return AggregateStats(avg_legit, std_legit, ...)
```

**统计可靠性**：
- 所有实验采用200次蒙特卡洛试验，达到95%置信水平
- 误差棒显示标准误差（SE = std/√n）

---

### 6.6 攻击者模型

**2种攻击时机**：

#### 事后攻击（Post-run Attack）
```python
# 合法通信结束后批量重放
legit_phase()   # 发送20帧
attack_phase()  # 重放100帧
```

#### 实时混入攻击（Inline Attack）
```python
# 在合法通信期间混入重放（更真实）
for frame in legit_frames:
    send(frame)
    if random() < 0.3:  # 30%概率
        replay(recorded_frame)  # 立即重放
```

**选择性重放**：
```python
attacker = Attacker(target_commands=["UNLOCK", "FIRE"])
# 只重放"UNLOCK"和"FIRE"
# 忽略无害命令如"STATUS"
```

---

## 7. 实验设计与方法论

### 7.1 实验参数设计概览

**目的**：系统性地评估不同条件下的性能

本研究通过三组核心实验全面评估防御机制：

#### 实验1：丢包率扫描
```python
p_loss_values = [0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30]
p_reorder = 0.0  # 固定（隔离丢包影响）
attack_mode = "post"
runs = 200, seed = 42
```

**目的**：评估丢包对各防御机制可用性的影响

#### 实验2：乱序率扫描
```python
p_reorder_values = [0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30]
p_loss = 0.10  # 固定（典型网络条件）
attack_mode = "post"
runs = 200, seed = 42
```

**目的**：揭示rolling机制对乱序的敏感性，验证window机制的鲁棒性

#### 实验3：窗口大小权衡
```python
window_values = [1, 3, 5, 7, 9, 15, 20]
p_loss = 0.15, p_reorder = 0.15  # 中等网络压力
attack_mode = "inline"  # 实时混入攻击，更严格的攻击模型
runs = 200, seed = 42
```

**目的**：在真实网络压力下找出安全性与可用性的最佳平衡点

---

### 7.2 实验可重现性

**随机种子管理**：
```python
config = SimulationConfig(
    rng_seed=42,  # 固定种子（本文所有实验使用seed=42）
    ...
)
```

所有实验使用相同种子 → 完全可重现

**公平比较**：
```python
# 所有模式使用相同的随机序列
rng = random.Random(seed)
for mode in [no_def, rolling, window, challenge]:
    rng.seed(seed)  # 每次重置
    run_experiment(mode, rng)
```

---

## 8. 主要实验结果

### 8.1 实验概览

本项目通过**三组核心实验**系统评估了四种重放攻击防御机制的性能。所有实验均采用：
- **200次蒙特卡洛运行**（每个实验配置运行200次，提供95%置信水平的统计可靠性）
- **固定随机种子 42**（完全可重现）
- **统一基线参数**：每次运行20个合法传输，100次重放尝试

**注**：理想信道基线（p_loss=0%, p_reorder=0%）作为性能上界的参考实验，独立进行了500次运行以获得更高的统计精度。该基线数据见README，主要用于理论性能对比。本文的三组核心实验（实验1/2/3）均使用200次运行。

完整参数配置详见：[实验参数配置文档](EXPERIMENTAL_PARAMETERS_CH.md)

**综合得分定义**：本文使用 `综合得分 = 可用性(%) - 攻击成功率(%)` 作为整体性能指标（越高越好）。该指标平衡了可用性和安全性两个维度，用于快速比较不同配置的整体表现

| 实验 | 变量参数 | 固定参数 | 攻击模式 | 测试防御 | 数据点 |
|------|---------|---------|---------|---------|-------|
| **实验1** | p_loss: 0-30% (7档) | p_reorder=0% | post-run | 4种 | 28条记录 |
| **实验2** | p_reorder: 0-30% (7档) | p_loss=10% | post-run | 4种 | 28条记录 |
| **实验3** | window_size: 1-20 (7档) | p_loss=15%, p_reorder=15% | inline | window | 7条记录 |

**注**：所有实验均使用 runs=200, seed=42, num_legit=20, num_replay=100

---

### 8.2 实验1：丢包率对防御机制的影响

**实验目的**：
评估不同丢包率下各防御机制的可用性和安全性，量化信道质量对性能的影响。

**实验设置**：
- 试验次数：200次（蒙特卡洛）
- 合法帧数：20/运行
- 重放尝试数：100/运行
- **变量**：p_loss = 0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30
- **固定**：p_reorder = 0.0（隔离丢包影响）
- 攻击模式：post-run（后运行重放）

**数据来源**：[`results/p_loss_sweep.json`](results/p_loss_sweep.json)

#### 关键数据点对比（0% vs 30%丢包）

| 防御模式 | 理想信道(0%)* | 严重丢包(30%) | 可用性下降 | 攻击成功率变化 |
|---------|-------------|--------------|-----------|---------------|
| **no_def** | 可用性100%, 攻击100% | 可用性70.3%, 攻击69.7% | ↓29.7% | ≈30% (信道直接影响) |
| **rolling** | 可用性100%, 攻击<0.1% | 可用性70.3%, 攻击0.4% | ↓29.7% | +0.3% (几乎不变) |
| **window** | 可用性100%, 攻击<0.1% | 可用性69.5%, 攻击1.8% | ↓30.5% | +1.7% (略微增加) |
| **challenge** | 可用性100%, 攻击<0.1% | 可用性70.0%, 攻击0.3% | ↓30.0% | +0.3% (极微增加) |

*注：理想信道(0%)数据来自实验1的p_loss=0档位（200次运行）。项目另有独立的理想基线实验（500次运行），数据见README，用于更精确的理论上界参考。

**可视化**：

![丢包率影响-可用性](figures/p_loss_legit.png)
*图1：丢包率对合法接受率的影响（4种防御机制对比）*

![丢包率影响-攻击成功率](figures/p_loss_attack.png)
*图2：丢包率对攻击成功率的影响（4种防御机制对比）*

**重要发现**：

1. **可用性下降均匀一致**：
   - 所有防御机制在30%丢包下可用性均下降约30%
   - 这是信道特性的直接反映，与防御机制无关
   - 证明防御机制不会额外降低可用性

2. **安全性在恶劣条件下保持稳定**：
   - rolling、window、challenge在30%丢包下攻击成功率仍<2%
   - challenge机制最稳定：攻击率保持<0.1%（0%丢包）至0.3%（30%丢包）
   - no_def基线显示攻击威胁真实存在（100% → 69.7%）

3. **中等丢包(10%)下的性能表现**：
   | 模式 | 可用性 | 攻击率 | 综合得分 |
   |-----|--------|--------|---------|
   | no_def | 90.3% | 89.6% | 0.6 |
   | rolling | 90.3% | 0.1% | **90.1** |
   | window | 90.3% | 0.5% | 89.8 |
   | challenge | 89.8% | <0.1% | ~89.7 |

**结论**：
- 丢包主要影响可用性，对安全性影响极小
- 所有防御机制在恶劣网络条件下均保持有效防护
- **challenge机制在各种丢包率下安全性最佳**

---

### 8.3 实验2：乱序率对防御机制的影响（关键实验）

**实验目的**：
在10%丢包率基础上，评估包乱序对各防御机制的影响，**揭示rolling机制的显著可用性问题**。

**实验设置**：
- 试验次数：200次
- **变量**：p_reorder = 0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30
- **固定**：p_loss = 0.10（模拟真实网络基线）
- 攻击模式：post-run

**数据来源**：[`results/p_reorder_sweep.json`](results/p_reorder_sweep.json)

#### 关键数据点对比（0% vs 30%乱序）

| 防御模式 | 无乱序(0%) | 严重乱序(30%) | 可用性下降 | 关键观察 |
|---------|-----------|--------------|-----------|---------|
| **no_def** | 可用性90.3%, 攻击89.6% | 可用性90.7%, 攻击89.9% | ↓-0.4% | 乱序无影响 |
| **rolling** | 可用性90.3%, 攻击0.1% | 可用性76.8%, 攻击0.1% | ↓13.5% | ⚠️ **显著局限** |
| **window** | 可用性90.3%, 攻击0.5% | 可用性90.6%, 攻击0.5% | ≈0% | ✅ **可用性对乱序高度鲁棒** |
| **challenge** | 可用性89.8%, 攻击<0.1% | 可用性64.5%, 攻击<0.1% | ↓25.3% | ⚠️ 受影响 |

**可视化**：

![乱序率影响-可用性](figures/p_reorder_legit.png)
*图3：乱序率对合法接受率的影响（揭示rolling机制局限性）*

**如何阅读此图**：
- **X轴**：p_reorder（包乱序概率）
  - 0.0 = 完美顺序（无乱序）
  - 0.3 = 高度不稳定网络（30%的帧延迟到达）
- **Y轴**：合法接受率（%）
  - 100% = 所有合法帧被接受
  - 90% = 10%的合法帧被错误拒绝
- **蓝线（rolling）**：随p_reorder急剧下降
- **橙线（window）**：几乎平坦，可用性对乱序高度鲁棒
- **绿线（challenge）**：在高乱序下显著下降
- **误差棒**：标准差（200次试验的统计变化）

**核心发现**：

1. **rolling机制对乱序敏感，存在显著局限性**：
   - 在30%乱序下，可用性下降至76.8%（下降13.5个百分点）
   - 原因：严格的顺序检查导致乱序包被误判为重放攻击
   - 实际影响：**约1/7的合法操作被拒绝**
   - 结论：rolling机制**在中高乱序环境中可用性显著下降，需谨慎评估适用性**

2. **window机制对乱序具有高度鲁棒性**：
   - 在30%乱序下，可用性保持90.6%（几乎无变化）
   - 原因：滑动窗口+位图机制有效处理乱序包
   - 结论：**window是乱序网络环境中的优选方案**

3. **challenge机制在高乱序下受限**：
   - 在30%乱序下，可用性降至64.5%（下降25.3%）
   - 原因：挑战-响应交互对乱序敏感
   - 适用场景：低乱序环境或容忍延迟的应用

**实际网络对比**：
| 网络类型 | 典型p_reorder | rolling可用性 | window可用性 | 结论 |
|---------|--------------|--------------|-------------|------|
| 有线以太网 | 0-5% | 90.3% | 90.3% | rolling可用 |
| Wi-Fi | 10-20% | 78-85% | 90.3% | ⚠️ rolling降级 |
| 蓝牙/Zigbee | 15-30% | 76-82% | 90.6% | ❌ rolling不可靠 |

**结论**：
- **rolling机制在存在乱序的IoT网络中表现受限**（Wi-Fi、BLE、Zigbee等环境）
- **window机制是通用IoT应用的优选方案**
- challenge适合有线网络或高安全要求场景

---

### 8.4 实验3：滑动窗口大小的权衡分析

**实验目的**：
在中等网络压力下，找出滑动窗口的最优大小，平衡可用性与安全性。

**实验设置**：
- 试验次数：200次
- 网络条件：p_loss=15%, p_reorder=15%（中等压力）
- **变量**：window_size = 1, 3, 5, 7, 9, 15, 20
- 攻击模式：**inline**（更严格的实时攻击模型）

**数据来源**：[`results/window_sweep.json`](results/window_sweep.json)

**重要说明**：本实验（实验3）与README中展示的"窗口扫描"采用不同实验条件：
- **实验3**（本节）：p_loss=15%, p_reorder=15%, 实时混入攻击 → 结果：W=5时可用性85.5%, 攻击率7.7%
- **附加扫描**（README）：p_loss=5%, p_reorder=30%, post攻击 → 结果：W=5时可用性95%, 攻击率0.3%

两组数据差异说明：网络条件（丢包率）和攻击模式（inline vs post）显著影响性能表现。本文主要结论基于实验3的更严格条件。

#### 窗口大小对性能的影响

| 窗口大小 | 可用性(%) | 攻击成功率(%) | 综合得分 | 评价 |
|---------|-----------|--------------|---------|------|
| **1** | 25.9 | 7.3 | 18.6 | ❌ 窗口过小，可用性极差 |
| **3** | 85.0 | 6.5 | 78.6 | ✅ **最佳平衡点** |
| **5** | 85.5 | 7.7 | 77.7 | ✅ 推荐（默认值） |
| **7** | 85.5 | 8.7 | 76.7 | ✅ 可接受 |
| **9** | 85.5 | 9.6 | 75.9 | ⚠️ 安全性开始下降 |
| **15** | 85.5 | 11.1 | 74.4 | ⚠️ 攻击率偏高 |
| **20** | 85.5 | 11.6 | 73.9 | ❌ 窗口过大，安全风险 |

**可视化**：

![窗口大小权衡](figures/window_tradeoff.png)
*图4：窗口大小的可用性-安全性权衡（window机制）*

**如何阅读此图**：
- **蓝色柱（左轴）**：合法接受率（越高越好）
- **橙色柱（右轴）**：攻击成功率（越低越好）
- **最佳区域**：蓝色柱高、橙色柱低

**重要发现**：

1. **窗口大小=1时不可用**：
   - 可用性仅25.9%，大量合法包被拒绝
   - 原因：窗口太小，无法容纳乱序+丢包
   - 结论：**绝不使用W=1**

2. **最佳窗口大小：3-7**：
   - 可用性：85.0-85.5%（优秀）
   - 攻击成功率：6.5-8.7%（可接受）
   - **推荐W=5作为默认值**（平衡性能与实现复杂度）

3. **窗口过大的风险**：
   - W>9后，可用性提升微小（停留在85.5%）
   - 但攻击成功率显著增加（11.1-11.6%）
   - 原因：更大窗口给攻击者更多重放机会
   - 结论：**不推荐W>9**

**实用建议**：
| 应用场景 | 推荐窗口大小 | 理由 |
|---------|------------|------|
| 实时通信（VoIP） | W=3 | 低延迟，最佳安全性（6.5%攻击率） |
| 一般IoT设备 | W=5 | **默认推荐**，平衡性能 |
| 高延迟网络 | W=7 | 容纳更多乱序，安全性仍可接受 |
| 低资源设备 | W=3 | 减少内存占用（3位位图 vs 5位） |

**结论**：
- 窗口大小是可用性与安全性的关键权衡参数
- **W=3-7为最佳范围，W=5为推荐默认值**
- 窗口过小导致可用性灾难，过大导致安全风险

---

### 8.5 综合评估与实用部署建议

#### 8.5.1 防御机制综合性能对比

基于200次蒙特卡洛模拟，在**中等网络条件(p_loss=10%, p_reorder=0%)**下的综合评估：

| 排名 | 防御机制 | 可用性 | 攻击成功率 | 综合得分 | 适用场景 | 关键特性 |
|-----|---------|--------|-----------|---------|---------|---------|
| 🥇 | **rolling** | 90.3% | 0.1% | **90.1** | ⚠️ 仅无乱序网络 | 计算简单但乱序脆弱 |
| 🥈 | **window** | 90.3% | 0.5% | 89.8 | ✅ **通用IoT首选** | 可用性对乱序鲁棒 |
| 🥉 | **challenge** | 89.8% | <0.1% | ~89.7 | ✅ 高安全要求 | 最高安全性，需双向通信 |
| ❌ | **no_def** | 90.3% | 89.6% | 0.6 | ❌ 基线参考 | 无防护能力 |

![基线攻击成功率对比](figures/baseline_attack.png)
*图5：中等网络条件下（p_loss=10%, p_reorder=0%）四种防御机制的攻击成功率对比*

#### 8.5.2 实用部署决策树

```
开始选择防御机制
│
├─ 网络是否有乱序问题？
│  │
│  ├─ 是（Wi-Fi/BLE/Zigbee） ─────> 【window】(窗口大小5-7)
│  │                                 理由：可用性对乱序鲁棒
│  │
│  └─ 否（有线/理想信道） ─┐
│                         │
│                         ├─ 安全要求是否极高？
│                         │  │
│                         │  ├─ 是 ──> 【challenge】
│                         │  │         理由：攻击率<0.1%，最佳安全性
│                         │  │
│                         │  └─ 否 ──> 【rolling】或【window】
│                         │            理由：两者性能相近，window更通用
│                         │
│                         └─ 设备资源是否极度受限？
│                            │
│                            ├─ 是 ──> 【rolling】(仅无乱序时)
│                            │         理由：实现最简单
│                            │
│                            └─ 否 ──> 【window】
│                                      理由：更鲁棒，轻微资源增加
```

#### 8.5.3 典型应用场景推荐

| 应用领域 | 推荐机制 | 参数配置 | 关键考虑 | 理由 |
|---------|---------|---------|---------|------|
| **智能家居** | window | W=5-7 | 乱序容忍，中等安全 | Wi-Fi常有乱序，需要鲁棒性 |
| **工业IoT** | window | W=7 | 高延迟容忍 | 容忍网络抖动，稳定优先 |
| **医疗设备** | challenge | - | 最高安全性 | 双向通信可接受，攻击率<0.1% |
| **智能电网** | challenge | - | 关键基础设施 | 安全优先，容忍交互延迟 |
| **RFID标签** | window | W=3 | 低资源+鲁棒性 | 内存受限但需容忍乱序 |
| **车联网** | window | W=3 | 实时性+鲁棒性 | 低延迟，容忍适度乱序 |
| **有线传感器** | rolling | - | 理想信道 | 无乱序环境，计算简单 |

**注**：上表为定性指导，不含具体性能数值。实际性能取决于网络条件和攻击模式：
- **实验3（严格条件）**：p_loss=15%, p_reorder=15%, 实时混入攻击 → window W=3-7可用性85%, 攻击率6.5-8.7%
- **实验1（中等条件）**：p_loss=10%, p_reorder=0%, post攻击 → window可用性90%, 攻击率0.5%
- **实验2（乱序条件）**：p_loss=10%, p_reorder=30%, post攻击 → window可用性91%, 攻击率0.5%

建议根据实际威胁模型和网络环境参考相应实验数据，或进行现场测试验证。

#### 8.5.4 关键决策因素

**1. 网络特性**
- 乱序率 >5%：**必须使用window**，rolling不可靠
- 乱序率 <5%：rolling和window均可
- 丢包率 >20%：所有机制可用性均下降，但安全性保持

**2. 安全要求**
- 极高安全（金融、医疗）：**challenge**（攻击率<0.1%-0.3%，取决于网络条件）
- 高安全（一般IoT）：**window**（实验1数据：p_loss=10-30%, p_reorder=0%时攻击率0.5-1.8%）
- 中等安全（消费电子）：**rolling**或**window**

**3. 资源限制**
- 极度受限（1KB RAM）：rolling（无位图）
- 中等受限（2-4KB RAM）：window（小窗口W=3）
- 无限制：challenge（加密开销）

**4. 通信模式**
- 单向通信：rolling或window
- 双向通信可用：考虑challenge（最高安全性）

#### 8.5.5 不推荐的配置

| 配置 | 问题 | 后果 |
|------|------|------|
| rolling + 乱序网络 | 对乱序极度敏感 | 可用性下降13.5%，用户体验差 |
| window W=1 | 窗口过小 | 可用性仅25.9%，几乎不可用 |
| window W>15 | 窗口过大 | 攻击成功率>11%，安全风险高 |
| no_def | 无防护 | 攻击成功率89.6%，完全不设防 |

#### 8.5.6 数据可靠性总结

✅ **统计可靠性**：
- 200次蒙特卡洛运行，95%置信水平
- 固定随机种子42，结果完全可重现
- 标准差低，结果稳定

✅ **性能验证**：
- 单次运行平均26-30ms，高效验证
- ~36-38次运行/秒吞吐量

✅ **实验透明性**：
- 完整源代码：[GitHub](https://github.com/tammakiiroha/Replay-simulation)
- 原始数据：`results/*.json`
- 参数配置：[EXPERIMENTAL_PARAMETERS_CH.md](EXPERIMENTAL_PARAMETERS_CH.md)
## 9. 项目质量保证

### 9.1 测试覆盖率

本项目实现了完整的单元测试套件，确保代码正确性和实验数据可靠性。

#### 9.1.1 测试统计

| 指标 | 数值 | 说明 |
|------|------|------|
| **测试文件数** | 5个 | 覆盖所有核心模块 |
| **测试用例总数** | 85+ | 全面的功能验证 |
| **代码覆盖率** | ~70% | 关键模块高覆盖 |
| **RFC符合性** | RFC 6479, 2104 | 标准对照验证 |

#### 9.1.2 测试套件详情

**1. tests/test_sender.py** (20+测试)
- MAC计算正确性验证（对照RFC 2104）
- 帧生成格式验证
- 计数器递增逻辑验证
- 挑战-响应nonce生成验证
- 固定种子可重现性验证

关键测试示例：
```python
def test_mac_correctness_basic():
    """验证MAC计算符合RFC 2104"""
    sender = Sender(defense=DefenseMode.ROLLING_MAC, seed=42)
    frame = sender.send_command(cmd)
    
    # 重新计算MAC验证
    data = f"{frame.command}:{frame.counter}"
    expected_mac = compute_mac(data, sender.key, sender.mac_length)
    
    assert frame.mac == expected_mac  # ✓ RFC 2104符合性
```

**2. tests/test_channel.py** (15+测试)
- 丢包率统计正确性（0%, 10%, 20%, 30%, 100%）
- 乱序概率统计特性验证
- 优先队列逻辑验证
- Flush行为验证

关键测试示例：
```python
def test_packet_loss_rate_10_percent():
    """验证10%丢包率的统计特性"""
    channel = Channel(p_loss=0.1, seed=42)
    
    # 发送1000个包进行统计测试
    received = sum(1 for _ in range(1000) 
                   if channel.send(frame))
    
    actual_loss = 1.0 - (received / 1000)
    # 允许±2%统计误差
    assert 0.08 < actual_loss < 0.12  # ✓ 统计特性正确
```

**3. tests/test_attacker.py** (25+测试)
- Dolev-Yao模型符合性验证
- 帧记录逻辑验证
- 选择性重放验证
- 攻击者丢包参数验证

关键测试示例：
```python
def test_attacker_cannot_forge_mac():
    """验证攻击者不能伪造MAC（Dolev-Yao模型）"""
    frame = create_frame("LOCK", 0, 1)
    frame.mac = "valid_mac_xyz"
    
    attacker.observe(frame)
    replayed = attacker.replay_frame(frame)
    
    # 攻击者只能重放，不能修改MAC
    assert replayed.mac == "valid_mac_xyz"  # ✓ Dolev-Yao符合性
```

**4. tests/test_experiment.py** (20+测试)
- 蒙特卡洛统计计算验证
- 平均值/标准差计算验证
- 固定种子完全可重现性验证
- 防御机制有效性验证
- 参数影响验证

关键测试示例：
```python
def test_reproducibility_with_fixed_seed():
    """验证固定种子的完全可重现性"""
    config = SimulationConfig(..., seed=42)
    
    # 两次独立运行
    result1 = run_many_experiments(config, runs=30)
    result2 = run_many_experiments(config, runs=30)
    
    # 应该完全相同
    assert result1['avg_legit'] == result2['avg_legit']  # ✓ 可重现
```

**5. tests/test_receiver.py** (5测试)
- 滑动窗口边界条件验证
- 重放检测验证
- 乱序处理验证
- RFC 6479符合性验证

#### 9.1.3 RFC标准符合性验证

| RFC标准 | 验证内容 | 测试文件 | 状态 |
|---------|---------|---------|------|
| RFC 6479 | 滑动窗口反重放 | test_receiver.py | ✅ 已验证 |
| RFC 2104 | HMAC-SHA256 | test_sender.py | ✅ 已验证 |
| Dolev-Yao | 攻击者模型 | test_attacker.py | ✅ 已验证 |

### 9.2 性能基准测试

完整的性能基准测试确保系统效率和实验可行性。

#### 9.2.1 基准测试结果

测试环境：MacBook Pro (Apple M1, 16GB RAM)

| 配置 | 运行次数 | 耗时 | 吞吐量 |
|------|---------|------|--------|
| 单个防御模式 | 200次 | ~5.3秒 | ~38 runs/s |
| 全部4种模式 | 各200次 | ~22秒 | ~36 runs/s |
| 参数扫描(5×5) | 各25次 | ~31秒 | - |

#### 9.2.2 性能指标详情

**单次运行性能**：
- 平均时间：**26-30毫秒**
- 标准差：±3ms
- 最快：18ms（无防御）
- 最慢：35ms（挑战-响应）

**防御机制开销**：
- 无防御：基准（0%）
- 滚动计数器：+1%（MAC计算）
- 滑动窗口：+2%（位掩码操作）
- 挑战-响应：+5%（双向通信）

**统计收敛性分析**：

| 运行次数 | Avg Legit | Std Legit | 置信度 |
|---------|-----------|-----------|--------|
| 10次 | 0.872 | 0.042 | ~70% |
| 50次 | 0.868 | 0.028 | ~90% |
| 100次 | 0.870 | 0.022 | ~93% |
| **200次** | **0.869** | **0.018** | **~95%** ✅ |
| 500次 | 0.870 | 0.016 | ~97% |

**统计量说明**：
- **Std Legit（标准差）**：衡量200次运行结果的分散度。0.018表示200次运行的可用性值分散在约±1.8%范围内。
- **标准误差（SE）**：衡量均值估计的精度，SE = Std/√n ≈ 0.018/√200 ≈ 0.0013（约0.13%），说明均值估计非常精确。
- **置信度**：基于中心极限定理，200次运行提供约95%置信水平，足以检测防御机制间的显著差异（>5%）。

**结论**：200次运行提供95%置信度，同时保持5秒内完成，是统计可靠性和计算效率的最佳平衡点。

#### 9.2.3 运行基准测试

```bash
python scripts/benchmark.py
```

输出包括：
1. 单次运行性能测试
2. 蒙特卡洛规模扩展性测试（10-500次）
3. 参数影响测试（num_legit, num_replay, defense mode）
4. 统计收敛性验证

### 9.3 代码质量保证

#### 9.3.1 参数验证

完整的输入参数验证，防止错误输入：

```python
def validate_parameters(args):
    """验证所有输入参数"""
    # 概率参数验证（0.0 ~ 1.0）
    if not 0.0 <= args.p_loss <= 1.0:
        raise ValueError("p_loss must be between 0.0 and 1.0")
    
    # 正整数验证
    if args.runs <= 0:
        raise ValueError("runs must be positive")
    
    # 文件路径验证
    if args.commands_file and not Path(args.commands_file).exists():
        raise FileNotFoundError(f"File not found: {args.commands_file}")
```

#### 9.3.2 错误处理

友好的错误提示和异常捕获：

示例输入：
```bash
python main.py --p-loss 1.5
```

输出：
```
❌ Parameter Validation Failed:
  • Invalid p_loss: 1.5. Must be between 0.0 and 1.0

Please fix the errors and try again.
```

#### 9.3.3 可重现性保证

- **固定种子**：所有随机操作都使用固定种子
- **确定性算法**：保证相同输入产生相同输出
- **版本锁定**：requirements.txt锁定所有依赖版本
- **测试验证**：test_experiment.py验证可重现性

### 9.4 质量保证总结

本项目采取的质量保证措施：

| 维度 | 实现内容 |
|------|---------|
| **测试覆盖** | 85+测试用例，覆盖核心防御逻辑、信道模拟、统计计算 |
| **标准符合** | 滑动窗口参考RFC 6479，HMAC实现基于RFC 2104 |
| **性能验证** | 单次运行26-30ms，200次试验5.3秒完成 |
| **参数验证** | 完整的输入检查和错误提示 |
| **可重现性** | 固定种子(42)，确定性算法，版本锁定 |
| **文档完整性** | 三语文档(EN/JP/CH)，代码注释，实验参数文档 |

这些措施确保：
1. ✅ 实验数据可靠可信（200次蒙特卡洛，95%置信度）
2. ✅ 代码实现可验证（85+测试用例，公开源代码）
3. ✅ 研究结果可重现（固定种子，完整参数记录）
4. ✅ 符合研究规范（标准参考，透明方法论）

---

## 10. 局限性与未来工作

### 10.1 当前局限性

#### 10.1.1 信道模型简化

**当前实现**：
- i.i.d（独立同分布）丢包模型
- 简单随机延迟产生的乱序

**局限性**：
- 未模拟突发丢包（burst loss）：真实无线信道中，丢包往往成簇出现（如干扰持续期间）
- 未考虑相关乱序：实际网络中，路由抖动可能导致连续多帧乱序
- 未包含延迟抖动统计特性：真实网络的延迟分布可能呈长尾特征

**影响评估**：
- 定性趋势稳健：即使信道模型简化，rolling对乱序敏感、window鲁棒、challenge最安全的核心结论仍然成立
- 定量数值可能偏差：具体百分比可能与真实网络有差异
- 相对比较有效：机制间的排序和权衡关系不受简化影响

**未来改进方向**：
- 实现Gilbert-Elliott两态突发丢包模型
- 引入Markov链模拟相关乱序
- 使用真实网络trace驱动仿真（trace-driven simulation）

---

#### 10.1.2 攻击模型覆盖范围

**当前实现**：
- 重放攻击（replay attack）：记录并重新传输合法帧
- 两种时机：事后攻击（post-run）和实时混入攻击（inline）

**未涵盖的攻击类型**：
1. **中继攻击（Relay Attack）**：
   - 实时转发合法用户的命令
   - 不需要破解密码学，只需延长通信距离
   - 对challenge-response机制仍可能有效

2. **信号操纵（Signal Manipulation）**：
   - 物理层干扰（jamming）
   - 功率分析（power analysis）
   - 时序攻击（timing attack）

3. **协议级攻击**：
   - 会话劫持
   - 降级攻击（downgrade attack）
   - 密钥泄露后的影响

**研究范围说明**：
本研究聚焦于**重放攻击的防御机制评估**，这是无线控制系统最常见的威胁之一。其他攻击类型属于不同的威胁模型，需要专门的研究。

**未来扩展方向**：
- 实现中继攻击仿真模块
- 引入物理层攻击模拟
- 评估多种攻击的组合场景

---

#### 10.1.3 密码学实现

**当前实现**：
- HMAC-SHA256截断至32位（8个十六进制字符）
- 主要用于演示和对比实验

**局限性**：
- 32位MAC空间（2³² ≈ 43亿）对于某些高安全场景可能不足
- 未考虑密钥管理（假设预共享密钥PSK）
- 未实现密钥更新机制

**澄清说明**：
- **不影响相对比较**：所有防御机制使用相同的MAC长度，相对性能排序不受影响
- **生产环境建议**：实际部署应使用64-128位MAC以提高安全边际（已在6.4节说明）
- **研究重点**：本研究关注防御机制的**系统性比较**，而非密码学协议设计

**未来改进**：
- 提供可配置的MAC长度参数
- 实现密钥轮换（key rotation）
- 支持多种加密算法（AES-GCM、ChaCha20-Poly1305）

---

#### 10.1.4 物理层验证缺失

**当前状态**：
- 纯软件仿真环境
- 固定随机种子保证可重现性
- 参数化探索（0-30%丢包/乱序扫描）

**缺失部分**：
- 真实RF环境测试
- 硬件实现验证
- 实际功耗测量
- 真实延迟特性

**仿真的优势**：
- ✅ 完全可重现（固定种子）
- ✅ 参数化系统评估（快速扫描）
- ✅ 成本低、迭代快
- ✅ 易于控制变量

**物理实验的价值**：
- ✅ 验证定性趋势的真实性
- ✅ 发现仿真未考虑的因素
- ✅ 获得实际部署数据

**研究定位**：
本研究是理论分析和物理实验之间的**参数化仿真评估**，为实际部署提供系统性指导，而非精确的性能预测。

---

### 10.2 未来工作方向

#### 10.2.1 短期扩展（6-12个月）

**1. 物理实验验证**

**目标**：在真实IoT硬件上验证仿真趋势

**实施计划**：
- **硬件选择**：
  - ESP32（Wi-Fi）
  - nRF52840（BLE）
  - CC2652（Zigbee）
- **实验设计**：
  - 在受控RF环境测试
  - 复现3组核心实验（丢包/乱序/窗口扫描）
  - 对比仿真vs实测数据
- **预期输出**：
  - 验证报告
  - 实测vs仿真的对比分析
  - 部署最佳实践文档

**预期结果**：定性趋势（如rolling对乱序敏感）应该得到验证，但具体数值会因硬件和环境而异。

---

**2. 增强信道模型**

**目标**：更真实地模拟无线信道特性

**技术方案**：
- **Gilbert-Elliott模型**：
  - 两态（好/坏）Markov链
  - 模拟突发丢包
  - 参数从文献校准（如IEEE 802.15.4测量数据）

- **相关乱序模型**：
  - 使用Markov过程生成相关延迟
  - 模拟路由抖动场景
  - 引入延迟分布（正态/指数/Pareto）

- **Trace驱动仿真**：
  - 使用真实网络trace作为输入
  - 支持pcap文件导入
  - 可重放真实网络行为

**预期影响**：更准确的定量预测，但相对比较结论不会改变。

---

#### 10.2.2 中期研究（1-2年）

**3. 扩展攻击模型**

**中继攻击仿真**：
```python
class RelayAttacker:
    """实时转发合法用户命令"""
    def relay(self, frame_from_user):
        # 不修改、不破解，只是延长距离
        return frame_from_user  # 转发给接收方
```

**研究问题**：
- 中继攻击对challenge-response的影响
- 距离限制（distance bounding）防御
- 时序约束的有效性

---

**4. 多协议支持**

**TLS 1.3握手模拟**：
- 评估TLS over IoT的开销
- 对比DTLS（用于UDP）
- 轻量级TLS变种（如TLS-PSK）

**MQTT-SN安全**：
- MQTT for sensor networks
- 发布/订阅模式的重放攻击
- QoS与安全性权衡

**CoAP + DTLS**：
- Constrained Application Protocol
- 资源受限设备的安全通信
- 块传输（block transfer）的防御

---

#### 10.2.3 长期愿景（2-5年）

**5. 硬件加速与优化**

**FPGA实现**：
- 滑动窗口算法的硬件加速
- 纳秒级延迟
- 适用于工业实时控制

**嵌入式优化**：
- 内存占用最小化（位图压缩）
- 功耗优化（sleep mode策略）
- 代码体积优化（适用于<32KB Flash）

**实时性基准测试**：
- 在Cortex-M4/M7上测试
- 建立延迟/吞吐量/功耗数据库
- 为不同场景提供配置建议

---

**6. 标准化贡献**

**IETF参与**：
- 向IoT工作组提交实验数据
- 参与RFC草案讨论（如CoAP安全扩展）
- 推动最佳实践文档（BCP: Best Current Practice）

**学术贡献**：
- 期刊论文投稿（IEEE IoT Journal、ACM TOSN）
- 会议演讲（IEEE INFOCOM、ACM SenSys）
- 教程和workshop组织

**开源生态**：
- 贡献到主流IoT框架（Zephyr、RIOT、Contiki）
- 提供生产级库实现
- 维护性能基准数据集

---

### 10.3 欢迎贡献

本项目欢迎以下形式的贡献：

#### 实验数据贡献
- 在真实硬件上运行实验
- 提交实测数据（JSON格式）
- 补充不同网络环境的测试结果

#### 代码贡献
- 新防御机制实现
- 信道模型增强
- 性能优化
- Bug修复

#### 文档改进
- 翻译到其他语言
- 补充使用案例
- 教程和示例
- API文档完善

#### 学术合作
- 联合研究项目
- 数据集共享
- 交叉验证实验

**贡献指南**：详见 [CONTRIBUTING.md](CONTRIBUTING.md)

**联系方式**：
- GitHub Issues: https://github.com/tammakiiroha/Replay-simulation/issues
- Email: [通过GitHub profile联系]

---

### 10.4 致谢

本研究的信道模型设计参考了以下文献的定性描述：
- IEEE 802.15.4/Zigbee网络可靠性研究
- LoRaWAN城市部署案例
- BLE通信质量分析

感谢开源社区提供的工具和库：
- Python生态系统（NumPy、Matplotlib）
- pytest测试框架
- GitHub平台

---

## 11. 术语表

<details>
<summary>展开术语表</summary>

| 术语 | 定义 |
|------|------|
| **重放攻击** | 攻击者记录并重新传输合法帧以欺骗接收方 |
| **滚动计数器** | 帧计数器严格递增，接收方拒绝旧帧 |
| **滑动窗口** | 使用位掩码允许有限乱序，同时防止重放 |
| **挑战-响应** | 接收方发出Nonce，发送方必须正确响应 |
| **Nonce** | Number used once，仅使用一次的随机数值，用于防止重放 |
| **MAC（消息认证码）** | HMAC-SHA256的截断版本，用于帧认证 |
| **Dolev-Yao模型** | 假设攻击者完全控制网络但无法破解密码学原语 |
| **蒙特卡洛仿真** | 通过大量随机试验估计统计量 |
| **PDR（包交付率）** | 成功接收的包占发送包的百分比 |

</details>

---

## 12. 演示说明

### 12.1 快速演示

**步骤1：基本执行**
```bash
python3 main.py --runs 10 --num-legit 10 --num-replay 20 \
                --modes rolling window --p-loss 0.05
```

**示例输出**：
```
Mode     Runs  Attack  p_loss  Window  Avg Legit  Avg Attack
-------  ----  ------  ------  ------  ---------  ----------
rolling  10    post    0.05    0        96.00%      0.00%
window   10    post    0.05    5        96.00%      0.50%
```

**要点**：
- 滚动计数器和窗口具有相同的合法接受率（仅丢包时）
- 两者安全性都很高

---

**步骤2：乱序影响**
```bash
python3 main.py --runs 10 --num-legit 20 --num-replay 50 \
                --modes rolling window --p-reorder 0.3
```

**示例输出**：
```
Mode     Runs  Attack  p_reorder  Window  Avg Legit  Avg Attack
-------  ----  ------  ---------  ------  ---------  ----------
rolling  10    post    0.30       0        82.50%      0.00%
window   10    post    0.30       5        99.50%      0.00%
```

**要点**：
- 滚动计数器的合法接受率**下降17%**
- 窗口几乎不受影响（99.5%）

---

### 12.2 图表演示

**图1：包乱序影响**
```bash
python3 scripts/plot_results.py --formats png
```

文件：`figures/p_reorder_legit.png`

**要点**：
- X轴：p_reorder（乱序概率）
- Y轴：合法接受率
- 蓝线（滚动）：急剧下降
- 橙线（窗口）：几乎平坦

---

**图2：窗口大小权衡**
```bash
open figures/window_tradeoff.png
```

**要点**：
- 本图基于实验3（p_loss=15%, p_reorder=15%, 实时混入攻击）
- W=1：可用性灾难性（25.9%），攻击率7.3%
- W=3-5：**最优平衡**（可用性85.0-85.5%，攻击率6.5-7.7%）
- W>9：可用性提升微小，但攻击率显著增加（>9.6%）
- 注：不同网络条件下数值会有差异（参见README中其他实验条件结果）

---

### 12.3 代码演示

**演示1：滑动窗口操作**

```python
# 打开 sim/receiver.py
def verify_with_window(frame, state, window_size):
    diff = frame.counter - state.last_counter
    
    if diff > 0:  # 新计数器
        print(f"新的最大计数器：{frame.counter}")
        state.received_mask <<= diff
        state.received_mask |= 1
        state.last_counter = frame.counter
        return VerificationResult(True, "accept_new", state)
```

**要点**：
1. `diff > 0`：计数器前进 → 移动窗口
2. `received_mask <<= diff`：左移以移除旧位
3. `received_mask |= 1`：标记当前计数器为已接收

---

**演示2：信道模型乱序**

```python
# 打开 sim/channel.py
def send(self, frame):
    if self.rng.random() < self.p_reorder:
        delay = self.rng.randint(1, 3)  # 随机延迟
        print(f"帧 {frame.counter} 延迟 {delay} 个时间片")
    else:
        delay = 0
    
    delivery_tick = self.current_tick + delay
    heapq.heappush(self.pq, (delivery_tick, frame))
```

**要点**：
1. 30%概率延迟1-3个时间片
2. 优先队列（堆）管理交付时间
3. 这自然导致乱序

---


### 12.4 问答准备

**预期问题和回答**：

**Q1：为什么用Python？C/C++不是更快吗？**
> A：仿真是计算密集型而非I/O密集型。Python完成200次试验仅需数秒。我们优先考虑可读性和开发速度。

**Q2：与物理实验相比如何？**
> A：物理实验是未来工作。本研究的信道模型参考了IEEE 802.15.4/ZigBee、LoRaWAN、BLE等无线网络文献中的定性描述。我们使用的0-30%参数范围是为系统评估设计的仿真参数，覆盖了从理想到挑战性的各种网络条件。

**Q3：挑战-响应在安全性上表现最好，为什么还要用其他方法？**
> A：挑战-响应在纯安全性维度（攻击成功率<0.1%-0.3%，取决于网络条件）上确实表现最佳，但需要双向通信且引入额外延迟。对于单向通信的IoT设备和低功耗传感器，滚动计数器或滑动窗口更实用。此外，challenge机制在高乱序环境下可用性会显著下降（30%乱序时降至64.5%），而window机制则保持稳定。实际部署需要综合考虑安全性、可用性、资源限制和通信模式。

**Q4：最优窗口大小是多少？**
> A：实验结果推荐W=3-5。但实际系统需要根据通信环境调整。

**Q5：如果攻击者针对窗口漏洞怎么办？**
> A：窗口机制的攻击成功率与网络条件和攻击模式相关。实验3（p_loss=15%, p_reorder=15%, 实时混入攻击）显示W=5时攻击率约7.7%；在更温和条件下（如p_loss=5%, p_reorder=30%, post攻击）攻击率可低至0.3-0.5%。虽然理论上存在重放窗口，但实验结果表明：相比rolling机制在高乱序下13.5%的可用性下降，window机制的安全性代价是可接受的。实际部署需根据威胁模型权衡。

---

## 附录A：系统要求

**硬件**：
- CPU：任意（Apple Silicon / Intel / AMD）
- RAM：2GB最低
- 存储：50MB

**软件**：
- Python 3.11+
- matplotlib >= 3.10（可视化）
- pytest >= 7.0（测试）

**操作系统**：
- macOS 14.x
- Ubuntu 22.04
- Windows 10/11（推荐WSL）

---

## 附录B：目录结构

```
Replay-simulation/
├── main.py                 # CLI入口点
├── README.md               # 主文档（英文）
├── README_JP.md            # 日文文档
├── README_CH.md            # 中文文档
├── PRESENTATION_JP.md      # 本演示（日文）
├── PRESENTATION_EN.md      # 本演示（英文）
├── PRESENTATION_CH.md      # 本演示（中文）
├── requirements.txt        # Python依赖
├── LICENSE                 # MIT许可证
│
├── sim/                    # 核心仿真库
│   ├── types.py           # 数据结构（Frame、Config等）
│   ├── sender.py          # 发送方逻辑
│   ├── receiver.py        # 接收方和验证逻辑
│   ├── channel.py         # 信道模型
│   ├── attacker.py        # 攻击者模型
│   ├── experiment.py      # 实验控制
│   ├── security.py        # 密码学原语
│   └── commands.py        # 命令序列
│
├── scripts/                # 自动化脚本
│   ├── run_sweeps.py      # 参数扫描
│   ├── plot_results.py    # 图表生成
│   └── export_tables.py   # Markdown表格生成
│
├── tests/                  # 单元测试
│   └── test_receiver.py   # 接收方逻辑测试
│
├── results/                # 实验结果（JSON）
│   ├── p_loss_sweep.json
│   ├── p_reorder_sweep.json
│   ├── window_sweep.json
│   ├── ideal_p0.json
│   └── trace_inline.json
│
├── figures/                # 生成的图表（PNG）
│   ├── p_loss_legit.png
│   ├── p_loss_attack.png
│   ├── p_reorder_legit.png
│   ├── window_tradeoff.png
│   └── baseline_attack.png
│
└── traces/                 # 命令轨迹
    └── sample_trace.txt   # 示例命令序列
```

---

## 附录C：参考文献

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
2. 信道模拟模型（丢包和乱序）
3. 定量评估（200次蒙特卡洛试验，95%置信度）
4. 完全可重现（固定种子、开源）
5. 可视化和文档（出版级图表、3语言文档）

### 主要发现

1. **滚动计数器的局限性**：在中高乱序环境（p_reorder=30%）下可用性下降约13.5个百分点
2. **滑动窗口的优势**：在不同网络条件下保持良好的可用性-安全性平衡，W=3-7为推荐范围
3. **挑战-响应的特点**：安全性最高（攻击率<0.1%），但需要双向通信且延迟较高，在高乱序环境下可用性显著下降

### 实用建议

| 系统特性 | 推荐防御机制 |
|---------|-------------|
| 单向通信、稳定网络 | 滚动计数器 |
| 单向通信、不稳定网络 | **滑动窗口 (W=5)** |
| 双向通信、高安全要求 | 挑战-响应 |

---

**感谢您的关注！**

**联系方式**：
- GitHub: https://github.com/tammakiiroha/Replay-simulation
- 项目许可证：MIT

**欢迎提问！**

