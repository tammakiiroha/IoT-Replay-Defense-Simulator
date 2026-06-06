# HSW-CR Phase 3 · Critical 两阶段提交 + PendingUserIntent — 逐行 TDD 实施计划

> **For Claude:** REQUIRED SUB-SKILL: 用 `superpowers:executing-plans` 逐任务实施本计划。
> 本文件是主计划 `docs/plans/2026-06-07-hsw-cr-full-protocol-overhaul.md` §4.4 + §4.5 的执行细化（对照 Phase 0/1/1.5/2 落地后的真实代码展开）。**执行前先确认下方"待拍板的关键设计决策"。**

**Goal:** 实现 G3「Critical 两阶段提交」（prepare→challenge→confirm→commit，原子提交、仅执行一次、pending 表有界 N_p）+ §4.5「发送端 PendingUserIntent」防 challenge 洗白重放（攻击者重放旧 critical REQ 不能借真发送端完成 confirm）。

**Architecture:** kernel 加 `critical_commit` 原子提交原语；`ReceiverState` 加 `pending_critical`（有界字典）+ `committed_critical`（去重集）；`Sender` 加 `PendingUserIntent`；receiver 新增 prepare/confirm 两个专用入口（不动 `process`）；引擎用 Phase 2 同款"有界两阶段子泵"（承接 Option A 委托路线，复用 `EventScheduler` R2T）把 prepare→challenge→confirm→commit 接线。engine 与 protocol 共用同一 kernel commit 逻辑。

**Tech Stack:** Python 3.9+、`EventScheduler`(R2T/TTL)、`mac_domains.crit_prepare_tag`/`crit_confirm_tag`、`window_commit`、pytest。环境：`.venv/bin/python`，`PYTHONPATH=src:.`，命令前若 cwd 漂移先 `cd /Users/romeitou/Desktop/論文/Replay`。

---

## 待拍板的关键设计决策（执行前必须确认）

Phase 3 碰命令执行语义，比 Phase 2 更易引入"合法 challenge 替攻击者确认"漏洞。五处分叉，先定再写代码。下面是**推荐方案**：

### D1：引擎如何泵两阶段往返？
- **推荐（Option A，承接 Phase 2 委托路线）**：在 `simulate_one_run` / `simulate_one_run_with_trace` 的 for 循环里加**有界 critical 子泵**——prepare 帧被 receiver 受理（登记 pending、发 CHALLENGE）后，引擎经 R2T 把 CHALLENGE 送到 sender；sender 若**用户意图匹配**则产出 CONFIRM 经反向送回；receiver 验证后**原子 commit + 执行一次**。prepare/challenge/confirm 作为真实帧经历 loss/delay/TTL（与 Phase 2 resync 同源建模）。
- **不推荐**：全事件泵重写（同 Phase 2 理由，推迟）。
- **代价**：两阶段往返在触发 prepare 那一步内有界解算，不与后续帧任意交错（与 Phase 2 resync 一致）。

### D2：入口与 tick/rng 归属？
- **推荐**：`process(frame)` **不改**。新增专用入口：
  - `receiver.process_crit_prepare(frame, rng, *, now_tick) -> VerificationResult`（验 prepare、登记 pending、生成 nonce_id/nonce_R/ttl）。
  - `receiver.issue_crit_challenge(pid) -> Frame`（**challenge 交付**：从 `pending_critical[pid]` 取字段构造 R2T CHALLENGE 帧；幂等——重复调用返回同一挑战，不刷新 nonce/TTL）。引擎在 `process_crit_prepare` 返回 `critical_prepared` 后调它拿 CHALLENGE。
  - `receiver.process_crit_confirm(frame, *, now_tick) -> VerificationResult`（验 confirm、原子 commit）。
  - 引擎按 `frame.flags` 路由：`FLAG_CRIT_PREPARE` → prepare 入口；`FLAG_CRIT_CONFIRM` → confirm 入口；其余仍走 `process`。
- 备选：扩 `process(frame,*,tick,rng)` 或在 `process` 内 dispatch confirm（拿不到 tick）——否决。

### D3：§4.5 PendingUserIntent 在批量引擎里怎么建模？（**安全核心**）
- **推荐（修审查：必须绑定到本次自发 prepare 的完整身份，不能只 `(cmd, payload_hash)`）**：`Sender` 在**自己发起** critical 命令时，记录 `PendingUserIntent(epoch, ctr, cmd, payload_hash, pid, key_id, t_intent, consumed=False)`——其中 `pid = pid_for(epoch, ctr, cmd, payload_hash)`，即**与它这次发出的 PREPARE 完全一致**。`sender.confirm_critical_challenge(challenge, now_tick)` 仅当：
  1. challenge 的 **`pid` 等于该未消费 intent 的 `pid`**（等价于 `(epoch, ctr, cmd, payload_hash)` 全等——因 pid 由这四项确定性派生）；
  2. challenge 的 `key_id`/`epoch` 与 intent 一致且合法；
  3. `now_tick - t_intent ≤ τ_intent`。
  三条全满足才产出 CONFIRM，并**消费**该 intent（一次性 `consumed=True`）。
- **为何不能只匹配 `(cmd, payload_hash)`**：否则用户稍后再发**同一** critical 命令/同 payload 时，攻击者重放**旧** prepare（旧 epoch/ctr 但同 cmd/payload）→ challenge 的 `(cmd,payload_hash)` 仍匹配新 intent → 被洗白。绑 `pid`（含 epoch/ctr）后，旧 prepare 的 pid ≠ 新 intent 的 pid → 拒绝。
- **攻击者重放旧 critical REQ**：receiver 照常登记 pending、发 CHALLENGE（pid=旧）；但真 sender 当前 intent 的 pid 是新的（或已消费/超时）→ pid 不匹配 → `confirm_critical_challenge` 返回 None → 不 confirm → 不 commit。这就是 `test_replayed_old_critical_req_no_sender_confirm_without_user_intent` 的防线。
- 引擎里 attacker 重放 prepare 时，**不**经过 sender 的 intent 创建路径（attacker 不是 sender）；只有 legit critical 发送才创建 intent。

### D4：pid / nonce_id / payload_hash 的类型（对齐现有 MAC helper，已核实签名）
现有签名（`mac_domains.py:44/51`）已写死：`crit_prepare_tag(..., payload_hash: bytes, flags: int)`、`crit_confirm_tag(..., payload_hash: bytes, pid: int, nonce_id: int, nonce_r: str, ttl: int, flags: int)`。**全链路统一为同一类型，避免与 helper / mypy 漂移**：
- `payload_hash: bytes` —— `payload_digest(payload: bytes) -> bytes`（`sha256(payload).digest()[:16]`，定长 16 字节）。
- `pid: int` —— `pid_for(epoch, ctr, cmd, payload_hash: bytes) -> int`（`int.from_bytes(sha256(f"{epoch}|{ctr}|{cmd}|".encode() + payload_hash).digest()[:8], "big")`，确定性；重放同 prepare → 同 pid → 幂等登记 + `committed_critical` 去重保 commit 仅一次）。
- `nonce_id: int`（R 端自增）；`nonce_r: str`（CSPRNG hex）。
- `pending_critical: dict[int, CriticalPending]`、`committed_critical: set[int]`（key = pid:int）。
- 备选否决：pid 用自增整数（重放得不同 pid 绕过去重）；payload_hash 用 str（与 helper `bytes` 签名漂移）。

### D5：Phase 3 改哪个 mode？
- **推荐**：`HSW_CR` 的**高风险路径**从当前单阶段 `verify_challenge_response` 升级为**两阶段 critical commit**（`Π(cmd)=critical` 即 `command_risk[cmd] ≥ risk_high`）。低风险路径仍走 window（含 Phase 2 resync）。
- 现有 `Mode.CHALLENGE`（单阶段 issue→verify）**保留为 baseline**，不改。
- **影响**：`HSW_CR` 数值按设计改变——但它在 Phase 2 已移出冻结 baseline（`STABLE_MODES` 不含 HSW_CR），故 baseline regression 不受影响；HSW_CR 新行为由 Phase 3 专门测试覆盖。

> **请确认 D1=A、D2=两专用入口、D3=sender intent 门控、D4=确定性 pid + payload_hash、D5=升级 HSW_CR 高风险路径（CHALLENGE 保留）。** 确认后我把引擎接线 Task 的逐行代码定稿（kernel/state/prepare/confirm 现在即可执行）。

---

## 范围决策（Phase 3 做什么 / 不做什么）

- **做**：Critical 两阶段提交（§4.4，含三不变量）+ §4.5 PendingUserIntent 防洗白；kernel `critical_commit` + `payload_digest`；`ReceiverState.pending_critical`/`committed_critical`；`Sender.PendingUserIntent`；引擎两阶段子泵；5 个 blocker test。
- **不做（留后续 Phase）**：完整 reboot/LOCKED_SAFE/counter-lease（Phase 4）；adaptive/诱导攻击者（Phase 5）；wire format / protocol 层（后续）。复用 Phase 2 的 `epoch` 字段，不在本 Phase 扩 reboot。
- 契约层：新增 critical 计数（`crit_prepared/crit_committed/crit_rejected`）需同步 `SimulationResultRecord` + `as_dict()` + TS + check-contracts（Task 3.6，**注意 Phase 2 教训：`as_dict()` 导出面别漏**）。

> **硬约束（贯穿）：**
> 1. **(C1) prepare 不提前提交**：prepare 通过 ⇒ 仅登记 pending，**不动 H/M_W、不执行命令**。
> 2. **(C2) commit 仅一次**：同 `(epoch,ctr,cmd,payload_hash)`（即同 pid）重复 confirm 被拒（`committed_critical` 去重）。
> 3. **(C3) pending 表有界 N_p**：默认 `N_p=2`；超出拒绝新 prepare（或淘汰最旧，二选一，**见 D 待确认**——推荐"拒绝新"以防淘汰攻击）。
> 4. **(C4) MAC-before-everything**：prepare 先验 `crit_prepare_tag`，confirm 先验 `crit_confirm_tag`；任一不过即拒，不动状态。
> 5. **(C5) §4.5 防洗白**：sender 仅在用户意图匹配 + 未过期 + challenge 合法时 confirm；重放 REQ 无新意图 → 不 confirm。
> 6. **(C6) 原子 commit**：`window_commit` 更新 + 执行一次 + 删 pending + 记 committed，要么全做要么全不做。
> 7. **回归零影响**：非 HSW_CR 模式（含 STABLE_MODES 与 CHALLENGE）数值不变；HSW_CR 按设计改变（已在 Phase 2 移出冻结 baseline）。
> 引用 @superpowers:test-driven-development、@superpowers:verification-before-completion。

---

## 当前形态速查（细化所依据的真实代码）

- `src/replay/core/kernel/mac_domains.py`：
  - `crit_prepare_tag(key, dev_id, key_id, epoch, ctr, cmd, payload_hash, flags) -> str`
  - `crit_confirm_tag(key, dev_id, key_id, epoch, ctr, cmd, payload_hash, pid, nonce_id, nonce_r, ttl, flags) -> str`
- `src/replay/core/kernel/window_commit.py`：`window_commit(n,h,mask,w)`（critical commit 与 normal accept **调同一份**，§4.1 约束）。
- `src/replay/core/types.py`：`Frame.FLAG_NORMAL_REQ=0`（resync=3/4 已用）；critical 用 `FLAG_CRIT_PREPARE=1`、`FLAG_CRIT_CONFIRM=2`。`Frame` 有 `dev_id/key_id/epoch/flags/payload/ttl`。`ReceiverState` 有 `epoch/resync_pending`（**无 pending_critical**）。
- `src/replay/core/receiver.py`：当前 `Mode.HSW_CR` 高风险 → `verify_hsw_cr`(:146) → 单阶段 `verify_challenge_response`(:107)；`process` dispatch(:264+) 按 mode；Phase 2 已加 `process_resync_confirm`/`issue_resync_challenge`/`time_out_resync`。`VerificationResult(accepted, reason, state)`。
- `src/replay/core/sender.py`：`Sender{mode, shared_key, mac_length, tx_counter, authenticator}` + `next_frame` + `respond_resync_challenge`（Phase 2）。**无 PendingUserIntent**。
- `src/replay/core/experiment.py`：`_resolve_resync` 有界子泵（Phase 2，可作 critical 子泵的范本）；`_should_challenge`(:94) 决定高风险；两路径 `process_arrived` 调 `receiver.process`。
- 回归安全网：`tests/test_engine_baseline_regression.py`（`STABLE_MODES` 不含 HSW_CR/SW_RESYNC）+ `tests/fixtures/engine_baseline.json`。

---

## Phase 3 · Tasks

> 门：5 个 blocker test 绿 + critical 单元/集成测试绿 + `test_engine_baseline_regression`（STABLE_MODES）仍逐值相等 + 全量 pytest 绿 + ruff/mypy 不退化 + check-contracts 绿。

### Task 3.0：kernel `payload_digest` + `critical_commit`（纯函数）

**Files:** Create `src/replay/core/kernel/critical_commit.py`；Test `tests/test_kernel_critical_commit.py`

**Step 1: 失败测试**
```python
# tests/test_kernel_critical_commit.py
from replay.core.kernel.critical_commit import critical_commit, payload_digest, pid_for


def test_payload_digest_is_16_bytes_and_stable():
    assert isinstance(payload_digest(b"x"), bytes)
    assert payload_digest(b"x") == payload_digest(b"x")
    assert payload_digest(b"x") != payload_digest(b"y")
    assert len(payload_digest(b"x")) == 16


def test_pid_is_deterministic_int_for_same_request():
    ph = payload_digest(b"p")
    a = pid_for(epoch=1, ctr=7, cmd="OPEN", payload_hash=ph)
    b = pid_for(epoch=1, ctr=7, cmd="OPEN", payload_hash=ph)
    assert isinstance(a, int) and a == b
    assert pid_for(epoch=1, ctr=8, cmd="OPEN", payload_hash=ph) != a   # 不同 ctr -> 不同 pid


def test_critical_commit_uses_same_window_commit():
    # critical commit 的窗口更新与 normal accept 完全一致（同 window_commit）
    new_h, mask = critical_commit(n=12, h=10, mask=[1, 0, 0, 0, 0], w=5)
    assert (new_h, mask) == (12, [1, 0, 1, 0, 0])
```

**Step 2:** 跑红（ModuleNotFoundError）。

**Step 3: 实现**
```python
# src/replay/core/kernel/critical_commit.py
"""Critical 两阶段提交原语（§4.4）：payload 摘要、pid 派生、原子窗口提交（复用 window_commit）。"""
from __future__ import annotations

import hashlib

from .window_commit import window_commit


def payload_digest(payload: bytes) -> bytes:
    return hashlib.sha256(payload).digest()[:16]   # 定长 16 字节，与 crit_*_tag 的 payload_hash: bytes 对齐


def pid_for(*, epoch: int, ctr: int, cmd: str, payload_hash: bytes) -> int:
    raw = f"{epoch}|{ctr}|{cmd}|".encode("utf-8") + payload_hash
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big")   # 确定性 int pid（去重键）


def critical_commit(*, n: int, h: int, mask: list[int], w: int) -> tuple[int, list[int]]:
    """原子 commit 的窗口部分：与 normal accept 调同一 window_commit（§4.1）。"""
    return window_commit(n, h, mask, w)
```

**Step 4:** 跑绿 + ruff + mypy。 **Step 5:** 提交 `feat: add critical_commit kernel primitives (payload_digest/pid/commit)`。

### Task 3.1：`ReceiverState` 加 `pending_critical` + `committed_critical`；`CriticalPending`

**Files:** Modify `src/replay/core/types.py`；Test `tests/test_critical_state.py`

**Step 1: 失败测试**
```python
# tests/test_critical_state.py
from replay.core.types import CriticalPending, ReceiverState


def test_defaults_empty_tables():
    s = ReceiverState()
    assert s.pending_critical == {}
    assert s.committed_critical == set()


def test_critical_pending_holds_confirm_binding_fields():
    p = CriticalPending(
        epoch=1, ctr=7, cmd="OPEN", payload_hash=b"ab",
        nonce_id=3, nonce_r="rr", ttl_ticks=20, expire_tick=25, sender_id=2,
    )
    assert p.cmd == "OPEN" and p.payload_hash == b"ab"
    assert p.nonce_id == 3 and p.nonce_r == "rr"
    assert p.expire_tick == 25 and p.sender_id == 2
```

**Step 3: 实现**（`types.py` 加 `CriticalPending` + 扩 `ReceiverState`）
```python
@dataclass
class CriticalPending:
    """pendingCritical[pid] 表项（§4.4 阶段1）。confirm 绑定字段全在此固化。"""
    epoch: int
    ctr: int
    cmd: str
    payload_hash: bytes       # 与 crit_*_tag 的 payload_hash: bytes 对齐
    nonce_id: int
    nonce_r: str
    ttl_ticks: int
    expire_tick: int
    sender_id: int

# ReceiverState 追加：
    pending_critical: dict[int, CriticalPending] = field(default_factory=dict)   # key=pid:int
    committed_critical: set[int] = field(default_factory=set)                    # 已提交 pid，去重(C2)
    crit_nonce_seq: int = 0                                                      # nonce_id 自增源
```

**Step 4/5:** 跑绿 + 全量回归 + 提交 `feat: extend ReceiverState with pending_critical and committed set`。

### Task 3.2：receiver prepare 路径（登记 pending，不动窗口/不执行，发 CHALLENGE，N_p 有界）

**Files:** Modify
- `src/replay/core/types.py`：(a) `Frame` 加 `FLAG_CRIT_PREPARE=1`/`FLAG_CRIT_CONFIRM=2`/`FLAG_CRIT_CHALLENGE=5`(ClassVar；0=NORMAL,3/4=RESYNC 已占) + **载体字段** `pid: int = 0`、`nonce_id: int = 0`、`payload_hash: bytes = b""`（**不复用 `nonce` 同时表示 nonce_r 与 pid**；`nonce_r` 仍走 `frame.nonce: str`），并更新 `clone()`；(b) `SimulationConfig` 加 `critical_pending_capacity: int = 2`、`critical_ttl_ticks: int = 16`。
- `src/replay/core/receiver.py`：`Receiver.__init__` 加 `critical_pending_capacity: int = 2`、`critical_ttl_ticks: int = 16` 参数并存为属性（否则 `process_crit_prepare` 不知道 N_p/TTL）；新增 `process_crit_prepare` + `issue_crit_challenge`。
- `src/replay/core/experiment.py`：`simulate_one_run` 与 `simulate_one_run_with_trace` 两处 `Receiver(...)` 构造都传 `critical_pending_capacity=config.critical_pending_capacity, critical_ttl_ticks=config.critical_ttl_ticks`。
- Test `tests/test_critical_prepare.py` + `tests/test_frame_critical_fields.py`（Frame 新字段 + clone）

**Step 1: 失败测试（含 blocker C1 + N_p C3）**
```python
# tests/test_critical_prepare.py 要点：
# test_critical_prepare_does_not_update_global_window (blocker C1)：
#   合法 prepare(crit_prepare_tag ok, cmd 高风险) -> 返回 challenge；state.last_counter/received_mask 不变；命令未执行。
# test_prepare_registers_pending_with_binding_fields：
#   pending_critical[pid] 存在，含 (epoch,ctr,cmd,payload_hash,nonce_r,ttl,sender_id)。
# test_pending_table_capacity_Np_enforced (blocker C3)：
#   N_p=2 时第 3 个不同 prepare -> 拒绝(reason="critical_pending_full")，表大小保持 2。
# test_prepare_bad_mac_rejected_no_pending (C4)：
#   crit_prepare_tag 篡改 -> reason="mac_mismatch"，pending_critical 不新增。
# test_prepare_non_critical_command_rejected：
#   低风险 cmd 的 prepare -> reason="not_critical"（不登记）。
# test_duplicate_prepare_is_idempotent (修审查#4)：
#   同一 (epoch,ctr,cmd,payload_hash) 重复 prepare -> 同 pid；pending 不增长；
#   且 nonce_id / nonce_r / expire_tick 全部不变（不递增 crit_nonce_seq、不刷新 TTL）。
```

**Step 3: 实现要点**
- `types.py`：`Frame` 加 `FLAG_CRIT_PREPARE=1`/`FLAG_CRIT_CONFIRM=2`(ClassVar) + 载体字段 `pid: int=0`、`nonce_id: int=0`、`payload_hash: bytes=b""`，`clone()` 复制三者。`SimulationConfig` 加 `critical_pending_capacity=2`、`critical_ttl_ticks=16`。
- `receiver.py`：`__init__` 接 `critical_pending_capacity`/`critical_ttl_ticks` 存属性。`process_crit_prepare(self, frame, rng, *, now_tick) -> VerificationResult`：
  ```
  if self.mode is not HSW_CR: return (False,"unexpected_crit_prepare")
  if (command_risk or {}).get(frame.command,0.0) < risk_high: return (False,"not_critical")   # 策略
  ph = payload_digest(frame.payload)
  expected = crit_prepare_tag(key, frame.dev_id, frame.key_id, frame.epoch, frame.counter,
                              frame.command, ph, Frame.FLAG_CRIT_PREPARE)
  if frame.mac is None or not constant_time_compare(frame.mac, expected):
      return (False,"mac_mismatch")                                              # C4：先 MAC
  pid = pid_for(epoch=frame.epoch, ctr=frame.counter, cmd=frame.command, payload_hash=ph)
  if pid in committed_critical: return (False,"critical_already_committed")        # C2 早拒
  if pid in pending_critical:                                                      # 幂等（修#4）
      return (False,"critical_prepared")          # 不递增 seq、不刷新 nonce/TTL；引擎仍 issue_crit_challenge(pid) 取同一挑战
  if len(pending_critical) >= self.critical_pending_capacity:
      return (False,"critical_pending_full")                                       # C3（拒绝新，不淘汰）
  # 首次登记（不动 H/M_W、不执行）—— C1
  nonce_id = state.crit_nonce_seq; state.crit_nonce_seq += 1
  nonce_r = f"{rng.getrandbits(96):024x}"
  expire = now_tick + self.critical_ttl_ticks
  pending_critical[pid] = CriticalPending(frame.epoch, frame.counter, frame.command, ph,
                                          nonce_id, nonce_r, self.critical_ttl_ticks, expire, frame.dev_id)
  return (False,"critical_prepared")
  ```
- `receiver.py` `issue_crit_challenge(self, pid) -> Frame`（幂等交付，**不改 pending**）：
  ```
  p = pending_critical[pid]
  return Frame(command=p.cmd, flags=Frame.FLAG_CRIT_PREPARE? no -> 用 challenge 语义,
               # CHALLENGE 是 R2T；用 flags=FLAG_CRIT_PREPARE 的反向？ -> 执行时定 challenge flags（建议复用 FLAG_CRIT_PREPARE 作 R2T challenge 标识或新增 FLAG_CRIT_CHALLENGE）
               pid=pid, nonce_id=p.nonce_id, nonce=p.nonce_r, payload_hash=p.payload_hash,
               epoch=p.epoch, counter=p.ctr, ttl=p.ttl_ticks, key_id=...)
  ```
  > **执行注**：CHALLENGE 是 R→T 反向帧，需一个明确 flags。建议 Task 3.2 顺带定 `FLAG_CRIT_CHALLENGE=5`（4 已被 RESYNC_CONFIRM 占）——避免与 prepare/confirm 混淆。sender 的 `confirm_critical_challenge` 读 `challenge.pid/nonce_id/nonce/payload_hash/epoch/counter/cmd` 构造 confirm。

**Step 4/5:** 跑绿（含 C1/C3 blocker）+ 回归 + 提交 `feat: receiver critical prepare registers bounded pending and emits challenge`。

### Task 3.3：receiver confirm 路径（Accept_critical 六条 + 原子 commit + 执行一次）

**Files:** Modify `src/replay/core/receiver.py`（新增 `process_crit_confirm`）；Test `tests/test_critical_confirm.py`

**confirm 绑定字段（crit_confirm_tag 输入，两侧必须逐项对齐）：**
`key, dev_id, key_id, epoch, ctr, cmd, payload_hash, pid, nonce_id, nonce_r, ttl, flags`
—— 其中 `epoch/ctr/cmd/payload_hash/pid/nonce_id/nonce_r/ttl` 全部取自 receiver 侧 `pending_critical[pid]`（权威值），`flags=FLAG_CRIT_CONFIRM`。

**Step 1: 失败测试（含 blocker C2/C6 + fake challenge）**
```python
# tests/test_critical_confirm.py 要点：
# test_critical_commit_updates_window_and_executes_once (blocker C2/C6)：
#   合法 confirm -> 原子 commit：last_counter 前进、window_commit 生效、命令"执行一次"(accepted=True)、pending 删除、pid 入 committed。
# test_duplicate_confirm_does_not_recommit (C2)：
#   同 pid 第二次 confirm -> reason="critical_already_committed"，不二次执行、窗口不再变。
# test_fake_challenge_does_not_commit (blocker)：
#   pid 不在 pending（伪造/未 prepare）的 confirm -> reason="critical_no_pending"，不 commit。
# test_confirm_bad_mac_keeps_pending (C4)：篡改 tag -> mac_mismatch；pending 保留、窗口不变。
# test_confirm_nonce_mismatch / epoch_mismatch / ttl_expired：保持/清理语义明确。
# test_confirm_sw_reject_when_ctr_not_acceptable：ctr 不在可接受位（dup/old）-> 不 commit。
```

**Step 3: 实现要点**
- `process_crit_confirm(self, frame, *, now_tick) -> VerificationResult`，顺序（MAC-before-everything）：
  ```
  pid = frame.pid                                              # Frame.pid 载体字段（Task 3.2 已定，int）
  if pid in committed_critical: return (False,"critical_already_committed")    # C2
  p = pending_critical.get(pid)
  if p is None: return (False,"critical_no_pending")                           # fake challenge 防线
  expected = crit_confirm_tag(key, dev_id, key_id, p.epoch, p.ctr, p.cmd, p.payload_hash,
                              pid, p.nonce_id, p.nonce_r, p.ttl_ticks, FLAG_CRIT_CONFIRM)
  if not constant_time_compare(frame.mac, expected): return (False,"mac_mismatch")   # C4 保留 pending
  if now_tick > p.expire_tick: del pending_critical[pid]; return (False,"critical_ttl_expired")
  # SWok：ctr 必须可被接受（用 classify 判定）
  decision = classify(p.ctr, last_counter, received_mask, W)
  if decision in (REJECT_DUP, REJECT_OLD): del pending_critical[pid]; return (False,"critical_sw_reject")
  # 原子 commit（C6）：窗口更新 + 执行一次 + 删 pending + 记 committed
  last_counter, received_mask = critical_commit(n=p.ctr, h=last_counter, mask=received_mask, w=W)
  del pending_critical[pid]; committed_critical.add(pid)
  return VerificationResult(True, "critical_committed", state)   # accepted=True 表示"执行一次"
  ```
- 注：confirm 的 `accepted=True` 即代表命令被执行一次；引擎据此计 legit_accepted / executed。dup confirm 因 `committed_critical` 命中而 `accepted=False`，不二次执行。

**Step 4/5:** 跑绿（含 C2/C6/fake blocker）+ 回归 + 提交 `feat: receiver critical confirm atomically commits and executes once`。

### Task 3.4：Sender `PendingUserIntent`（§4.5 防 challenge 洗白）

**Files:** Modify `src/replay/core/sender.py`（新增 intent 记录 + `confirm_critical_challenge`）、`src/replay/core/types.py`（`PendingUserIntent`）；Test `tests/test_sender_intent.py`

**Step 1: 失败测试（含 blocker §4.5）**
```python
# tests/test_sender_intent.py 要点：
# test_sender_confirms_when_intent_matches：
#   sender 发起 critical REQ(记 intent) -> 收到匹配 challenge -> confirm_critical_challenge 产出 CONFIRM。
# test_replayed_old_critical_req_no_sender_confirm_without_user_intent (blocker §4.5)：
#   intent 已消费/从未存在时收到 challenge -> 返回 None（不替攻击者 confirm）。
# test_intent_expires_after_tau：now - t_intent > τ_intent -> None。
# test_intent_consumed_once：一次 confirm 后 intent 标记已消费，重复 challenge -> None。
# test_challenge_wrong_epoch_or_keyid_rejected：challenge 来源不合法 -> None。
# test_old_prepare_same_cmd_payload_rejected_by_pid (修审查#1，关键)：
#   用户已就 (epoch2,ctr2) 发新 intent；攻击者重放旧 prepare 触发的 challenge 带旧 pid(epoch1,ctr1，同 cmd/payload)
#   -> challenge.pid != intent.pid -> None（绑 pid/epoch/ctr 后不被同 cmd/payload 洗白）。
```

**Step 3: 实现要点**
- `types.py`：`PendingUserIntent(epoch: int, ctr: int, cmd: str, payload_hash: bytes, pid: int, key_id: int, t_intent: int, consumed: bool = False)`（**绑完整身份，非仅 cmd/payload**）。
- `sender.py`：
  - `begin_critical_intent(self, cmd, payload, *, epoch, key_id, now_tick) -> Frame`：
    ```
    self.tx_counter += 1
    ph = payload_digest(payload); ctr = self.tx_counter
    pid = pid_for(epoch=epoch, ctr=ctr, cmd=cmd, payload_hash=ph)
    self.pending_intent = PendingUserIntent(epoch, ctr, cmd, ph, pid, key_id, now_tick)
    return Frame(command=cmd, counter=ctr, epoch=epoch, key_id=key_id, flags=Frame.FLAG_CRIT_PREPARE,
                 payload=payload, payload_hash=ph,
                 mac=crit_prepare_tag(key, dev_id, key_id, epoch, ctr, cmd, ph, Frame.FLAG_CRIT_PREPARE))
    ```
  - `confirm_critical_challenge(self, challenge, *, now_tick, tau_intent) -> Frame | None`：
    ```
    intent = self.pending_intent
    if intent is None or intent.consumed: return None
    if challenge.pid != intent.pid: return None                 # ★ 绑 pid（含 epoch/ctr/cmd/payload_hash）防同 cmd 洗白
    if challenge.key_id != intent.key_id or challenge.epoch != intent.epoch: return None
    if now_tick - intent.t_intent > tau_intent: return None
    intent.consumed = True                                      # 一次性
    return Frame(command=intent.cmd, counter=intent.ctr, epoch=intent.epoch, key_id=intent.key_id,
                 flags=Frame.FLAG_CRIT_CONFIRM, pid=intent.pid, nonce_id=challenge.nonce_id,
                 nonce=challenge.nonce, payload_hash=intent.payload_hash,
                 mac=crit_confirm_tag(key, dev_id, intent.key_id, intent.epoch, intent.ctr, intent.cmd,
                                      intent.payload_hash, intent.pid, challenge.nonce_id, challenge.nonce,
                                      challenge.ttl, Frame.FLAG_CRIT_CONFIRM))
    ```
- **关键**：attacker 重放 prepare **不**调 `begin_critical_intent`（只有 legit sender 发起才记 intent）；且即便用户重发同 cmd/payload，旧 prepare 的 `pid`（旧 epoch/ctr）≠ 当前 intent.pid → 不 confirm。

**Step 4/5:** 跑绿（含 §4.5 blocker）+ 提交 `feat: add sender PendingUserIntent to block challenge-washing replay`。

### Task 3.5：引擎两阶段子泵接线（**D1–D5 确认后定稿**）

**Files:** Modify `src/replay/core/experiment.py`（`_resolve_critical` 子泵，两路径共用，仿 `_resolve_resync`）、`src/replay/core/cost.py`（`CostStats` 加 `crit_prepared/crit_committed/crit_rejected`）、`src/replay/core/types.py`（`SimulationConfig` 加 `tau_intent_ticks`）、`src/replay/core/trace.py`（critical 专用 drop/delay 序列，末尾抽取）；Test `tests/test_critical_engine.py`

**做法骨架（Option A，仿 Phase 2 `_resolve_resync`）：**
1. HSW_CR 高风险命令：legit 发送时 `sender.begin_critical_intent(...)` 产出 PREPARE（替代当前 `issue_nonce`+单阶段 challenge）。
2. PREPARE 到达 → `receiver.process_crit_prepare(frame, rng, now_tick=...)` → `critical_prepared` + CHALLENGE；`crit_prepared += 1`。
3. 引擎经 R2T 送 CHALLENGE → `sender.confirm_critical_challenge(challenge, now_tick, tau_intent)`：
   - None（无意图/洗白/过期）→ 不 confirm；pending 最终 TTL 超时清理；`crit_rejected += 1`。
   - CONFIRM → 经反向送回 → `receiver.process_crit_confirm(confirm, now_tick=arrival)`；`critical_committed` → `crit_committed += 1`（命令执行一次，计 legit_accepted）。
4. loss/delay/TTL：live=rng / paired=trace（**新增 critical 专用 trace 序列，末尾抽取**，同 Phase 2 resync 的零漂移技巧）。
5. **不显式重发**；attacker 重放 prepare 走同路径但 sender 无意图 → 不 commit。

**测试规格（test_critical_engine.py）：**
- `test_hsw_cr_critical_command_commits_once_clean_channel`：无损下高风险命令两阶段 commit，`crit_committed==1`、命令执行一次。
- `test_replayed_critical_prepare_does_not_commit`：attacker 重放 prepare → `crit_committed` 不增、`attack_success==0`。
- `test_critical_confirm_lost_times_out`：confirm 丢失 → pending TTL 清理、`crit_rejected` 计数。
- `test_baseline_stable_modes_unchanged_with_critical_engine`：STABLE_MODES 逐值不变。

**Step 5:** 提交 `feat: wire bounded critical two-phase commit into engine (both paths)`。

### Task 3.6：契约/指标同步（critical 计数，**含 as_dict 导出面**）

**Files:** Modify `src/replay/core/types.py`（`SimulationRunResult` + `AggregateStats` 加 `crit_prepared/crit_committed/crit_rejected` + **`AggregateStats.as_dict()`**）、`src/replay/core/experiment.py`（两处 run result 填充 + `_aggregate_results` 汇总）、`src/replay/contracts/models.py`（`SimulationResultRecord` + `from_aggregate`）、`src/replay/contracts/typescript.py`（TS interface）、`web/scripts/check-contracts.mjs`（断言）；Test `tests/test_contract_critical_metrics.py`

**做法：** 同 Phase 2 Task 2.6 + 修复——**五条导出面全贯通**：`SimulationRunResult` 字段 → `AggregateStats` 字段 + **`as_dict()`** → Pydantic → TS/web。测试必须含 `AggregateStats.as_dict()` 暴露断言（Phase 2 漏过这条，本 Phase 一次写全）。重生成 `contracts.ts`/`contracts.json`。
**Step 5:** 提交 `feat: expose critical two-phase counters in contracts and TS`。

> **Phase 3 门（用 @superpowers:verification-before-completion 核验）：**
> - 5 个 blocker test 绿：`test_critical_prepare_does_not_update_global_window`、`test_critical_commit_updates_window_and_executes_once`、`test_pending_table_capacity_Np_enforced`、`test_fake_challenge_does_not_commit`、`test_replayed_old_critical_req_no_sender_confirm_without_user_intent`
> - critical 单元（kernel/state/prepare/confirm/intent）+ 引擎集成全绿
> - `test_engine_baseline_regression`（STABLE_MODES）仍逐值相等
> - 全量 pytest 绿 + ruff/mypy 不退化 + check-contracts 绿（含 `as_dict` 导出面测试）

---

## 执行建议

- 顺序：3.0（kernel）→ 3.1（state）→ 3.2（prepare）→ 3.3（confirm）→ 3.4（sender intent）→ **【确认 D1–D5】** → 3.5（引擎接线）→ 3.6（契约指标）。
- 3.0–3.4 歧义低/中，确认前即可开工；**3.5 必须等 D1–D5 拍板后再写逐行**（与 Phase 2 同理）。
- 每个 Task 后跑 `test_engine_baseline_regression`（STABLE_MODES）自查——非 HSW_CR 模式任何漂移立即停下排查。
- **Phase 2 两个教训务必带入**：(a) confirm 验证里加 counter/SW 不变量防回退；(b) 指标 `as_dict()` 导出面别漏（3.6 一次写全 + 测试）。
- Phase 3 门绿后，用 `superpowers:writing-plans` 细化 Phase 4（epoch / LOCKED_SAFE / reboot / counter-lease）。
