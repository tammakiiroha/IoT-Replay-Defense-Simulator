# HSW-CR Phase 2 · Authenticated Resync 状态机 — 逐行 TDD 实施计划

> **For Claude:** REQUIRED SUB-SKILL: 用 `superpowers:executing-plans` 逐任务实施本计划。
> 本文件是主计划 `docs/plans/2026-06-07-hsw-cr-full-protocol-overhaul.md` §4.3 的执行细化（对照 Phase 0/1/1.5 落地后的真实代码展开）。**执行前先确认下方"待拍板的关键设计决策"。**

**Goal:** 实现 G2「Authenticated Resync 状态机」：MAC 有效但前跳 > G_hard 时进入 RESYNC_PENDING，经反向 `R→T` 信道完成 challenge/confirm 往返，验证通过后**仅更新 (epoch, H, M_W)、不执行触发命令（H1）、整窗封死被跳过的 counter（H2）**。

**Architecture:** kernel 加纯函数 `resync_commit`（同 epoch 封窗 / epoch bump）；`ReceiverState` 加 `epoch` + `resync_pending`；receiver 在 resync 触发点改为「生成 nonce_R + 进 PENDING + 产出 RESYNC_CHALLENGE（R2T）」，并新增 RESYNC_CONFIRM 验证→封窗提交；引擎用 Phase 1.5 的 `EventScheduler` R2T 队列泵动往返 + sender 侧 confirm 应答；TTL 超时清 pending。engine 与 protocol 共用同一 kernel 状态机。

**Tech Stack:** Python 3.9+、`EventScheduler`(`Direction.R2T`/TTL)、`mac_domains.resync_confirm_tag`、pytest。环境：`.venv/bin/python`，`PYTHONPATH=src:.`，命令前若 cwd 漂移先 `cd /Users/romeitou/Desktop/論文/Replay`。

---

## 待拍板的关键设计决策（执行前必须确认）

Phase 2 不像 Phase 0/1 那样机械——有三处实质设计分叉，先定再写代码。下面是**推荐方案**：

### D1：引擎如何泵动 resync 往返？
- **推荐（Option A，承接 1.5 委托路线）**：在现有 `simulate_one_run` / `simulate_one_run_with_trace` 的 for 循环里加一个**有界 resync 子泵**——当 `receiver.process(legit_frame)` 返回 `resync_required` 且带回一个 RESYNC_CHALLENGE 时，引擎把它经 `EventScheduler` 的 R2T 队列送到"发送端"，sender 产出 RESYNC_CONFIRM 经 T2R/反向送回，receiver 验证并封窗。challenge/confirm 作为真实帧经历 loss/delay/TTL（§4.3 完整事件建模）。
- **不推荐（Option B）**：把整个 for 循环改成完全事件泵——更大重写，1.5 已明确推迟，Phase 2 非必需。
- **代价**：Option A 下，resync 往返被建模为"在触发帧那一步内有界解算"，而非与后续 legit 帧任意交错。对论文要的 p_loss/TTL 敏感性足够；若未来要建模"resync 进行中又来新 legit 帧"的并发，再升级。

### D2：nonce_R / tick / RNG 归属？
- **推荐（定稿）**：receiver 拥有 resync 簿记（生成 `nonce_R`、记 pending、验证 confirm），但**不自己推进 tick / 不持有信道 RNG**——`tick`/`rng` 由引擎注入。两个**专用入口**，`process(frame)` 一字不改（非 resync 模式回归零影响）：
  - `receiver.issue_resync_challenge(rng, *, now_tick, ttl_ticks) -> Frame`（触发后由引擎调，生成挑战）。
  - `receiver.process_resync_confirm(frame, *, now_tick) -> VerificationResult`（引擎对 `flags==FLAG_RESYNC_CONFIRM` 的帧只调这个；confirm 验证所需的 `now_tick` 走这里注入，解决"`process(frame)` 不带 tick 却要验 TTL"的矛盾）。
- 备选：扩 `process(frame, *, tick, rng)` 或让 `process` dispatch confirm——侵入面更大、且 `process` 拿不到 tick，**否决**。

### D3：触发命令与 step-6 重发的指标语义？
- **推荐（定稿）**：触发 resync 的那一帧**计入 `legit_sent`、不计入 `legit_accepted`**（reason=`resync_required`，符合 H1 不执行）。**精确口径**：`legit_sent` 在"发送"时自增（现状如此），与是否被接受无关，所以触发帧天然进分母；`legit_accepted` 仅在 `result.accepted` 时自增，触发帧不进分子 → **LAR 分母不被改坏**。
- step-6"T 用新 ctr 重发"在批量引擎里**不显式重发**——后续 legit 帧自然走正常接受；resync 成功只体现为"窗口已重建，后续新帧可被接受"。
- 新增计数 `resync_initiated` / `resync_completed` / `resync_timeout` 进 `CostStats`/结果 metadata 供论文分析。
- 这样**非 resync 模式数值完全不变**，只有 `SW_RESYNC`/`HSW_CR` 在前跳越闸场景出现新行为（其旧 baseline 值会按设计改变，见 Task 2.4 回归拆分）。

> **请确认 D1=A、D2=receiver 簿记+引擎注入、D3=不显式重发+计数指标。** 确认后我再把 Task 2.4（引擎接线）的逐行代码定稿（其余 Task 现在即可执行）。

---

## 范围决策（Phase 2 做什么 / 不做什么）

- **做**：同 epoch 的 6 步 Authenticated Resync（§4.3）+ H1/H2 + TTL 超时 + CONFIRM 失败处理；`ReceiverState.epoch` 字段；kernel `resync_commit`（同 epoch 封窗）+ `epoch_bump` 原语；3 个 blocker test。
- **不做（留后续 Phase）**：Critical 两阶段提交（G3 → Phase 3）；§4.5 PendingUserIntent 防 challenge 洗白（Phase 3）；§4.6 完整 reboot / LOCKED_SAFE / counter-lease（Phase 4；本 Phase 仅落 `epoch_bump` 纯原语 + `epoch` 字段，不接 reboot 流程）；wire format / protocol 层（后续）。
- 契约层：`SW_RESYNC` 已在 Phase 1 贯通；Phase 2 若新增结果指标（`resync_*` 计数）需同步 `SimulationResultRecord` + TS + check-contracts（Task 2.6）。

> **硬约束（贯穿）：**
> 1. **H1**：RESYNC_CONFIRM 通过 ⇒ 只 `update(epoch,H,M_W)`，**绝不执行触发命令**。
> 2. **H2**：同 epoch 封窗 `M_W=[1]*W`（不是清零）——封窗后旧 in-window 帧（如 ctr=198，new_H=200）必须被拒。
> 3. **MAC-before-everything**：RESYNC_CONFIRM 先验 `resync_confirm_tag`，再验 nonce/epoch/ttl；任一不过 → 丢弃、保持 PENDING（不污染状态）。
> 4. **回归零影响**：非 resync 模式（NO_DEFENSE/ROLLING/WINDOW/OSCORE/CHALLENGE）数值与 `engine_baseline.json` 逐值不变；`WINDOW` 纯 baseline 前跳越闸仍 `ACCEPT_FORWARD`（不触发 resync）。
> 引用 @superpowers:test-driven-development、@superpowers:verification-before-completion。

---

## 当前形态速查（细化所依据的真实代码）

- `src/replay/core/kernel/window_commit.py`：`window_commit(n,h,mask,w)`（list bitmap，§8.6-3）。
- `src/replay/core/kernel/acceptance.py`：`SwDecision`/`classify` + `needs_resync(n,h,g_hard)`。
- `src/replay/core/kernel/mac_domains.py`：`resync_confirm_tag(key, dev_id, key_id, old_epoch, new_epoch, old_h, new_h, nonce_r, ttl, flags) -> str`。
- `src/replay/core/scheduler.py`：`EventScheduler` + `Direction.T2R/R2T` + `submit(...,expire_tick=)` + `pop_due(direction=)` + `expired_count(direction=)`。
- `src/replay/core/receiver.py`：`verify_with_window` 在 `enable_resync and needs_resync(...)` 时 `return VerificationResult(False, "resync_required", state)`（**当前占位：不改状态、不发挑战**）。`VerificationResult(accepted, reason, state)`。dispatch 用 `WINDOW_VERIFY_MODES`，`SW_RESYNC`→`enable_resync=True`，`HSW_CR` 经 `verify_hsw_cr` 低风险路径 `enable_resync=True`。
- `src/replay/core/types.py`：`Frame` 有 `dev_id/key_id/epoch/flags/payload`；`ReceiverState{last_counter, expected_nonce, received_mask, outstanding_nonces, used_nonces}`（**无 epoch / 无 resync_pending**）；`SimulationConfig.g_hard`。
- `src/replay/core/experiment.py`：`simulate_one_run`（Channel）/`simulate_one_run_with_trace`（trace），均 `process_arrived(...)` 调 `receiver.process`。
- 回归安全网：`tests/fixtures/engine_baseline.json` + `tests/test_engine_baseline_regression.py`（改动后必须仍逐值相等）。

---

## Phase 2 · Tasks

> 门：3 个 blocker test 绿 + resync 单元/集成测试绿 + `test_engine_baseline_regression` 仍逐值相等（非 resync 模式零漂移）+ 全量 pytest 绿 + ruff/mypy 不退化 + check-contracts 绿。

### Task 2.0：kernel `resync_commit`（同 epoch 封窗 + epoch bump 原语，纯函数）

**Files:** Create `src/replay/core/kernel/resync_commit.py`；Test `tests/test_kernel_resync_commit.py`

**Step 1: 失败测试**
```python
# tests/test_kernel_resync_commit.py
from replay.core.kernel.resync_commit import epoch_bump, resync_commit_same_epoch


def test_same_epoch_seals_full_window():
    # H2：同 epoch resync -> H=new_h，整窗封死（全 1）
    new_h, mask = resync_commit_same_epoch(200, 5)
    assert new_h == 200
    assert mask == [1, 1, 1, 1, 1]


def test_epoch_bump_resets_window():
    # reboot/brownout：epoch+1，H=new_h，M_W 清零（新窗口）
    e, h, mask = epoch_bump(old_epoch=1, new_h=0, w=5)
    assert e == 2
    assert h == 0
    assert mask == [0, 0, 0, 0, 0]
```

**Step 2:** 跑红：`cd /Users/romeitou/Desktop/論文/Replay && PYTHONPATH=src:. .venv/bin/python -m pytest tests/test_kernel_resync_commit.py -q` → ModuleNotFoundError。

**Step 3: 实现**
```python
# src/replay/core/kernel/resync_commit.py
"""Resync 提交原语（§4.3）：同 epoch 封窗（H2）与 reboot epoch bump。纯函数，engine/protocol 共用。"""
from __future__ import annotations


def resync_commit_same_epoch(new_h: int, w: int) -> tuple[int, list[int]]:
    """同 epoch 重同步提交：H←new_h，整窗封死 M_W[d]=1 ∀d（§4.3 H2）。
    封窗后只有 ctr>new_h 的新帧可被接受；旧 in-window 帧被判 dup 拒绝。"""
    return new_h, [1] * w


def epoch_bump(old_epoch: int, new_h: int, w: int) -> tuple[int, int, list[int]]:
    """reboot/brownout 强重同步：epoch←old+1，H←new_h，M_W 清零（旧 epoch 帧由调用方全拒）。"""
    return old_epoch + 1, new_h, [0] * w
```

**Step 4:** 跑绿 + `ruff check src/replay/core/kernel/resync_commit.py tests/test_kernel_resync_commit.py` + `mypy src`。
**Step 5:** 提交 `feat: add resync_commit kernel primitives (seal window / epoch bump)`。

### Task 2.1：`ReceiverState` 加 `epoch` + `ResyncPending`（新字段，默认向后兼容）

**Files:** Modify `src/replay/core/types.py`（`ReceiverState` + 新 `ResyncPending`）；Test `tests/test_resync_state.py`

**Step 1: 失败测试**
```python
# tests/test_resync_state.py
from replay.core.types import ResyncPending
from sim.types import ReceiverState


def test_receiver_state_defaults_epoch_zero_no_pending():
    s = ReceiverState()
    assert s.epoch == 0
    assert s.resync_pending is None


def test_resync_pending_holds_challenge_context():
    p = ResyncPending(
        nonce_r="ab", trigger_counter=200, epoch=1, h_at_challenge=10,
        ttl_ticks=20, expire_tick=42,
    )
    assert p.nonce_r == "ab" and p.trigger_counter == 200
    assert p.epoch == 1 and p.h_at_challenge == 10
    assert p.ttl_ticks == 20 and p.expire_tick == 42
```

**Step 2:** 跑红（`AttributeError: epoch` / `ImportError: ResyncPending`）。

**Step 3: 实现**（在 `types.py` `ReceiverState` 之前加 `ResyncPending`，并扩 `ReceiverState`）
```python
@dataclass
class ResyncPending:
    """RESYNC_PENDING 期间的挑战上下文（§4.3 step 2-3）。"""
    nonce_r: str
    trigger_counter: int      # 触发 resync 的 ctr（供 step-6 / 指标）
    epoch: int                # 发挑战时的 epoch
    h_at_challenge: int       # 发挑战时的 H（confirm tag 的 old_h）
    ttl_ticks: int            # TTL（绑进 resync_confirm_tag，两侧必须一致）
    expire_tick: int          # TTL 截止 tick = issued_tick + ttl_ticks

@dataclass
class ReceiverState:
    last_counter: int = -1
    expected_nonce: str | None = None
    received_mask: list[int] = field(default_factory=list)
    outstanding_nonces: dict[str, int] = field(default_factory=dict)
    used_nonces: set[str] = field(default_factory=set)
    epoch: int = 0
    resync_pending: ResyncPending | None = None
```

**Step 4:** 跑绿 + 全量回归（确认 `ReceiverState()` 各处构造未破坏）+ ruff/mypy。
**Step 5:** 提交 `feat: extend ReceiverState with epoch and ResyncPending`。

### Task 2.2：receiver 触发 RESYNC_CHALLENGE（进 PENDING，不改窗口）

> 把当前 `resync_required` 占位升级为：生成 `nonce_R`、记 `resync_pending`、产出一个 R2T RESYNC_CHALLENGE 帧；**(H1) 不改 (H,M_W)、不执行命令**。挑战的 nonce/tick 由引擎注入（D2）。

**Files:** Modify `src/replay/core/receiver.py`（新增 `issue_resync_challenge`；`verify_with_window` 触发分支记 pending）、`src/replay/core/types.py`（`Frame` 帧类型常量）；Test `tests/test_resync_trigger.py`

**Step 1: 失败测试（行为规格）**
```python
# tests/test_resync_trigger.py
import random

from sim.receiver import Receiver
from sim.security import compute_mac
from sim.types import Frame, Mode

KEY = "test_key"; MAC_LEN = 8


def _frame(ctr, command="CMD"):
    return Frame(command=command, counter=ctr, mac=compute_mac(ctr, command, KEY, MAC_LEN))


def _recv():
    return Receiver(Mode.SW_RESYNC, shared_key=KEY, mac_length=MAC_LEN, window_size=5, g_hard=8)


def test_trigger_enters_pending_without_window_mutation():
    r = _recv()
    r.process(_frame(10))                      # H=10
    before_h, before_mask = r.state.last_counter, list(r.state.received_mask)
    res = r.process(_frame(100))               # jump=90 > g_hard -> resync_required
    assert not res.accepted and res.reason == "resync_required"
    assert r.state.last_counter == before_h          # H1：状态未变
    assert r.state.received_mask == before_mask
    assert r.state.resync_pending is not None         # 进 PENDING
    assert r.state.resync_pending.trigger_counter == 100


def test_issue_resync_challenge_emits_r2t_frame_with_nonce_and_ttl():
    r = _recv()
    r.process(_frame(10))
    r.process(_frame(100))                     # 进 pending
    challenge = r.issue_resync_challenge(random.Random(0), now_tick=5, ttl_ticks=20)
    assert challenge.flags == Frame.FLAG_RESYNC_CHALLENGE
    assert challenge.ttl == 20                            # 同一 TTL 必须随挑战带给 sender
    assert challenge.counter == 10                        # 携带 receiver 当前 H（old_h）
    assert r.state.resync_pending.nonce_r == challenge.nonce
    assert r.state.resync_pending.ttl_ticks == 20
    assert r.state.resync_pending.expire_tick == 25     # 固化 issued_tick(=now_tick) + ttl_ticks
```

**Step 2:** 跑红。

**Step 3: 实现要点**
- `types.py`：(a) `Frame` 加帧类型常量（class 级）：`FLAG_NORMAL_REQ=0`、`FLAG_RESYNC_CHALLENGE=3`、`FLAG_RESYNC_CONFIRM=4`（与主计划 §3.3 flags 语义对齐；critical prepare/confirm 留给 Phase 3）。(b) `Frame` 加字段 `ttl: int = 0`（默认 0 向后兼容；用于 challenge/confirm 携带同一 TTL，使两侧 `resync_confirm_tag` 输入一致），并更新 `clone()` 复制 `ttl`。
- `receiver.py` `verify_with_window` 触发分支：MAC 已过 + `needs_resync` 真 → **若已 PENDING 则直接 `resync_required`（不重复建 pending）**；否则建占位 pending `ResyncPending(nonce_r="", trigger_counter=frame.counter, epoch=state.epoch, h_at_challenge=state.last_counter, ttl_ticks=0, expire_tick=-1)`（nonce/ttl/expire 待 `issue_resync_challenge` 填），返回 `resync_required`。**不调 window_commit**。
- `receiver.py` 新增 `issue_resync_challenge(self, rng, *, now_tick, ttl_ticks) -> Frame`：要求当前有 `resync_pending`；用 rng 生成 `nonce_r`（复用 `issue_nonce` 的 hex 生成风格）；**回填 `pending.nonce_r`、`pending.ttl_ticks = ttl_ticks`、`pending.expire_tick = now_tick + ttl_ticks`**；返回 `Frame(command="RESYNC_CHALLENGE", flags=Frame.FLAG_RESYNC_CHALLENGE, nonce=nonce_r, epoch=state.epoch, counter=state.last_counter, ttl=ttl_ticks, dev_id=..., key_id=...)`（R2T 帧：`counter`=receiver 当前 H（=confirm 的 `old_h`）、`epoch`=当前 epoch、`ttl`=TTL，供 sender 构造 confirm tag）。

**Step 4:** 跑绿 + 回归（baseline 仍逐值相等；`WINDOW` 纯模式不受影响）+ ruff/mypy。
**Step 5:** 提交 `feat: receiver enters RESYNC_PENDING and emits RESYNC_CHALLENGE`。

### Task 2.3：RESYNC_CONFIRM 验证 + 封窗提交（H1/H2）

> receiver 收到 `flags==FLAG_RESYNC_CONFIRM` 的帧时：① 验 `resync_confirm_tag` ② 验 nonce_R 匹配 pending ③ 验 epoch ④ 验 ttl（current_tick ≤ expire_tick）⑤ 全过 → `resync_commit_same_epoch(new_h, W)` 封窗、清 pending、**不执行命令**；任一不过 → 丢弃、保持 PENDING。

**Files:** Modify `src/replay/core/receiver.py`（`Receiver.process` dispatch 识别 CONFIRM；新增 `verify_resync_confirm`）；Test `tests/test_resync_confirm.py`（含 3 个 blocker test 的 2 个）

**Step 1: 失败测试（blocker + 异常，命名对齐主计划 §4.3）**
```python
# tests/test_resync_confirm.py 要点：
# 工具：构造 nonce/epoch/new_h/ttl 与 pending 匹配、tag 由 resync_confirm_tag 合法生成的 CONFIRM 帧。
#
# test_resync_confirm_does_not_execute_original_command (H1)：
#   confirm 通过后 res.accepted is False（reason=="resync_committed"，不计 legit）；
#   "命令未执行"通过"封窗后该 ctr 区间判 dup"间接验证。
# test_resync_seals_skipped_window_counters (H2)：
#   confirm(new_h=200) 后 state.received_mask == [1]*W 且 last_counter==200。
# test_old_in_window_frame_rejected_after_resync (H2)：
#   confirm(new_h=200) 后 process(_frame(198)) -> not accepted（封窗 dup/old）。
# test_bad_mac_confirm_keeps_pending：篡改 tag -> 丢弃；resync_pending 仍非 None；窗口未变。
# test_wrong_nonce_confirm_keeps_pending / test_expired_confirm_clears_pending 同理。
```

**Step 2:** 跑红。

**Step 3: 实现要点**
- **专用入口（D2 定稿）**：`Receiver.process(frame)` **不改**、不识别 confirm。新增 `Receiver.process_resync_confirm(self, frame, *, now_tick) -> VerificationResult`，引擎对 `flags==FLAG_RESYNC_CONFIRM` 的帧只调它（仅 `SW_RESYNC`/`HSW_CR` 模式有效；其余模式 → `VerificationResult(False, "unexpected_resync_confirm", state)`）。`now_tick` 经此入口注入，解决 `process` 无 tick 却要验 TTL 的矛盾。
- `process_resync_confirm` 验证顺序（**MAC-before-everything 修正：先 MAC，TTL 最后；失败保持 pending，仅 TTL 过期清 pending**）：
  ```
  pending = state.resync_pending
  if pending is None:
      return (False, "resync_no_pending")
  # ① 先常量时间验 tag（用 pending 固化的 old_h/old_epoch/ttl_ticks；new_h/new_epoch 取自 confirm 帧）
  expected = resync_confirm_tag(key, frame.dev_id, frame.key_id,
                                pending.epoch, frame.epoch,
                                pending.h_at_challenge, frame.counter,
                                pending.nonce_r, pending.ttl_ticks, frame.flags)
  if frame.mac is None or not constant_time_compare(frame.mac, expected):
      return (False, "mac_mismatch")            # 保持 PENDING
  # ② nonce ③ epoch（同 epoch 路径）
  if frame.nonce != pending.nonce_r:
      return (False, "resync_nonce_mismatch")   # 保持 PENDING
  if frame.epoch != pending.epoch:
      return (False, "resync_epoch_mismatch")   # 保持 PENDING
  # ④ counter 不变量（防状态回退，§4.3 confirm 验 ctr）：new_h 必须覆盖触发 counter
  if frame.counter < pending.trigger_counter:
      return (False, "resync_counter_mismatch") # 保持 PENDING；否则 new_h=11 会把 H 从 10 改成 11
  # ⑤ TTL 最后：仅过期才清 pending
  if now_tick > pending.expire_tick:
      state.resync_pending = None
      return (False, "resync_ttl_expired")
  # ⑥ 全过 → 封窗提交（H2），不执行命令（H1）
  new_h = frame.counter   # = sender.tx_counter（见 Task 2.4 D5），confirm 携带商定的 new_H
  state.last_counter, state.received_mask = resync_commit_same_epoch(new_h, W)
  state.resync_pending = None
  return (False, "resync_committed")            # H1：accepted=False（不计 legit、不执行命令）
  ```
  （MAC tag 用 `pending.nonce_r`/`pending.h_at_challenge`/`pending.ttl_ticks` 这些 receiver 侧权威值，攻击者无 key 无法伪造；nonce/epoch 字段再做一致性双保险。）

**Step 4:** 跑绿（confirm/seal/old-frame + 异常保持/清 pending）+ 回归 + ruff/mypy。
**Step 5:** 提交 `feat: verify RESYNC_CONFIRM and seal window (H1/H2)`。

### Task 2.4：引擎接线——反向往返泵 + sender confirm 应答（**D1/D2/D3 确认后定稿**）

> 把 Task 2.2/2.3 的能力接入 `simulate_one_run` 与 `simulate_one_run_with_trace`（共用 helper），用 `EventScheduler` R2T 队列建模 challenge→confirm 往返，经历 loss/delay/TTL。**先确认 D1=A / D2 / D3 再写逐行。**

**Files:** Modify `src/replay/core/experiment.py`（两路径共用 `_resolve_resync(...)` helper）、`src/replay/core/sender.py`（`Sender.respond_resync_challenge(challenge) -> Frame`）、`src/replay/core/cost.py`（`CostStats` 加 `resync_initiated/resync_completed/resync_timeout`）、`src/replay/core/trace.py`（`ScenarioTrace` 加 resync 信道 drop/delay 序列，paired 确定性）、`src/replay/core/types.py`（`SimulationConfig` 加 `resync_ttl_ticks: int = 16`、`resync_rtt_ticks: int = 1` 两个旋钮，默认值；若需透出到 API/Web 则随 Task 2.6 进契约，否则仅 runtime config）、`tests/test_engine_baseline_regression.py`（回归拆分 STABLE_MODES）；Test `tests/test_resync_engine.py`

**测试规格（行为，非逐行）：**
- `test_sw_resync_recovers_after_forward_jump`：固定 seed，`SW_RESYNC` 注入前跳越闸 legit 帧；challenge/confirm 无损往返后**后续新 ctr 帧被接受**（窗口已重建），`resync_completed==1`、触发帧不计 legit。
- `test_resync_confirm_lost_times_out`：confirm 被信道丢弃 → TTL 到期 → `resync_timeout==1`、pending 清空、回 NORMAL。
- `test_attacker_cannot_forge_resync_confirm`：攻击者注入伪 CONFIRM（无正确 key）→ `mac_mismatch`、不封窗、不提升 H。
- `test_baseline_modes_unchanged_with_resync_engine`：复跑 `engine_baseline.json` 对应配置，非 resync 模式逐值不变（D3 零影响验证）。

**做法骨架（Option A）：**
1. `process_arrived` 中某 legit 帧得 `resync_required` 且现处 PENDING → `challenge = receiver.issue_resync_challenge(rng, now_tick=now_tick, ttl_ticks=cfg.resync_ttl_ticks)`；经反向信道送出（经历 loss/delay）。**幂等守卫**：`issue_resync_challenge` 已实现"仅首次签发、之后重发同一挑战"（见 Task 2.2 修复），故子泵**只在首次进 PENDING（`pending.nonce_r == ""`）时 `cost_stats.resync_initiated += 1` 并真正发出**；in-flight 期间后到的远跳帧不重新签发、不重置 TTL、不计数。
2. 信道交付 challenge（未丢/未过 TTL）→ `confirm = sender.respond_resync_challenge(challenge)` → 经信道送回 → 引擎调 `receiver.process_resync_confirm(confirm, now_tick=now_tick')`。
3. `resync_committed` → `resync_completed += 1`（窗口已重建）；challenge 或 confirm 被丢弃 / `now_tick > expire_tick` → `resync_timeout += 1`，pending 按 TTL 清空、回 NORMAL。
4. **不显式重发触发命令（D3）**；后续 legit 帧自然走正常接受。

**D5 定稿 —— `Sender.respond_resync_challenge(self, challenge) -> Frame`：**
```
# challenge.counter = receiver 当前 H（old_h）；绝不能拿它当 new_h。
old_h     = challenge.counter
new_h     = self.tx_counter          # ★ new_h 取发送端自己的当前 counter，不是 challenge.counter
epoch     = challenge.epoch          # 同 epoch 路径：old_epoch == new_epoch == challenge.epoch
nonce_r   = challenge.nonce
ttl       = challenge.ttl            # 用挑战携带的同一 TTL（保证两侧 tag 输入一致）
tag = resync_confirm_tag(K, self.dev_id, self.key_id, epoch, epoch, old_h, new_h, nonce_r, ttl,
                         Frame.FLAG_RESYNC_CONFIRM)
return Frame(command="RESYNC_CONFIRM", flags=Frame.FLAG_RESYNC_CONFIRM,
             counter=new_h, epoch=epoch, nonce=nonce_r, ttl=ttl, mac=tag)
```
> 接收端 `process_resync_confirm` 验 tag 时用 `pending.h_at_challenge`(=old_h)、`pending.ttl_ticks`(=ttl)、`pending.nonce_r`、`pending.epoch`，并取 `new_h = confirm.counter`(=sender.tx_counter)。两侧 tag 输入逐项对齐才会通过。

**paired trace 路径的 resync 信道来源（修审查：不得临时用 live RNG）：**
- `ScenarioTrace` 增 resync 专用确定性序列：`resync_challenge_dropped: list[bool]`、`resync_challenge_delay: list[int]`、`resync_confirm_dropped: list[bool]`、`resync_confirm_delay: list[int]`（按"resync 尝试序号"索引）。
- 在 `generate_trace` 中，这些序列的 RNG 抽取**追加在所有现有抽取之后**（末尾），从而**不改动现有数组的抽取顺序** → 非 resync 模式 paired 数值逐字节不变（同 Phase 1.5 的 append 技巧）。长度按 `num_legit`（resync 尝试上界）预生成。
- live 路径（`simulate_one_run`）仍用 `Channel` 的 rng 掷 challenge/confirm 的 loss/delay（与正向帧同源，合法）。

**回归拆分（关键，否则 Phase 2 必然"破"基线）：**
- `engine_baseline.json` 是 Phase 1.5 冻结的——那时 `SW_RESYNC`/`HSW_CR` 的 resync 只是 reject 占位。Phase 2 让它们真正往返，**这两个 mode 的数值按设计改变**。
- 改 `tests/test_engine_baseline_regression.py`：把断言限定到 `STABLE_MODES = [NO_DEFENSE, ROLLING_MAC, WINDOW, CHALLENGE, OSCORE_LIKE]`（**剔除 SW_RESYNC/HSW_CR**），并加注释说明原因。`SW_RESYNC`/`HSW_CR` 的新行为由 `tests/test_resync_engine.py` 专门覆盖，**不再**对照冻结基线。
- `test_baseline_modes_unchanged_with_resync_engine` 即断言上述 `STABLE_MODES` 子集逐值不变（D3 零影响验证的落点）。

**Step 5:** 提交 `feat: wire authenticated resync round-trip through reverse channel`。

### Task 2.5：TTL 超时清 pending（确定性单测，锁死异常路径）

**Files:** Test `tests/test_resync_timeout.py`（必要时小改 `receiver.py` 暴露"按 tick 清 pending"入口）

**测试规格：** 进入 PENDING 后，喂 `current_tick > expire_tick` 的事件/帧 → `resync_pending` 清为 None、回 NORMAL、计 `resync_timeout`；TTL 内 confirm 仍成功（边界 `current_tick == expire_tick` 视为未过期，与 scheduler TTL 语义一致）。

**Step 5:** 提交 `test: lock resync TTL timeout and pending cleanup`。

### Task 2.6：契约/指标同步（若 Task 2.4 新增 `resync_*` 结果指标）

**Files:** Modify `src/replay/contracts/models.py`（`SimulationResultRecord` 加 `resync_initiated/resync_completed/resync_timeout`）、`src/replay/contracts/typescript.py`（同步 TS interface）、`web/scripts/check-contracts.mjs`（断言新字段）、`src/replay/core/experiment.py` `_aggregate_results`（聚合）；Test `tests/test_contract_resync_metrics.py`

**做法：** 同 Phase 1 Task 1.4——契约加字段 → aggregate 传递 → 手改 TS 模板 → 重生成 `contracts.ts`/`contracts.json` → check-contracts 断言。
**Step 5:** 提交 `feat: expose resync counters in contracts and TS`。

> **Phase 2 门（用 @superpowers:verification-before-completion 核验）：**
> - 3 个 blocker test 绿：`test_resync_confirm_does_not_execute_original_command`、`test_resync_seals_skipped_window_counters`、`test_old_in_window_frame_rejected_after_resync`
> - resync 单元（kernel/state/trigger/confirm/timeout）+ 引擎集成（恢复/超时/攻击者伪造）全绿
> - `test_engine_baseline_regression` 仍逐值相等（非 resync 模式零漂移）
> - 全量 pytest 绿 + ruff/mypy 不退化 + check-contracts 绿

---

## 执行建议

- 顺序：2.0（kernel）→ 2.1（state）→ 2.2（trigger）→ 2.3（confirm/封窗）→ **【确认 D1/D2/D3】** → 2.4（引擎接线）→ 2.5（TTL）→ 2.6（契约指标）。
- 2.0–2.3 是纯/半纯逻辑，歧义低，确认决策前即可开工；**2.4 必须等 D1/D2/D3 拍板后再写逐行**（与 Phase 1.5 等前置 Phase 落地后再细化同理）。
- 每个 Task 后跑 `test_engine_baseline_regression` 自查——任何非 resync 模式数值漂移立即停下排查。
- Phase 2 门绿后，用 `superpowers:writing-plans` 细化 Phase 3（Critical 两阶段提交 + §4.5 PendingUserIntent 防 challenge 洗白）。
