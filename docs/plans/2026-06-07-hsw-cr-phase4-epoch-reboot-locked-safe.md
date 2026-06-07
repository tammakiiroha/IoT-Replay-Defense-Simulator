# HSW-CR Phase 4 · Epoch Bump / Reboot / LOCKED_SAFE / Counter-Lease — 逐行 TDD 实施计划

> **For Claude:** REQUIRED SUB-SKILL: 用 `superpowers:executing-plans` 逐任务实施本计划。
> 本文件是主计划 `docs/plans/2026-06-07-hsw-cr-full-protocol-overhaul.md` **§4.6**（epoch / locked-safe / reboot）的执行细化，对照 Phase 0/1/1.5/2/3 落地后的真实代码展开。**执行前先确认下方「待拍板的关键设计决策」。**

**Goal:** 让 HSW_CR 接收端在 reboot/brownout（易失态 H/M_W/pending 全丢）后**不**简单清零恢复普通接受，而是进入 **LOCKED_SAFE** —— 先 epoch bump + 认证重同步重建 (epoch, H)，再恢复收帧；发送端用 **counter lease** 保证跨重启 counter 不复用。杜绝「reboot 洗白旧帧」。

**Architecture:** kernel 加 `epoch.py` 纯函数（epoch bump、lease 预约/推进、reboot-后状态判定）；`ReceiverState` 加显式 `locked_safe` 状态 + lease/boot 字段；`Sender` 加 counter-lease 持久化模型；receiver 新增 `reboot()` + LOCKED_SAFE 收帧门 + `recover_from_locked_safe`（复用 Phase 2 resync 往返重建 epoch/H）；引擎在 trace/config 注入 reboot 事件（末尾抽取，零漂移）。engine 与 protocol 共用同一 kernel。

**Tech Stack:** Python 3.9+、现有 kernel（`window_commit`/`acceptance`/`mac_domains`/`resync_commit`/`critical_commit`）、Phase 2 `EventScheduler`+resync 往返、pytest。环境：`.venv/bin/python`，`PYTHONPATH=src:.`，命令前若 cwd 漂移先 `cd /Users/romeitou/Desktop/論文/Replay`。

---

## ⚠️ 范围澄清（务必先读）

- 主计划把 **G5/G9（命令风险二分类 + Policy Table + strict/standard/permissive 三 Profile）** 也挂在「Phase 4」名下，而把 epoch/reboot/locked-safe 放在「Phase 5」摘要里。**本计划按你的最新口径重新切分**：本 Phase 4 = **仅** §4.6（epoch / LOCKED_SAFE / reboot / counter-lease）。
- **不做（留后续 Phase）**：Policy Table / I(c)=max Hₖ / 三触发线 / 三冻结 Profile（G5/G9，单独 Phase）；adaptive 攻击者 / 闭式模型（G7/G10）；指标口径变更（见硬约束 7）；protocol 参考实现层（G12）。
- 复用 Phase 2 的 `epoch` 字段与 resync 往返做「重建 epoch/H」，**不**在本 Phase 引入新的 wire format。

---

## 待拍板的关键设计决策（执行前必须确认）

Phase 4 碰接收端生命周期与跨重启 counter 空间，比 Phase 3 更易引入「reboot 洗白」漏洞。六处分叉，先定再写代码。下面是**推荐方案**：

### D1：reboot 在仿真里怎么建模？谁触发？
- **推荐**：reboot 是**接收端事件**——易失态（`last_counter`/`received_mask`/`resync_pending`/`pending_critical`/`committed_critical`/`outstanding_nonces`/`expected_nonce`/`crit_nonce_seq`）丢失，NVM 持久态（`epoch`/lease 区间/`key_id`/`boot_counter`）保留。引擎在「某 tick / 某帧序号」按 config/trace 注入一次 `receiver.reboot()`。发送端的 counter-lease 是**发送端 NVM** 关注点，独立建模。
- **备选否决**：把 reboot 当成普通帧（无法表达易失/持久态分离）。
- **代价**：reboot 注入点在一次运行内有界、确定（trace 决定），不与任意帧交错。

### D2：LOCKED_SAFE 用显式状态还是隐式？
- **推荐**：`ReceiverState` 加显式 `locked_safe: bool = False`（最小、可加默认、向后兼容；与现有隐式态 resync_pending/pending_critical 风格一致）。LOCKED_SAFE=True 时**拒绝一切 normal/critical 收帧**（reason=`locked_safe_reject`），只接受用于重建的 RESYNC_CONFIRM。
- **备选**：引 `ReceiverPhase` 枚举 {NORMAL, LOCKED_SAFE}（更干净但改动面大、触及更多分支）。**否决**（YAGNI；一个 bool 足够表达本 Phase 语义）。

### D3：epoch bump 与 counter lease 谁是权威？（**安全核心**）
- **推荐（职责分离，互补非竞争）**：
  - **epoch = 接收端权威的「新鲜域」**：reboot ⇒ `epoch ← epoch+1`（kernel `epoch_bump`），旧 epoch 帧**全拒**（MAC 域含 epoch，旧帧 tag 对不上新 epoch）。这是**抗 reboot 洗白**的主机制。
  - **counter lease = 发送端权威的「同 epoch 内 counter 单调」**：发送端 NVM 存 `(epoch, ctr_reserve_high, key_id, boot_counter)`，启动**预约**一段 ctr 区间，仅快用完才写一次 NVM；跨自身重启不复用 ctr。
  - **裁决**：reboot 后接收端**进 LOCKED_SAFE 并 bump epoch**；发送端经认证 resync 进入新 epoch、并按 lease 取下一段 ctr。epoch 决定「哪些帧算新鲜」，lease 决定「发送端绝不复用 ctr」——二者不冲突。
- **备选否决**：只用 lease 不 bump epoch（接收端无法独立拒绝旧 epoch 帧，依赖发送端自律，不安全）；只 bump epoch 不要 lease（发送端自身重启后可能复用同 epoch 内 ctr，与窗口语义冲突）。

### D4：reboot 后 pending 表清理 vs 继承？
- **推荐（§4.6「清空 pending nonce 表 critical + resync」）**：reboot 清空 `resync_pending`、`pending_critical`、`outstanding_nonces`、`expected_nonce`，`crit_nonce_seq←0`；`last_counter←-1`、`received_mask←[]`（易失，丢失）。
- **`committed_critical`（去重集）**：**也清空**——跨 reboot 的去重由 **D7 的显式 epoch 守门**兜底（旧 epoch confirm：要么 `frame.epoch != state.epoch` 被守门拒，要么攻击者篡改 `frame.epoch` 使 `crit_confirm_tag` 失配；二者皆拒，不可能 re-commit）。**注意：不是靠「自动 MAC 失配」**（见 R2 更正）。**blocker 测试钉死**：reboot+recovery 后重放旧 epoch critical confirm/prepare → 被 epoch 守门拒，而非依赖 committed 集。
- **持久态**：`epoch`（bump 后的新值）、lease 区间、`key_id`、`boot_counter`（+1）保留。

### D5：reboot 后如何恢复收帧（LOCKED_SAFE → NORMAL）？
- **推荐（复用 Phase 2 resync）**：LOCKED_SAFE 下，第一帧若触发不可接受（H 丢失，`last_counter=-1`），接收端**不**走「初始帧直接建窗」老路（那等于洗白），而是要求一次**认证重同步**重建 (epoch, H)；`process_resync_confirm` 成功后 **`locked_safe←False`**、回 NORMAL。
  - **⚠️ 缺口（已修，blocker #2）**：现有 `issue_resync_challenge` 要求 `state.resync_pending` 已存在（[receiver.py:350](src/replay/core/receiver.py)），而 LOCKED_SAFE 会在 normal/critical 入口直接 `locked_safe_reject`，**永不经 `verify_with_window` 创建 pending** → 无恢复入口。**必须新增专用入口** `begin_locked_safe_resync(self, rng, *, now_tick, ttl_ticks) -> Frame`：显式创建 `ResyncPending(nonce_r="", trigger_counter=0, epoch=state.epoch[新], h_at_challenge=-1, ttl_ticks, expire_tick=now_tick+ttl)` 再 issue R2T challenge（counter=-1 占位 old_h、epoch=新）。否则 4.3/4.5 不可实现。
  - **发送端 epoch 同步（blocker #4 关联）**：recovery 成功后必须用**明确方法** `Sender.adopt_epoch(new_epoch)` 更新发送端自有 epoch，**不得**由 engine 每次偷读 `receiver.state.epoch`。confirm 绑定 **新 epoch**；旧 epoch 的 confirm 拒绝。
- **备选否决**：reboot 后用普通帧的「初始帧建窗」恢复（=洗白，违背 §4.6）。

### D6：counter-lease 建模深度？（**已修，blocker #3：旧算法崩溃后会复用 counter**）
- **⚠️ 原 `next_lease(ctr, reserve_high)`「接近 high 才扩容」算法错误**：若 NVM 只存 `ctr_reserve_high`，崩溃后易失 `tx_counter` 归零，`ctr=0, reserve_high=100` 不触发扩容 → 下一帧从 1 开始**复用** 1..100。
- **正确模型——boot 时烧掉旧 lease**：`Sender` 加 `nvm_ctr_reserve_high`（NVM 持久）+ `reserve_size` 参数 + `boot_counter`。`begin_boot(self)`：
  1. `self.tx_counter = self.nvm_ctr_reserve_high`（**烧掉**整段旧预约——下一帧 `next_frame` 会 `+1`，从 `old_high+1` 起，必 > 崩溃前任何 ctr）；
  2. `self.nvm_ctr_reserve_high += self.reserve_size`（预约新段，模拟一次 NVM 写）；
  3. `self.boot_counter += 1`。
  - 稳态运行中，当 `tx_counter` 逼近 `nvm_ctr_reserve_high` 时也写一次 NVM 扩容（`nvm_ctr_reserve_high += reserve_size`），**非每帧写**。
- **不变量（R5，blocker 测试钉死）**：模拟「崩溃前只用到 10、NVM high=100」→ `begin_boot()` 后下一帧 ctr **必 > 100**（不是 11，不是 1）。
- **备选否决**：每帧写 NVM；省略 lease（D3 已否决）。

### D7：sender epoch 权威落到接口 + 接收端显式 epoch 守门（**安全核心，blocker #1+#4**）
- **⚠️ 现状缺口（已核实）**：`Sender.next_frame` 不携带 epoch（[sender.py:25](src/replay/core/sender.py)，frame.epoch 默认 0）；critical 由 engine 把 `receiver.state.epoch` 传给 `begin_critical_intent`（[sender.py:69](src/replay/core/sender.py) 附近），**掩盖了发送端自身 epoch 状态**。接收端则完全不比 `frame.epoch == state.epoch`。
- **推荐（发送端拥有 epoch、接收端显式守门）**：
  - **发送端**：`Sender` 加 `current_epoch: int = 0` + `nvm_epoch: int = 0`。`next_frame`（HSW_CR normal）stamp `frame.epoch = self.current_epoch` 并把 epoch 绑进 normal MAC（见下「MAC 绑定取舍」）；`begin_critical_intent` 从 **`self.current_epoch`** 取 epoch（不再由 engine 传 receiver epoch）；recovery 经 `adopt_epoch(new)` 更新。
  - **接收端**：`process`（HSW_CR 分支）/`process_crit_prepare`/`process_crit_confirm` 一律先 `if frame.epoch != state.epoch: return (False, "epoch_mismatch")`（不动状态），且在 LOCKED_SAFE 闸门**之后**、其它判定**之前**。
  - **MAC 绑定取舍（请你裁决）**：
    - (a)【推荐，改动小】normal 帧**不**改 MAC（仍 `HmacAuthenticator(counter,command)`），replay 防御靠「epoch 守门 + SW 窗口 + lease 单调 ctr」（recovery 后 H 重建到高位，旧 ctr REJECT_OLD）。critical 帧已 epoch-in-MAC，天然防篡改 epoch。
    - (b)【更强、改动大】HSW_CR normal 帧改用 `normal_req_tag`(含 epoch)，需把 HSW_CR 低风险路径从共享 `verify_with_window` 分出独立 MAC 分支（STABLE_MODES 不受影响但 drift 风险升高）。
    - 我**倾向 (a)**：在「lease 保证新 ctr 远高于旧 ctr」前提下，SW 窗口已挡住 normal replay，epoch 守门作纵深；(b) 留作后续硬化。
- **测试要求**：recovery **完成后**（非仅 LOCKED_SAFE 中）重放旧 epoch 的 normal **和** critical 帧都必须拒。

> **请确认 D1=接收端事件注入、D2=显式 `locked_safe` bool、D3=epoch 接收端权威 + lease 发送端权威（互补）、D4=清空含 committed_critical（靠 D7 显式 epoch 守门去重，非自动失配）、D5=LOCKED_SAFE 经 `begin_locked_safe_resync` 新入口认证重建后回 NORMAL、D6=boot 烧旧 lease 防复用、D7=发送端拥有 epoch + 接收端显式守门（含 MAC 绑定取舍 a/b）。** 确认后我把「引擎 reboot 注入接线」Task 的逐行代码定稿（kernel/state/reboot/locked-safe 闸门现在即可执行）。

---

## 硬约束（贯穿，blocker 守门）

1. **(R1) reboot 不洗白**：reboot 后 `last_counter` 丢失，但**不得**用「初始帧建窗」接受任意帧；必须先认证重同步。
2. **(R2) epoch 单调 bump + 显式守门**：reboot ⇒ `epoch+1`。**⚠️ 旧 epoch 帧不会「自动 MAC 失配」**——经核实（[receiver.py:75](src/replay/core/receiver.py) window 路径用 `HmacAuthenticator(counter, command)` 不含 epoch；[receiver.py:385](src/replay/core/receiver.py) critical prepare 用 `frame.epoch` 自验自、从不比 `state.epoch`）。因此必须在 **HSW_CR 全收帧路径**（window/normal、crit prepare、crit confirm）显式加 `frame.epoch == state.epoch` 守门（不等即拒、不动状态）。replay 防御按帧型分层（见 D7）：**critical 帧**靠「epoch 守门 + crit_*_tag 已含 epoch」（攻击者篡改 frame.epoch 即 MAC 失配）；**normal 帧**靠「epoch 守门 + SW 窗口 + lease 单调 ctr」（normal MAC 不含 epoch，但 recovery 后 H 重建到高位 + lease 保证新 ctr 远高于旧 ctr，旧帧 REJECT_OLD）。
3. **(R3) LOCKED_SAFE 闸门**：`locked_safe=True` 时拒绝 normal/critical 收帧（`locked_safe_reject`），仅接受重建用的（新 epoch）RESYNC_CONFIRM。
4. **(R4) pending 全清**：reboot 清空 resync/critical pending + nonce 表 + committed 集；持久态（epoch/lease/key_id/boot_counter）保留。
5. **(R5) counter 不复用**：发送端跨 `begin_boot()` 的 `tx_counter` 严格单调、不回退、不复用（lease 不变量）。
6. **(R6) 恢复路径唯一**：LOCKED_SAFE → NORMAL 只能经认证 resync 成功（新 epoch 绑定），别无旁路。
7. **(R7) 不动指标口径（呼应 Phase 3 known boundary）**：Phase 4 **不**改 `attack_success`/`legit_accepted` 等归因语义；若 reboot 引出新的归因问题（如「reboot 期间丢帧」），**只记录为 known boundary，单独设 metrics task**，不在本 Phase 顺手改。
8. **回归零影响**：非 HSW_CR 模式（含 STABLE_MODES）数值逐字节不变；reboot 仅对 HSW_CR 注入。
> 引用 @superpowers:test-driven-development、@superpowers:verification-before-completion。

---

## 当前形态速查（细化所依据的真实代码）

- `src/replay/core/types.py`：
  - `Mode`（:10-19）含 `HSW_CR`；`WINDOW_VERIFY_MODES`/`WINDOW_SIZED_MODES` 常量。
  - `ReceiverState`（:129+）现有：`last_counter/expected_nonce/received_mask/outstanding_nonces/used_nonces/epoch/resync_pending/pending_critical/committed_critical/crit_nonce_seq`。**无 `locked_safe`、无 lease/boot 字段。**
  - `Sender` 在 `sender.py`（dataclass）：`mode/shared_key/mac_length/tx_counter/authenticator/pending_intent`。**无 lease/boot 字段。**
  - `SimulationConfig`：已含 `critical_*`/`tau_intent_ticks`/`resync_*`。**无 reboot 注入字段。**
- `src/replay/core/kernel/`：`window_commit`/`acceptance(classify/needs_resync)`/`mac_domains`/`resync_commit`/`critical_commit`。**无 `epoch.py`。**
  - `mac_domains`：`normal_req_tag`/`crit_prepare_tag`/`crit_confirm_tag`/`resync_confirm_tag` 均含 `epoch` 入参 → epoch bump 后旧帧 tag 自动失配（R2 的密码学基础）。
- `src/replay/core/receiver.py`：`Receiver`（mode/window/g_hard/critical_* 属性）；`process`/`process_resync_confirm`/`issue_resync_challenge`/`time_out_resync`/`process_crit_prepare`/`issue_crit_challenge`/`process_crit_confirm`/`time_out_critical`/`reset`。**无 `reboot`、无 LOCKED_SAFE 闸门。**
- `src/replay/core/experiment.py`：`simulate_one_run` + `simulate_one_run_with_trace`，`_resolve_resync`/`_resolve_critical` 有界子泵；两路径 `process_arrived`。
- `src/replay/core/trace.py`：`ScenarioTrace` + `generate_trace`，resync/critical 序列**末尾抽取**（零漂移技巧范本）。
- 回归安全网：`tests/test_engine_baseline_regression.py`（`STABLE_MODES` 不含 HSW_CR/SW_RESYNC）+ `tests/fixtures/engine_baseline.json`。

---

## Phase 4 · Tasks

> 门：reboot/locked-safe/lease blocker 全绿 + 单元/集成全绿 + `test_engine_baseline_regression`(STABLE_MODES) 逐值相等 + 全量 pytest 绿 + ruff/mypy 不退化 + check-contracts 绿。

### Task 4.0：kernel `epoch.py`（纯函数：epoch_bump / next_lease / lease_ok）

**Files:** Create `src/replay/core/kernel/epoch.py`；Test `tests/test_kernel_epoch.py`

**要点（纯函数，无副作用）：**
- `epoch_bump(epoch: int) -> int`：`return epoch + 1`（R2，单调）。
- `next_lease(ctr: int, reserve_high: int, reserve_size: int) -> int`：若 `ctr >= reserve_high - 1` 返回 `reserve_high + reserve_size`，否则返回 `reserve_high`（R5；纯函数，调用方决定是否「写 NVM」）。
- `lease_ok(prev_ctr: int, new_ctr: int) -> bool`：`new_ctr > prev_ctr`（跨 boot 单调断言用）。

**测试要点：** `epoch_bump(0)==1 且严格递增`；`next_lease` 在临界点扩容、未临界不动；`lease_ok` 拒绝回退/复用。
**Step 5:** 提交 `feat: add epoch kernel primitives (epoch_bump/next_lease/lease_ok)`。

### Task 4.1：`ReceiverState` 加 `locked_safe` + lease/boot 持久字段；`SimulationConfig` 加 reboot 注入

**Files:** Modify `src/replay/core/types.py`；Test `tests/test_reboot_state.py`

**要点：**
- `ReceiverState` 追加：`locked_safe: bool = False`、`boot_counter: int = 0`、`nvm_epoch: int = 0`（持久 epoch 镜像，用于校验 reboot 后 bump）。
- `SimulationConfig` 追加：`reboot_at_legit_index: int | None = None`（在第 N 条 legit 后注入一次 reboot；None=不注入）。**带默认、向后兼容。**
- 钉默认值测试 + reboot 字段可设置。
**Step 5:** 提交 `feat: extend ReceiverState with locked_safe and persistent boot/lease fields`。

### Task 4.2：receiver `reboot()` + LOCKED_SAFE 收帧闸门（R1/R2/R3/R4）

**Files:** Modify `src/replay/core/receiver.py`；Test `tests/test_reboot_receiver.py`

**要点：**
- `reboot(self) -> None`：清空易失态（last_counter←-1、received_mask←[]、resync_pending←None、pending_critical←{}、committed_critical←set()、outstanding_nonces←{}、expected_nonce←None、crit_nonce_seq←0）；`epoch ← epoch_bump(epoch)`、`nvm_epoch ← epoch`、`boot_counter += 1`、`locked_safe ← True`。
- `process`(HSW_CR 分支)/`process_crit_prepare`/`process_crit_confirm` 入口加两道闸（顺序：LOCKED_SAFE → epoch）：
  1. `if state.locked_safe: return (False, "locked_safe_reject")`（R3；不动状态）。
  2. `if frame.epoch != state.epoch: return (False, "epoch_mismatch")`（**R2/D7 显式 epoch 守门**；不动状态）——这是旧 epoch 帧被拒的**真正机制**（非「自动 MAC 失配」）。
- **blocker 测试：**
  - `test_reboot_bumps_epoch_and_enters_locked_safe`（R2/R3）。
  - `test_reboot_clears_pending_tables`（R4：critical/resync/nonce/committed 全清）。
  - `test_old_epoch_frame_rejected_by_explicit_gate`（R2/D7：`frame.epoch != state.epoch` 的 normal/critical 帧 → `epoch_mismatch`，状态不变）。
  - `test_locked_safe_rejects_normal_and_critical`（R3）。
**Step 5:** 提交 `feat: receiver reboot bumps epoch, clears volatile state, enters LOCKED_SAFE with explicit epoch gate`。

### Task 4.3：LOCKED_SAFE 经认证 resync 重建 → 回 NORMAL（R6，含 blocker #2 修复）

**Files:** Modify `src/replay/core/receiver.py`（新增 `begin_locked_safe_resync` + resync confirm 成功清 locked_safe）、`src/replay/core/sender.py`（`adopt_epoch`）；Test `tests/test_locked_safe_recovery.py`

**要点：**
- **新增专用恢复入口（blocker #2）** `Receiver.begin_locked_safe_resync(self, rng, *, now_tick, ttl_ticks) -> Frame`：要求 `state.locked_safe`，显式创建 `ResyncPending(nonce_r="", trigger_counter=0, epoch=state.epoch[新], h_at_challenge=-1, ttl_ticks, expire_tick=now_tick+ttl_ticks)`，再调 `issue_resync_challenge` 产出 R2T challenge（counter=-1 占位 old_h、epoch=新）。**不复用** `verify_with_window` 的 resync 触发（LOCKED_SAFE 已在入口拒帧）。
- `process_resync_confirm` 成功（绑定新 epoch、`new_h=sender.tx_counter` 高位）→ `resync_commit_same_epoch` 重建 H、`locked_safe ← False`、回 NORMAL。
- **发送端 epoch 同步（blocker #4）** `Sender.adopt_epoch(self, new_epoch: int) -> None`：`self.current_epoch = new_epoch`（recovery 时由引擎显式调用；其后 `next_frame`/`begin_critical_intent` 用新 epoch）。
- 旧 epoch 的 resync confirm → 拒（R2/D7），保持 LOCKED_SAFE。
- **blocker 测试：**
  - `test_locked_safe_recovers_via_authenticated_resync`（R6：`begin_locked_safe_resync` → 新 epoch resync 成功 → `locked_safe=False`，之后正常收帧）。
  - `test_locked_safe_not_recovered_by_old_epoch_confirm`（R2/R6）。
  - `test_old_epoch_replay_rejected_after_recovery`（**关键**：recovery 完成回 NORMAL 后，旧 epoch normal+critical replay 仍被 epoch 守门拒——非仅 LOCKED_SAFE 中拒）。
  - `test_brownout_enters_locked_safe`（brownout=reboot 别名场景）。
**Step 5:** 提交 `feat: recover from LOCKED_SAFE via dedicated authenticated-resync entry into new epoch`。

### Task 4.4：Sender epoch 权威 + counter-lease（R5，含 blocker #3+#4 修复）

**Files:** Modify `src/replay/core/sender.py`、`src/replay/core/types.py`（lease 参数 / SimulationConfig `lease_reserve_size`）、`src/replay/core/experiment.py`（critical 帧改用 sender 自有 epoch，不再传 `receiver.state.epoch`）；Test `tests/test_sender_lease.py` + `tests/test_sender_epoch.py`

**要点（epoch 权威，blocker #4）：**
- `Sender` 加 `current_epoch: int = 0`、`nvm_epoch: int = 0`。`next_frame`（HSW_CR normal）stamp `frame.epoch = self.current_epoch`。`begin_critical_intent` 从 `self.current_epoch` 取 epoch（**移除** engine 传入 receiver epoch 的 `epoch=` 实参——改默认取 sender 自有，或保留入参但默认 `self.current_epoch`；engine 两处调用点同步改为不偷读 receiver epoch）。
- `adopt_epoch` 见 Task 4.3。

**要点（counter-lease，blocker #3 正确算法）：**
- `Sender` 加 `nvm_ctr_reserve_high: int`、`reserve_size: int`、`boot_counter: int`。`begin_boot(self) -> None`（见 D6）：①`tx_counter = nvm_ctr_reserve_high`（烧旧段）②`nvm_ctr_reserve_high += reserve_size`（写 NVM）③`boot_counter += 1`。稳态 `next_frame` 中 `tx_counter` 逼近 `nvm_ctr_reserve_high` 时也扩容一次（非每帧）。
- kernel `epoch.py` 的 `next_lease`/`lease_ok` 作纯函数判定辅助。

- **blocker 测试：**
  - `test_counter_lease_never_reuses_across_boot`（R5：模拟崩溃前用到 10、NVM high=100 → `begin_boot()` 后下一帧 ctr **>100**，非 11、非 1）。
  - `test_lease_reserves_in_blocks_not_every_frame`（稳态仅临界扩容）。
  - `test_sender_stamps_current_epoch_on_normal_and_critical`（blocker #4：normal/critical 帧 epoch 取自 sender 自有 `current_epoch`）。
  - `test_adopt_epoch_updates_sender_epoch`（recovery 后 stamp 新 epoch）。
**Step 5:** 提交 `feat: add sender epoch authority and crash-safe counter-lease`。

### Task 4.5：引擎 reboot 注入接线（**D1–D6 确认后定稿**）

**Files:** Modify `src/replay/core/experiment.py`（两路径在 `reboot_at_legit_index` 处调 `receiver.reboot()` + `sender.begin_boot()`，随后 legit 帧若遇 LOCKED_SAFE 触发认证 resync 重建，仿 `_resolve_resync`/`_resolve_critical`）、`src/replay/core/trace.py`（若 reboot 注入需信道决策则**末尾抽取**）；Test `tests/test_reboot_engine.py`

**做法骨架（Option A，仿 Phase 2/3 子泵）：**
1. 主循环到 `index == reboot_at_legit_index` 时注入一次 reboot：`receiver.reboot()`（bump epoch、清易失态、`locked_safe=True`）+ `sender.begin_boot()`（烧旧 lease）。
2. **恢复子泵**：reboot 后引擎调 `receiver.begin_locked_safe_resync(rng, now_tick, ttl)` 取 challenge → `sender.respond_resync_challenge` → `receiver.process_resync_confirm`；成功后 `sender.adopt_epoch(receiver.state.epoch)`（一次性显式同步，非每帧偷读）→ `locked_safe=False` → 后续 legit 正常。失败（丢包/TTL）→ 保持 LOCKED_SAFE，本轮后续帧被拒。
3. critical 帧的 `begin_critical_intent` 用 **sender 自有 epoch**（Task 4.4），engine 不再传 `receiver.state.epoch`。
4. attacker 在 reboot 后重放**旧 epoch** 帧 → 被 epoch 守门拒（R2/D7），`attack_success` 不增。
5. **不动指标口径**（R7）；非 HSW_CR 模式不注入 reboot（`reboot_at_legit_index=None`）→ STABLE_MODES 零漂移。

**测试规格：**
- `test_hsw_cr_reboot_then_recover_resumes_traffic`（reboot → LOCKED_SAFE → resync 重建 → 后续 legit 正常 accept）。
- `test_replayed_old_epoch_frame_after_reboot_does_not_commit`（R1/R2：reboot 后重放旧帧 → attack_success==0）。
- `test_baseline_stable_modes_unchanged_with_reboot_engine`（STABLE_MODES 逐值不变）。
**Step 5:** 提交 `feat: wire receiver reboot + LOCKED_SAFE recovery into engine (both paths)`。

### Task 4.6：契约/指标同步（**仅新增观测计数，不改归因口径——R7**）

**Files:** Modify `src/replay/core/cost.py`（`reboots/locked_safe_rejects/epoch_recoveries` 计数）、`src/replay/core/types.py`（`SimulationRunResult` + `AggregateStats` + **`as_dict()`**）、`src/replay/core/experiment.py`（两处填充 + `_aggregate_results` 汇总）、`src/replay/contracts/models.py`（+`from_aggregate`）、`src/replay/contracts/typescript.py`、`web/scripts/check-contracts.mjs`、**`web/lib/static-simulator.ts`（blocker #5：补默认 counters，否则 web build 炸——Phase 3 已被此坑打过，见 commit `b6dc2fb`）**、必要时 `web/components/simulator-panel.tsx` 默认 spec 字段；Test `tests/test_contract_reboot_metrics.py`（含 `as_dict` 导出面断言）。重生成 `web/lib/contracts.ts`/`web/public/data/contracts.json`。

**做法：** 同 Phase 3 Task 3.6 **六段**导出面全贯通（`SimulationRunResult → AggregateStats → as_dict() → Pydantic → TS/json → web static fallback`），测试必须含 `AggregateStats.as_dict()` 暴露断言。**这些是中性观测计数（发生了几次 reboot / 几次 locked_safe 拒绝 / 几次 epoch 重建），不触碰 `attack_success`/`legit_accepted` 归因（R7）。**
**Step 5（gate 必含 `cd web && npm run test:contracts && npm run build` 双绿）：** 提交 `feat: expose reboot/locked-safe observability counters in contracts and TS`。

> **Phase 4 门（用 @superpowers:verification-before-completion 核验）：**
> - blocker 全绿：`test_reboot_bumps_epoch_and_enters_locked_safe`、`test_reboot_clears_pending_tables`、`test_old_epoch_frame_rejected_by_explicit_gate`、`test_locked_safe_rejects_normal_and_critical`、`test_locked_safe_recovers_via_authenticated_resync`、`test_old_epoch_replay_rejected_after_recovery`（recovery 后仍拒）、`test_counter_lease_never_reuses_across_boot`、`test_sender_stamps_current_epoch_on_normal_and_critical`、`test_replayed_old_epoch_frame_after_reboot_does_not_commit`
> - epoch/reboot/locked-safe/lease/sender-epoch 单元 + 引擎集成全绿
> - `test_engine_baseline_regression`(STABLE_MODES) 逐值相等
> - 全量 pytest 绿 + ruff/mypy 不退化 + **`cd web && npm run test:contracts && npm run build` 双绿（blocker #5：web static fallback 也补全）**
> - **R7 复核**：grep 确认未改 `attack_success`/`legit_accepted` 归因逻辑；reboot 引出的任何归因疑问只作 known boundary 记录。

---

## 执行建议

- 顺序：4.0（kernel）→ 4.1（state）→ 4.2（reboot+LOCKED_SAFE 闸门）→ 4.3（recovery）→ 4.4（lease）→ **【确认 D1–D6】** → 4.5（引擎接线）→ 4.6（契约观测计数）。
- 4.0–4.4 歧义低/中，确认前即可开工；**4.5 必须等 D1–D6 拍板后再写逐行**（与 Phase 2/3 同理）。
- 每个 Task 后跑 `test_engine_baseline_regression`(STABLE_MODES) 自查——非 HSW_CR 模式任何漂移立即停下排查。
- **带入 Phase 2/3 三个教训**：(a) confirm/恢复路径加 epoch/counter 不变量防回退；(b) 指标 `as_dict()` 导出面别漏；(c) **不顺手改攻击归因口径（R7）**——Phase 3 known boundary 与本 Phase 的 reboot 归因都留给单独 metrics phase。
- Phase 4 门绿后，单独建计划做 G5/G9（Policy Table + 三 Profile）或 Phase 5（adaptive 攻击者 + 闭式模型）。
