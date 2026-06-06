# HSW-CR 完整协议实现 · 大改计划（代码追上研究计划规格）

> **For Claude:** 本文件是设计 + 实施主计划。执行实现时使用 `superpowers:executing-plans` 逐任务推进；需要把某个 Phase 展开成逐行 RED/GREEN TDD 任务时，使用 `superpowers:writing-plans` 对该 Phase 单独细化。

**Goal:** 把 `src/replay` 从“HSW-CR 的极简残影”升级为“研究计划里那个完整 HSW-CR 协议的忠实实现”，落地闭式数学模型，并产出论文所需的全部仿真验证证据。

**Architecture:** 双层。第 1 层 `core/` 是概率化、批量蒙特卡洛仿真引擎（求速度）；第 2 层 `protocol/` 是逐帧、确定性、带 wire format 的协议参考实现（求保真、可移植固件）。两层共用一个“单一真相核” `core/kernel/`（`WINDOW_COMMIT`、接受判定、MAC domain），从架构上保证“simulator 与 firmware 调用同一份判定逻辑”（研究计划 §8.6）。现有 6 个模式全部保留作 baseline。

**Tech Stack:** Python 3.9+（`from __future__ import annotations`）、Pydantic v2、FastAPI、pytest、ruff、mypy；Next.js/TypeScript（Web）；可选 `ascon`、`PyYAML`。

---

## 0. 元目标、受众与证据边界

### 0.1 元目标（按优先级）

1. **学术影响力（最主要）**：HSW-CR 作为论文的**核心科学贡献**，必须名副其实、有威胁模型、有闭式数学背书、有严格对比与消融。审稿人查 artifact 时，代码必须与论文设计一致。
2. **现实贡献（放大器）**：协议参考实现层贴近真实固件（ESP32 + nRF24L01+ / nRF52840 DK），可落地、可移植。
3. **可见度（放大器）**：完整、可复现的开源 benchmark + 交互式 Web Demo + 双重验证图。

目标受众优先级：**学术同行/审稿人（主）** > 开发者/安全社区 > 广泛受众/教学 > 工业/厂商。

### 0.2 研究计划是“宪法”

权威规格来源（只读，不在本仓修改）：

- `/Users/romeitou/Desktop/Github/Note/硕士计划/低价格IoT重放攻击与HSW-CR防御协议研究计划指导书.md`（导航）
- `…/HSW-CR研究计划指导书/01..08 + 10`（分章）
- `…/HSW-CR概念知识库/`（84 词条）

本计划只做**实现对齐 + 数学落地 + 验证产出**。若实现中发现研究计划本身的缺口（例如某公式与代码无法自洽），**回查研究计划并在本文件“§14 双向同步”记录待澄清项**，不擅自改变研究设计。

### 0.3 证据边界（写进论文，也写进代码 README）

> 目前所有量化结果来自 **synthetic Monte Carlo**，只能说明模型与程序在合成条件下自洽。真实 RF trace 与硬件验证是后续阶段（“数学建模 + 仿真跑完后再做真机”）。在拿到真实 trace 之前，不得声称结果接近真实无线环境。

### 0.4 与 2026-06-05 overhaul plan 的关系

`docs/plans/2026-06-05-replaybench-iot-overhaul.md`（v0.2.0 已落地）做的是“研究级基础设施”（P0 正确性、Wilson CI、GE 信道、成本指标、HSW-CR 雏形、presets/advisor/Web/CI）。本计划是**下一台阶**：把 HSW-CR 从雏形升级为完整协议。二者不冲突，本计划复用其统计/信道/契约基础设施。

---

## 1. 规格 vs 代码 差距分析（大改的根据地）

| # | 研究计划设计 | 代码现状（`src/replay`） | 等级 | 主要落点 |
|---|---|---|---|---|
| G1 | **W ≠ G_hard 分离**：W 向后乱序窗口（2~8），G_hard 向前跳容忍（可 50+），各按分位数取值 | 只有 `window_size`，**无 G_hard**，向前大跳跃无容忍上界 | 🔴 | Phase 1 |
| G2 | **Authenticated Resync 状态机**：6 步、RESYNC_PENDING、不执行原命令、封窗、epoch bump、TTL | **完全没有** | 🔴 | Phase 2 |
| G3 | **Critical 两阶段提交**：prepare→challenge→confirm→commit，pendingCritical 表 N_p 有界，原子 commit | challenge 是单阶段 issue→verify | 🔴 | Phase 3 |
| G4 | **发送端 PendingUserIntent 不变量**：单纯收到 challenge 不得 confirm（防 challenge 洗白重放） | 无发送端状态机 | 🔴（安全漏洞） | Phase 3 |
| G5 | **normal/critical 二分类 + Policy Table**：I(c)=max Hₖ，三触发线，O(1) 查表 | 连续 `risk>=0.8` 阈值，无 I(c)/Hₖ/policy table | 🟠（名实不符） | Phase 4 |
| G6 | **帧结构**：dev_id、key_id、epoch、ctr、cmd、payload、flags、N_R、tag，各字段定位长（ℓ_e=32, ℓ_ctr=48, ℓ_t=96, ℓ_N=96） | `Frame` 仅 command/counter/nonce/mac/is_attack | 🟠 | Phase 1 |
| G7 | **闭式数学模型**：a_W(r;p_ℓ)、LAR(W)=1−q_rᵂ、P_forge=q/2^{ℓ_t}、W\* 目标、P_compromise=1−(1−ASR)ᴺ | 仅经验统计，无解析模型，无“闭式 vs 仿真”对比 | 🔴（论文主线） | Phase 5 |
| G8 | **双口径指标**：LAR_delivered vs LAR_sent、ASR_attempted vs ASR_delivered、P_compromise、P_critical | 单口径 avg rate | 🟠 | Phase 6 |
| G9 | **strict/standard/permissive 三组冻结 Profile**（θ_I, θ_R, λ），禁止反向调参 | 设备 preset，非命令阈值 profile | 🟠 | Phase 4 |
| G10 | **攻击者位置×强度**（tx/rx/ind × strong/weak）+ lost-frame 专门建模 + 自适应攻击者 | 随机记录 + 随机重放 | 🔴（威胁模型弱） | Phase 5 |
| G11 | **§8.6 冻结规格**：WINDOW_COMMIT 单一实现、MAC domain 分离、19 个 blocker oracle tests、wire format | 测试不覆盖 resync/两阶段/epoch/G_hard | 🔴（测试缺口） | 贯穿全程 |
| G12 | **firmware-simulator 等价性**：同一 trace → engine 与 reference 产出同一 decision 序列 | 无参考实现层 | 🟠（增量 2） | Phase 7 |

---

## 2. 总体架构（双层 + 单一真相核）

```
src/replay/
├── core/                      ← 第1层:仿真引擎(概率化、批量蒙特卡洛、快)
│   ├── kernel/                ← 【单一真相核】两层共用,§8.6 冻结规格
│   │   ├── window_commit.py   ←  WINDOW_COMMIT(n,H,M_W,W) 唯一实现 (§8.6-3)
│   │   ├── acceptance.py      ←  SW 四分支判定 + G_hard 闸门 (§5.2/§5.3)
│   │   └── mac_domains.py     ←  domain 前缀常量 + tag 输入构造 (§8.6-1)
│   ├── frame.py               ← 扩展帧:dev_id/key_id/epoch/ctr/cmd/payload/flags/nonce/tag
│   ├── types.py               ← Mode 扩展、ReceiverState 扩展(epoch/pending 表/locked_safe)
│   ├── receiver.py            ← 重构:dispatch + 调 kernel + resync/critical 钩子
│   ├── sender.py              ← 扩展:PendingUserIntent 不变量
│   ├── resync.py              ← 新增:Authenticated Resync 状态机 (§5.4)
│   ├── critical.py            ← 新增:两阶段提交 pendingCritical 表 (§5.5)
│   ├── epoch.py               ← 新增:epoch / locked-safe / reboot (§8.5)
│   ├── policy.py              ← 新增:I(c)=max Hₖ 二分类 + Policy Table + 三 Profile (§3b)
│   ├── channel_models.py      ← 对齐:i.i.d.(Geometric 乱序) + GE + trace
│   ├── attacker.py            ← 重构:位置×强度 + lost-frame + 自适应攻击者 (§4.4)
│   ├── analytic/
│   │   └── models.py          ← 新增:闭式模型 a_W、LAR(W)、P_forge、P_compromise、W*
│   ├── experiment.py          ← 扩展:实验矩阵 + 消融钩子
│   ├── stats.py               ← 复用 Wilson + 零观测 UCB
│   └── metrics.py             ← 新增:双口径 LAR/ASR + P_compromise/P_critical
├── protocol/                  ← 第2层:协议参考实现(逐帧、确定性、贴近固件)
│   ├── wire.py                ← wire format 编解码(normal/critical/confirm/resync;nRF24 32B 短帧)
│   ├── state_machine.py       ← 接收端状态机(NORMAL/RESYNC_PENDING/CRIT_PENDING/LOCKED_SAFE)
│   ├── sender_sm.py           ← 发送端状态机(PendingUserIntent)
│   ├── reference_receiver.py  ← 调 core/kernel 的同一 WINDOW_COMMIT/acceptance
│   └── conformance.py         ← 等价性:同 trace → engine 与 reference 同一 decision 序列
├── contracts/                 ← 随帧/指标/profile 扩展;TS 同步 (hand-edit typescript.py)
├── api/  cli/  services/      ← 暴露新 profile/实验/等价性报告
└── (sim/, 顶层 replay/ 仍为 re-export shim)
```

**两层分工**：

| 维度 | `core/`（引擎） | `protocol/`（参考实现） |
|---|---|---|
| 目的 | 跑 10⁵ 蒙特卡洛、出统计图与 CI | 逐帧 decision、wire format、可移植 C |
| 表示 | 概率事件；窗口位掩码 `M_W` 统一 `list`/`bytearray`（与 protocol 一致） | 字节级帧、定长字段、查表状态机 |
| 随机性 | DeterministicRNG 注入 | 确定性（消费 trace） |
| 共用 | `core/kernel/`（WINDOW_COMMIT、acceptance、mac_domains） | 同左 |

> **命名决策点**：`protocol/` 也可叫 `firmware_ref/`。默认用 `protocol/`。执行 Phase 7 前如需改名，在此记录。

---

## 3. 数据模型：帧结构与契约

### 3.1 扩展 `Frame`（`core/frame.py`）

研究计划 §3.3 帧格式（保留位长符号）：

```
普通受保护帧     m_i      = (dev_id, key_id, e, ctr_i, c_i, payload_i, flags_i, tag_i)
关键命令确认帧   m_i^conf = (dev_id, key_id, e, ctr_i, c_i, N_R, payload_i, flags_i, tag_i)
```

推荐位长（§6.1）：`ℓ_t=96`（tag）、`ℓ_N=96`（nonce）、`ℓ_ctr=48`（counter）、`ℓ_e=32`（epoch）；下限线 `ℓ_t≥80, ℓ_N≥64, ℓ_ctr≥32, ℓ_e≥16`，32/48-bit 仅用于敏感性扫描。

`Frame` 新增字段（保持 immutable / `clone()`）：`dev_id, key_id, epoch, flags, payload`（现有 `command, counter, nonce, mac, is_attack` 保留）。`flags` 标识帧类型（NORMAL_REQ / CRIT_PREPARE / CRIT_CONFIRM / RESYNC_CHALLENGE / RESYNC_CONFIRM）。

**payload 表示（已定稿 2026-06-07）**：`core/` 引擎与 `protocol/` 参考层**统一存真实 `payload` 字节**（不走 len+hash 抽象）。好处：两层帧表示完全一致，firmware-simulator 等价性更天然；`payload_hash` 由真实字节派生，用于 MAC 绑定与 critical 的 `payload_hash` 匹配。代价：蒙特卡洛内存/速度略增（保真优先，可接受）。nRF24 短帧的 `payload_repr`（4B 无损）仍由 protocol 层在编码时处理。

### 3.2 MAC domain 分离（`core/kernel/mac_domains.py`，§8.6-1）

```
NORMAL_REQ_TAG       = HMAC96(K, "HSWCR_NORMAL_REQ"   || dev_id||key_id||epoch||ctr||cmd||payload||flags)
CRITICAL_PREPARE_TAG = HMAC96(K, "HSWCR_CRIT_PREPARE" || dev_id||key_id||epoch||ctr||cmd||payload_hash||flags)
CRITICAL_CONFIRM_TAG = HMAC96(K, "HSWCR_CRIT_CONFIRM" || dev_id||key_id||epoch||ctr||cmd||payload_hash||pid||nonce_id||nonce_R||ttl||flags)
RESYNC_CONFIRM_TAG   = HMAC96(K, "HSWCR_RESYNC_CONFIRM"|| dev_id||key_id||old_epoch||new_epoch||old_H||new_H||nonce_R||ttl||flags)
```

其中 `HMAC96(·) = Trunc_96(HMAC_SHA256(·))`，`||` 表示**类型化长度前缀编码**的串接（每段 = 1B 类型标签 `i/b/s/?` + 4B 大端长度前缀 + bytes，既杜绝 delimiter collision 又杜绝类型歧义如 `int 1` vs 等值 `bytes`；**不得**用字符分隔符如 `"|".join`）。**禁止跨帧类型重用 tag**（normal 帧 MAC 不能挪作 confirm 用）。Ascon profile 用 `Ascon-AEAD128` 的 128-bit tag 截断（不是“Ascon-MAC”，研究计划已更正）。

### 3.3 契约与 TS 同步

`contracts/models.py` 扩展：`SimulationSpec` 增 `g_hard`、`profile`（strict/standard/permissive）、`epoch_bits`、`attacker_position`、`attacker_inject_strength` 等；**resync 不作全局 bool，由防御变体 `Mode.SW_RESYNC` 表达**（修审查 P2，见 §9）；`SimulationResultRecord` 增双口径指标与 `p_compromise`/`p_critical`。
**注意（沿用 overhaul plan 教训 A）**：`web/lib/contracts.ts` 是**手写模板**，须手改 `contracts/typescript.py` 模板字符串后调 `write_contract_artifacts(Path('.'))` 重新生成；并加强 `web/scripts/check-contracts.mjs` 断言新字段名存在（当前只做子串检查）。

---

## 4. 协议机制设计（核心）

### 4.1 滑动窗口接受判定 + `WINDOW_COMMIT` 冻结函数

**SW 四分支判定**（§5.2，放 `core/kernel/acceptance.py`）：

```
SW(n; H, M_W, W) =
  ACCEPT_FORWARD     if n > H
  ACCEPT_IN_WINDOW   if H-W+1 <= n <= H  and  M_W[H-n] == 0
  REJECT_DUP         if H-W+1 <= n <= H  and  M_W[H-n] == 1
  REJECT_OLD         if n < H-W+1
```

**`WINDOW_COMMIT(n, H, M_W, W)` 唯一实现**（§8.6-3，engine 与 reference 都只调它）：

```python
def window_commit(n, H, M_W, W):
    if n > H:                          # 情形1:前跳接受
        J = n - H
        M_new = [0] * W
        M_new[0] = 1                   # 新窗口顶 H'=n 自身置位
        for d in range(W):
            if J + d < W:
                M_new[J + d] = M_W[d]  # 旧 bit d 平移到新 offset J+d
        return n, M_new
    if H - W + 1 <= n <= H and M_W[H - n] == 0:   # 情形2:窗口内接受
        M_W = M_W[:]; M_W[H - n] = 1
        return H, M_W
    return H, M_W                      # 情形3:dup/old/macfail/resync-pending,不变
```

约束：critical **prepare 不调** `window_commit`；critical **commit 与 normal accept 调同一份**；resync 同 epoch 路径用 `M_W = all_ones(W)` 覆盖。

**M_W 表示（已定稿 2026-06-07）**：统一 `list[int]`/`bytearray`（不用 int 位掩码），engine 与 protocol 共用，与 §8.6 伪代码逐行对应；`M_W[d]=1` 表示 counter `H-d` 已接受。

对应 blocker tests：`test_sw_duplicate_rejected`、`test_sw_old_rejected`、`test_sw_forward_jump_updates_bitmap_exactly`、`test_sw_in_window_accept_marks_only_target_bit`、`test_critical_commit_uses_same_window_commit_as_normal`。

### 4.2 W ≠ G_hard 分离（§5.3，核心设计原则）

- `W ≥ Q_{1-ε}(D_reorder) + 1`（向后乱序，通常 2~8）
- `G_hard ≥ Q_{1-ε}(B_gap) = Q_{1-ε}(B_loss) + 1`（向前突发跳跃，可 50+）
- **前跳 gap 比丢包长度多 1**：H 后连丢 B_loss 帧，下一送达帧 counter = H+B_loss+1。仿真扫描与 trace 校准**统一用 B_gap**（实测前跳分布），不用裸 B_loss。

危害论证（替换口语化“放大 50 倍”）：用 §6.2 闭式 `a_W(r;p_ℓ)` 给定量结论 —— W 从 4 增到 50，`r<W` 的“必接受重放”区间从 4 帧扩到 50 帧。对应 `test_Ghard_uses_forward_gap_not_raw_loss_count`、`test_forward_jump_over_Ghard_enters_resync`。

### 4.3 Authenticated Resync 状态机（§5.4，`core/resync.py` + `protocol/state_machine.py`）

触发：MAC 有效但 counter 前跳 > G_hard。六步：

```
1. 不直接执行原命令
2. 进入 RESYNC_PENDING
3. R → T : RESYNC_CHALLENGE(nonce_R, H, epoch, ttl)
4. T → R : RESYNC_CONFIRM(带 MAC)
5. 验证 nonce/MAC/epoch/ctr/ttl 通过后【仅更新 (e,H,M_W),不执行触发的原命令】
6. 同步恢复后,T 用新 ctr 重发该命令,再走正常接受 / challenge 流程
```

两条不可违反硬规则：

- **(H1) 不顺带执行原命令**：`RESYNC_CONFIRM ok ⇒ update(e,H,M_W)`，**no command execution**。否则 resync 变成绕过窗口的执行路径。
- **(H2) 封死被跳过的窗口**：同 epoch 路径 `M_W[d]=1 ∀d∈[0,W-1]`（整窗标记“已消费”），此后只有 ctr>new_H 的新帧能执行。仅 `H←new_H, M_W←0` 是不安全的（旧帧 ctr=198 会被接受）。
- reboot/brownout 走更强的 **epoch bump**：`e←old+1, M_W=0, 旧 epoch 帧全拒`。
- 异常：CONFIRM 验证失败 → 丢弃、保持 PENDING；TTL 超时 → 清 pending、回 NORMAL。`nonce_R` 进入 PENDING 时由 R 端 CSPRNG 生成；`ttl` 基于 2× 信道 RTT 上界 + 时钟漂移裕量。

对应 blocker tests：`test_resync_confirm_does_not_execute_original_command`、`test_resync_seals_skipped_window_counters`、`test_old_in_window_frame_rejected_after_resync`。

**建模定稿（2026-06-07）**：resync 用**完整事件建模** —— RESYNC_CHALLENGE/CONFIRM 作为真实帧进信道（引擎新增反向 `R→T` 信道），经历 loss/delay/TTL，engine 与 protocol 共用同一 kernel 状态机保证等价。这要求引擎先具备双向事件驱动能力，故新增 **Phase 1.5** 作为前置（见 §12）。`nonce_R` 进 PENDING 时 CSPRNG 生成；`ttl` = 2×信道RTT上界 + 漂移裕量（折算 tick）。

### 4.4 Critical 两阶段提交（§5.5，`core/critical.py`）

prepare → challenge → confirm → commit：

```
阶段1 Prepare : T→R REQ(e,ctr,cmd,payload,tag_req)
   R 校验 MACok ∧ 初步 SWok ∧ Π(cmd)=critical
   → 不执行、不更新 H/bitmap,仅登记 pendingCritical[pid]=(e,ctr,cmd,payload_hash,nonce_R,ttl,sender_id)
阶段2 Challenge: R→T CHALLENGE(pid,nonce_R,ttl,cmd_hint)
阶段3 Confirm  : T→R CONFIRM(pid,e,ctr,cmd,payload_hash,nonce_R,tag_conf)
   R 校验通过后【原子 commit】:更新 H/bitmap(同一 WINDOW_COMMIT) → 执行 cmd 一次 → 删 pending
```

Confirm 接受条件（全满足）：

```
Accept_critical = MACok ∧ SWok ∧ NonceFresh ∧ PolicyMatch ∧ TTLValid ∧ PendingMatch
```

三不变量：(1) 不提前提交（prepare 不动 H/bitmap）；(2) commit 仅一次（同 (e,ctr,cmd,payload_hash) 重复 confirm 拒绝）；(3) pending 表有界 **`N_p=2`（已定稿默认；可作为敏感性扫描变量 {1,2}）**，超出拒绝或淘汰最旧。对应 `test_critical_prepare_does_not_update_global_window`、`test_critical_commit_updates_window_and_executes_once`、`test_pending_table_capacity_Np_enforced`、`test_fake_challenge_does_not_commit`。

### 4.5 发送端 PendingUserIntent 不变量（§5.5-4，`core/sender.py` + `protocol/sender_sm.py`）

防 challenge 洗白重放：攻击者重放旧 critical REQ → R 照常发 CHALLENGE → 若发送端“收到合法 challenge 就自动 confirm”，真发送端替攻击者完成 confirm。防护：

```
ConfirmAllowed ⟺ (cmd,payload_hash) 匹配未消费的当前用户意图
                 ∧ t_now - t_intent ≤ τ_intent
                 ∧ challenge 来源/key_id/epoch 合法
```

`PendingIntent_T=(cmd,payload_hash,t_intent,state)`，commit 成功或超时后一次性清空。对应 `test_replayed_old_critical_req_no_sender_confirm_without_user_intent`。

### 4.6 epoch / locked-safe / reboot（§8.5，`core/epoch.py`）

- reboot 后清空 pending nonce 表（critical + resync）。
- reboot 后必须改 epoch，或用持久化 counter lease，避免 counter 空间复用。
- 高风险 profile 在 reboot/brownout（H、mask 丢失）后**不得**简单清零 mask 恢复普通接受 → 进入 **LOCKED_SAFE**：先认证重同步重建 epoch 与 H，再恢复收帧。
- counter 持久化用**租约**（不每帧写 NVM）：NVM 存 `(epoch, ctr_reserve_high, key_id, boot_counter)`，启动预约区间，快用完才写一次。

对应 `test_reboot_clears_pending_nonce`、`test_reboot_changes_epoch_or_uses_counter_lease`、`test_brownout_enters_locked_safe`、`test_no_old_frame_accepted_after_reboot`、`test_rng_entropy_source_enabled_before_nonce`。

---

## 5. 命令风险二分类 + Policy Table + 三 Profile（§3b，`core/policy.py`）

**影响度**（六维后果，取高水位）：

```
K = {phys, property, privacy, availability, auth, recovery}
H_k(c) ∈ {0,1,2,3,4}      I(c) = max_{k∈K} H_k(c)      I_max = 4
```

**风险与边际效用**：

```
R̃_D(c) = (I(c)/4) · P_succ,D(c)                      # 归一化风险
P_succ,D(c,x) = P_record · P_select · P_deliver^A · P_accept,D   # 四步链式
ΔU(c) = [R̃_SW(c) - R̃_CR(c)] - λ·[Cost_CR(c) - Cost_SW(c)]
Cost_D(c) = α_F·F̂ + α_L·L̂ + α_E·Ê + α_M·M̂   (Σα=1, 默认等权 0.25)
```

**三触发线**（命令升为 critical）：

```
c ∈ C_critical  ⟺  I(c) ≥ θ_I  ∨  R̃_SW(c) ≥ θ_R  ∨  ΔU(c) > 0
```

**三组冻结 Profile（部署前冻结，禁止反向调参）**：

| Profile | θ_I | θ_R | λ | 特征 |
|---|---:|---:|---:|---|
| strict | 2 | 0.005 | 0.25/0.5 | 更安全、更多命令升 critical |
| **standard（主线默认）** | 3 | 0.01 | 1 | 论文基准 |
| permissive | 4 | 0.02 | 2/4 | 更低成本、更少 challenge |

Policy Table 部署前离线算好，运行时 O(1) 查表。`SET_SPEED` 归类争议（物理伤害维度可能升 critical）在论文讨论。对应 `test_split_chapters_do_not_override_implementation_canonical_spec`（policy 以 §8.6 冻结规格为准）。

设备适用性 A/B/C/D（§3a）也并入 `policy.py`：用能力向量 `z_d=(b_bi,b_K,b_MAC,b_ctr,b_NVM,L_free,M_free,NVM_end,ℓ_MTU)` 与开销公式 `B_sec_normal/B_sec_critical/B_frame/B_state(W,N_p)` 判级（A 完全 / B 部分 / C 受限 / D 不适用）。

**主线设备/命令集（已定稿 2026-06-07）：多设备对比** —— 遥控小车（方向/速度/灯，含 `SET_SPEED` 的 normal/critical 争议）+ 智能门锁（UNLOCK/LOCK/PAIRING）+ 智能插座（ENABLE_POWER/FACTORY_RESET）。每设备一张独立 Policy Table，实验展示 HSW-CR 跨设备泛化；小车命令集与用户已有的小车逆向工作衔接。

---

## 6. 攻击者模型（§4.4，`core/attacker.py`）

两个正交维度（实验需扫描组合）：

```
录制位置 x ∈ {x_tx(Tx侧,可录到接收端未收到的帧,lost-frame 风险高),
              x_rx(Rx侧,重复重放易被窗口拒),
              x_ind(独立,取决于捕获质量)}
注入强度 g ∈ {strong(高概率送达), weak(低概率送达)}
```

攻击类型矩阵（4 类）：Duplicate Replay / **Lost-Frame Replay**（闭式 §6.2）/ Delayed Valid / Critical Delayed。

**增量 3：自适应攻击者**（知道 HSW-CR 策略的最优攻击者）：

- 专攻 normal 命令的 lost-frame 窗口（挑 `r<W` 的帧）；
- 诱导 resync（发 ctr 大跳跃帧试图绕窗）；
- 试 critical delayed（重放旧 critical REQ，赌发送端无 PendingUserIntent 防线）。
- 实现为可插拔 `AttackerStrategy`（`RandomReplay` baseline / `AdaptiveReplay`），实验对比两者下各防御的 ASR。**已定稿（2026-06-07）：上述三种自适应策略全部实现**（lost-frame 窗口 / 诱导 resync / critical delayed），各对应一组对抗实验。

能力边界：`P_forge ≤ q/2^{ℓ_t}`、`P_nonce ≤ q/2^{ℓ_N}`；不能破 MAC、不能猜 nonce、不能绕状态机。

---

## 7. 闭式数学模型层 + 双重验证（增量 1，`core/analytic/models.py`）

**核心闭式**：

```
lost-frame replay 接受概率   a_W(r; p_ℓ) = 1                      , 0 ≤ r < W
                                          = p_ℓ^(r-W+1)            , r ≥ W
几何乱序可用性               LAR(W) = 1 - q_r^W
伪造/猜 nonce               P_forge ≈ q/2^{ℓ_t}    P_nonce ≈ q/2^{ℓ_N}
系统级被攻陷                 P_compromise(N) = 1 - (1-ASR)^N
HSW-CR critical 残余风险      R_critical^HSWCR(W) ≈ P_succ,SW^lost(W) · P_nonce
窗口目标函数                 W* = min{W : LAR(W)≥LAR_target ∧ R_normal(W)≤R_norm_target ∧ R_critical^HSWCR(W)≤R_crit_target}
GE 稳态                      π_G=p_BG/(p_GB+p_BG), p̄_ℓ=π_G·k+π_B·h, E[burst]≈1/p_BG
```

**双重验证图**（审稿人加分项）：把解析曲线（`a_W`、`LAR(W)=1-q_r^W`）与蒙特卡洛散点叠在同一张图 → 一图证明“实现正确 + 模型正确”。新增 `scripts/plot_analytic_vs_mc.py` 产出该图。验收：解析与 MC 在扫描点 `W∈{1,2,3,4,5,6,8,12}` 上相对偏差落入 MC 95% CI。

---

## 8. 指标体系与统计口径（`core/metrics.py`，§7.1）

```
可用性  LAR_delivered = N_legit_accept / N_legit_delivered   (协议误拒率)
        LAR_sent      = N_legit_accept / N_legit_sent         (端到端,含信道丢包)
        FRR = 1 - LAR_delivered
安全性  ASR_attempted = N_replay_accept / N_replay_attempt
        ASR_delivered = N_replay_accept / N_replay_delivered
        ASR_attempted = P_deliver^A · ASR_delivered
系统级  P_compromise = #{run: ≥1 replay accepted} / N_runs
        P_critical   = #{run: ≥1 critical replay accepted} / N_runs
零观测  k=0 时禁报“安全=0”,改报 Wilson 上界 UCB(0,N) = z²/(N+z²)
        (注明单侧 z=1.645 还是双侧 z=1.96;与 rule-of-three 3/N 互校)
```

样本量反推（声明 p_claim 级上界所需 N_attack ≥ z²(1/p_claim − 1)）：10⁻⁴ ⇒ ≈4×10⁴/场景，10⁻⁵ ⇒ ≈3.8×10⁵/场景。**已定稿（2026-06-07）：两档都跑** —— 主线全矩阵用 p_claim=10⁻⁴（N_attack≥4×10⁴）；关键场景（critical replay、自适应攻击者）补 p_claim=10⁻⁵（N_attack≥3.8×10⁵）做强声明。

---

## 9. 实验矩阵与消融实验（增量 4，`core/experiment.py` + `scripts/`）

防御集：`{None, Counter, SW, SW+Resync, ChallengeAll, HSW-CR}`。**映射到代码（修审查 P1-1：用防御变体而非全局 bool）**：`SW`=`Mode.WINDOW`（纯 baseline，**不被 G_hard hook 污染**）；`SW+Resync`=`Mode.SW_RESYNC`（resync 是 mode 固有属性）；`HSW-CR` 自带 resync。消融"Resync on/off" = 同 `g_hard` 下跑 `modes=[WINDOW, SW_RESYNC]` 对比（同一 batch 可并列，因每个 mode 自带 resync 语义，不再共享全局 `enable_resync`）。

| 实验 | 自变量 | 目的 / 论文论据 |
|---|---|---|
| Baseline | 防御方式 | 验证基础模型、各防御排序 |
| Window trade-off | W∈{1,2,3,4,5,6,8,12}、乱序深度、攻击者位置 | LAR↑ 但 ReplayExposure↑，不能“窗口越大越好” |
| Burst loss | GE (p_GB,p_BG,k,h)、G_hard | 突发丢包下 G_hard + resync 的价值 |
| **消融:Resync on/off** | `defense_variant ∈ {WINDOW, SW_RESYNC}` | 证明 Authenticated Resync 必要性（SW+Resync LAR≈1 ≫ 纯 SW） |
| **消融:W=G_hard vs W≠G_hard** | 绑定/分离 | 量化“安全因可用性被牺牲”，用 a_W 闭式 |
| Critical replay | 关键命令占比、policy table | HSW-CR critical 接近 ChallengeAll、成本约 1/10 |
| Adaptive attacker | RandomReplay vs AdaptiveReplay | 对抗了解机制的攻击者仍成立 |
| Real-trace（占位） | trace vs synthetic | 后续阶段，趋势/排序/同量级判据 |

每组报告：seed、N_runs/N_frames/N_attack、信道参数、攻击者 (x,g,P_record,P_deliver^A)、防御参数 (D,W,G_hard,ℓ_t,ℓ_N,ℓ_ctr)、mean±95%CI、原始 CSV/JSON。

---

## 10. 测试策略：19 个 blocker tests + firmware-simulator 等价性（增量 2，§8.6）

**19 个 oracle tests（不全绿不得声称协议安全）**，归入 `tests/test_hswcr_blockers.py`：

```
# 滑动窗口
test_sw_duplicate_rejected
test_sw_old_rejected
# G_hard 闸门与认证重同步
test_forward_jump_over_Ghard_enters_resync
test_resync_confirm_does_not_execute_original_command
test_resync_seals_skipped_window_counters
test_old_in_window_frame_rejected_after_resync
# 关键命令两阶段提交 + 发送端意图
test_critical_prepare_does_not_update_global_window
test_critical_commit_updates_window_and_executes_once
test_replayed_old_critical_req_no_sender_confirm_without_user_intent
test_pending_table_capacity_Np_enforced
test_fake_challenge_does_not_commit
# RNG / reboot
test_rng_entropy_source_enabled_before_nonce
test_reboot_clears_pending_nonce
test_no_old_frame_accepted_after_reboot
# 滑动窗口状态更新精确性
test_sw_forward_jump_updates_bitmap_exactly
test_sw_in_window_accept_marks_only_target_bit
test_critical_commit_uses_same_window_commit_as_normal
# G_hard 前跳 gap 定义
test_Ghard_uses_forward_gap_not_raw_loss_count
# 实现规范源
test_split_chapters_do_not_override_implementation_canonical_spec
```

**等价性**（`protocol/conformance.py` + `tests/test_conformance.py`）：同一 trace schedule 喂给 engine 与 reference，断言 `decision_engine(i) == decision_reference(i) ∀i`。须声明 trace 覆盖率与边界用例（不只在训练 trace 上成立）。

运行：`PYTHONPATH=src:. python3 -m pytest`（保留 overhaul plan 的约定）。

---

## 11. Web 可视化与论文产出映射（增量 3 + 论文 8 章）

### 11.1 Web（`web/`）

- Simulator 增 profile（strict/standard/permissive）+ 防御对比 + 消融开关。
- 新页/区：**双重验证图**（解析 vs MC 叠图）、Resync 消融、Critical replay 帕累托。
- artifact 流水线扩展：新 sweep（resync 消融、W=G_hard 消融、adaptive attacker）写入 `web/public/data/artifacts/`。

### 11.2 论文 8 章映射（研究计划 §2.2）

| 章 | 内容 | 本计划产出 |
|---|---|---|
| 1 绪论 | 威胁、研究问题 | §0 |
| 2 相关研究 | MAC/window/challenge/轻量密码/GE | 文献(知识库 §10) |
| 3 系统模型 | 设备能力/命令集/风险/攻击者/信道 | §3,§5,§6 |
| 4 防御协议 | MAC→SW→Resync→Challenge→HSW-CR 递进 + 状态机 | §4 |
| 5 数学模型与仿真 | 闭式推导 + MC 框架 + 指标 | §7,§8 |
| 6 实验结果 | baseline/window/resync/critical/扫描 | §9 |
| 7 原型验证 | 帧格式/状态机/Trace/实测对比 | §10,Phase 7,真机后续 |
| 8 讨论与局限 | synthetic vs real 边界、未覆盖攻击 | §0.3 |

---

## 12. 阶段化实施路线（Phases，门控）

> 每个 Phase 末尾跑 `pytest + ruff + mypy` 绿灯门；TDD（先写失败测试再实现）；频繁提交。Phase N+1 不在 Phase N 门绿前启动。

- **Phase 0 · 准备与单一真相核抽取**
  - 清理工作树 5 个 macOS 副本（`* 2.json`）+ 加 `.gitignore`；建立契约/测试基线快照。
  - 抽出 `core/kernel/{window_commit,acceptance,mac_domains}.py`，把现有 window 逻辑迁入并以现有测试守护（行为不变重构）。
  - 门：现有全部测试仍绿。

- **Phase 1 · 帧结构 + WINDOW_COMMIT + G_hard**（G1,G6,G11 部分）
  - 扩展 `Frame`（epoch/dev_id/key_id/flags/payload）+ 契约 + TS 同步。
  - 落地 `WINDOW_COMMIT` 冻结函数 + SW 四分支 + `G_hard` 闸门（前跳>G_hard 触发 resync 钩子，先占位）。
  - blocker：`test_sw_*`、`test_Ghard_uses_forward_gap_not_raw_loss_count`、`test_forward_jump_over_Ghard_enters_resync`。

- **Phase 1.5 · 双向事件驱动引擎基座**（resync/critical 前置，设计 4 定稿引入）
  - 把 `experiment.py` 单向帧 for 循环升级为 tick/事件驱动调度器：支持反向 `R→T` 信道、TTL 超时、多帧交互。
  - 门：现有单向实验数值在新调度器下回归复现（容差内）。

- **Phase 2 · Authenticated Resync 状态机**（G2）
  - `core/resync.py` + ReceiverState 扩展（RESYNC_PENDING、nonce_R、ttl）。
  - 硬规则 H1（不执行原命令）+ H2（封窗）+ epoch bump。
  - blocker：`test_resync_*`、`test_old_in_window_frame_rejected_after_resync`。

- **Phase 3 · Critical 两阶段提交 + 发送端不变量**（G3,G4）
  - `core/critical.py`（pendingCritical、N_p 有界、原子 commit）+ `core/sender.py`（PendingUserIntent）。
  - blocker：`test_critical_*`、`test_replayed_old_critical_req_no_sender_confirm_without_user_intent`、`test_pending_table_capacity_Np_enforced`、`test_fake_challenge_does_not_commit`。

- **Phase 4 · 风险二分类 + Policy Table + 三 Profile + 设备判定**（G5,G9）
  - `core/policy.py`：I(c)=max Hₖ、三触发线、strict/standard/permissive 冻结、A/B/C/D 判级。
  - 重写 `verify_hsw_cr` 走 policy table（替换 `risk>=0.8`）。
  - blocker：`test_split_chapters_do_not_override_implementation_canonical_spec`。

- **Phase 5 · 攻击者增强 + 闭式模型 + 双重验证**（G7,G10,增量1,增量3）
  - `core/attacker.py`：位置×强度 + lost-frame + `AdaptiveReplay`。
  - `core/analytic/models.py`：a_W、LAR(W)、P_forge、P_compromise、W\*。
  - `scripts/plot_analytic_vs_mc.py` 双重验证图。
  - epoch/reboot/locked-safe（`core/epoch.py`）+ RNG 规则测试。

- **Phase 6 · 指标体系 + 实验矩阵 + 消融**（G8,增量4）
  - `core/metrics.py` 双口径 + P_compromise/P_critical + 零观测 UCB。
  - 实验矩阵 + Resync on/off、W=G_hard 消融、adaptive 对比；artifact 产出。

- **Phase 7 · protocol 参考实现层 + 等价性**（G12,增量2）
  - `protocol/{wire,state_machine,sender_sm,reference_receiver,conformance}.py`（含 nRF24 32B 短帧 wire format）。
  - `tests/test_conformance.py`：engine ≡ reference。

- **Phase 8 · Web + 论文产出 + 发布**
  - Web 新页（双重验证图/消融/帕累托）+ profile 控件；论文图表脚本；README 证据边界；CHANGELOG/Release。

---

## 13. 风险与 YAGNI

- **范围爆炸**：协议状态机庞大。对策：严格门控 + 每 Phase 可独立交付价值；reference 层（Phase 7）若时间紧可后置。
- **闭式与仿真不吻合**：用 `superpowers:systematic-debugging` 回查（先怀疑实现/参数定义，尤其 `r` 定义与 B_gap），不要调参到绿。
- **契约漂移**：每次改 Pydantic 必手改 `typescript.py` 模板 + 重生成 + 加强 check-contracts。
- **不做（YAGNI）**：真实 pcap/CSV trace 加载器（仅留 in-memory `list[bool]` 占位）；真机实验（留作后续阶段）；不把研究设计在代码里“即兴改造”。
- **immutability 例外**：现有引擎依赖 `ReceiverState` 原地变更，重写为不可变高风险、超范围；新字段附加式加入，保持现有变更契约（沿用 overhaul plan 记录的权衡）。

---

## 14. 与研究计划的双向同步约定

- 研究计划为权威；本仓只做实现。实现中发现的规格缺口/疑点记录于此（待澄清）：
  - [x] `nonce_R` 生成时机与 `ttl`：已采纳默认（PENDING 时 CSPRNG 生成；ttl=2×RTT上界+漂移裕量，折算 tick）。
  - [ ] `SET_SPEED` 归类（normal vs critical）：多设备主线下，小车 Policy Table 就地判定（§3b 物理伤害维度可能升 critical）。
  - [ ] §4.4 攻击矩阵 3 行 vs 4 行最终取舍。
  - [ ] Φ 状态转移函数是否进入 H_k 主流程（§3b 待办）。
- 反向：本实现产出的 blocker tests / 等价性报告 / 双重验证图，可回填研究计划 §7、§8 作为证据。

---

## 执行选项（Handoff）

计划已保存到 `docs/plans/2026-06-07-hsw-cr-full-protocol-overhaul.md`。两种执行方式：

1. **Subagent-Driven（本会话）**：我为每个 Task 派新 subagent，任务间代码审查，快速迭代（用 `superpowers:subagent-driven-development`）。
2. **Parallel Session（独立会话）**：在 worktree 开新会话，用 `superpowers:executing-plans` 批量执行 + 检查点。

确认设计后再选执行方式。下一步建议：先把 **Phase 0 + Phase 1** 用 `superpowers:writing-plans` 展开成逐行 RED/GREEN TDD 任务。
