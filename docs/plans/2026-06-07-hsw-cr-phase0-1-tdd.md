# HSW-CR Phase 0 / 1 / 1.5 · 逐行 TDD 实施计划

> **For Claude:** REQUIRED SUB-SKILL: 用 `superpowers:executing-plans` 逐任务实施本计划。
> 本文件是主计划 `docs/plans/2026-06-07-hsw-cr-full-protocol-overhaul.md` 的**执行细化**，只覆盖 Phase 0 / 1 / 1.5；后续 Phase 待这三个门绿后再细化。

**Goal:** 在不破坏现有行为的前提下，建立 `core/kernel/` 单一真相核（WINDOW_COMMIT/acceptance/MAC domain），扩展帧结构，把 receiver 切到 kernel 并引入 G_hard，最后铺好双向事件驱动引擎基座。

**约定（每个 Task 通用）：**
- **环境**：用项目 `.venv`（系统 `python3` 未装 pytest）；下列命令统一用 `.venv/bin/python`。基线已实测：pytest / ruff / mypy / check-contracts 全绿。
- 测试运行：`PYTHONPATH=src:. .venv/bin/python -m pytest <file>::<test> -v`
- 全量回归：`PYTHONPATH=src:. .venv/bin/python -m pytest`
- 质量门：`PYTHONPATH=src:. .venv/bin/python -m ruff check src tests` + `PYTHONPATH=src .venv/bin/python -m mypy src` + `cd web && node scripts/check-contracts.mjs`
- 提交格式：`<type>: <desc>`（feat/fix/refactor/test/chore）
- TDD 纪律：先写失败测试 → 跑红 → 最小实现 → 跑绿 → 提交。引用 @superpowers:test-driven-development、@superpowers:verification-before-completion。
- Python 3.9：`from __future__ import annotations` 必加；类型注解可用 `list[int]` 写法（因 future import），但不要运行期下标泛型实例化。

---

## Phase 0 · 准备与 kernel 抽取（纯新增，不动现有 receiver）

> 门：本 Phase 结束时现有全部测试仍绿；新增 kernel 模块独立测试绿。**不修改** `receiver.py`/`types.py`。

### Task 0.1：清理工作树 macOS 副本 + 加 .gitignore

**Files:** Modify `.gitignore`

**Step 1:** 删除 5 个未跟踪副本（它们是 Finder 复制产物，非 git 跟踪）：
```bash
cd /Users/romeitou/Desktop/論文/Replay
rm -f web/public/data/artifacts/"p-loss-sweep 2.json" \
      web/public/data/artifacts/"p-reorder-sweep 2.json" \
      web/public/data/artifacts/"validation-20260316-164739 2.json" \
      web/public/data/artifacts/"window-sweep 2.json" \
      web/public/data/"manifest 2.json"
```

**Step 2:** `.gitignore` 追加**精准**规则（修审查 P2：仅限 data 目录的 Finder 副本，避免误伤合法 `xxx 1.json`）：
```
# macOS Finder copy duplicates under generated data dir only
web/public/data/* [0-9].json
web/public/data/artifacts/* [0-9].json
```

**Step 3（计划替换提交，修审查 P2）:** 把旧计划删除 + 三份新计划作为一次清晰提交，并确认工作树干净（不要留散落未跟踪计划）：
```bash
git add -A docs/plans .gitignore
git status   # 确认无 "* 2.json"、无散落未跟踪计划
git commit -m "docs: replace overhaul plan with HSW-CR full-protocol + TDD breakdown"
```

**Step 4:** 基线确认：`PYTHONPATH=src:. .venv/bin/python -m pytest` 全绿。

### Task 0.2：基线确认（建立绿灯快照）

**Step 1:** `PYTHONPATH=src:. python3 -m pytest` → 记录全绿与用例数。
**Step 2:** 若缺 dev 工具：`python3 -m pip install -e ".[dev]"`。
**Step 3:** `PYTHONPATH=src:. python3 -m ruff check src tests` 与 `PYTHONPATH=src python3 -m mypy src` → 记录现状（mypy 可能有既有告警，记录为基线，不在本 Phase 扩大）。
（无提交。）

### Task 0.3：`core/kernel/` 包 + `window_commit.py`（list 版冻结函数）

**Files:**
- Create: `src/replay/core/kernel/__init__.py`
- Create: `src/replay/core/kernel/window_commit.py`
- Test: `tests/test_kernel_window_commit.py`

**Step 1: 写失败测试**
```python
# tests/test_kernel_window_commit.py
from replay.core.kernel.window_commit import window_commit


def test_forward_jump_updates_bitmap_exactly():
    # W=5, H=10, 仅顶位已置（counter 10 已收）
    new_h, new_mask = window_commit(12, 10, [1, 0, 0, 0, 0], 5)
    assert new_h == 12
    # 新顶 counter12 -> offset0；旧 counter10 -> offset (12-10)=2
    assert new_mask == [1, 0, 1, 0, 0]


def test_in_window_accept_marks_only_target_bit():
    new_h, new_mask = window_commit(11, 12, [1, 0, 1, 0, 0], 5)
    assert new_h == 12                      # H 不前移
    assert new_mask == [1, 1, 1, 0, 0]      # 仅 offset(12-11)=1 置位


def test_forward_jump_beyond_window_resets():
    new_h, new_mask = window_commit(100, 10, [1, 1, 1, 1, 1], 5)
    assert new_h == 100
    assert new_mask == [1, 0, 0, 0, 0]      # jump>=W，旧位全部移出


def test_duplicate_or_old_leaves_state_unchanged():
    assert window_commit(11, 12, [1, 1, 1, 0, 0], 5) == (12, [1, 1, 1, 0, 0])  # dup
    assert window_commit(2, 12, [1, 0, 0, 0, 0], 5) == (12, [1, 0, 0, 0, 0])   # old
```

**Step 2:** 跑红：`PYTHONPATH=src:. python3 -m pytest tests/test_kernel_window_commit.py -v` → 预期 `ModuleNotFoundError: replay.core.kernel`。

**Step 3: 最小实现**
```python
# src/replay/core/kernel/__init__.py
"""HSW-CR 单一真相核：engine 与 protocol 共用的判定逻辑（研究计划 §8.6 冻结规格）。"""

# src/replay/core/kernel/window_commit.py
from __future__ import annotations


def window_commit(n: int, h: int, mask: list[int], w: int) -> tuple[int, list[int]]:
    """滑动窗口状态更新（§8.6-3）。mask[d]=1 表示 counter h-d 已接受。
    仅在帧被接受（ACCEPT_FORWARD / ACCEPT_IN_WINDOW）时调用。返回 (new_h, new_mask)。"""
    if n > h:  # 情形1：前跳接受
        jump = n - h
        new_mask = [0] * w
        new_mask[0] = 1  # 新窗口顶 H'=n 自身置位
        for d in range(w):
            if jump + d < w:
                new_mask[jump + d] = mask[d]
        return n, new_mask
    if h - w + 1 <= n <= h and mask[h - n] == 0:  # 情形2：窗口内接受
        new_mask = list(mask)
        new_mask[h - n] = 1
        return h, new_mask
    return h, list(mask)  # 情形3：dup/old/macfail/resync-pending，不变
```

**Step 4:** 跑绿：同 Step 2 命令 → 4 个测试 PASS。
**Step 5:** 提交：`git add src/replay/core/kernel tests/test_kernel_window_commit.py && git commit -m "feat: add frozen WINDOW_COMMIT kernel (list bitmap)"`

### Task 0.4：`acceptance.py`（SW 四分支判定）

**Files:** Create `src/replay/core/kernel/acceptance.py`；Test `tests/test_kernel_acceptance.py`

**Step 1: 失败测试**
```python
# tests/test_kernel_acceptance.py
from replay.core.kernel.acceptance import SwDecision, classify


def test_accept_forward():
    assert classify(13, 10, [1, 0, 0, 0, 0], 5) is SwDecision.ACCEPT_FORWARD


def test_accept_in_window():
    assert classify(11, 12, [1, 0, 0, 0, 0], 5) is SwDecision.ACCEPT_IN_WINDOW


def test_reject_dup():
    assert classify(11, 12, [1, 1, 0, 0, 0], 5) is SwDecision.REJECT_DUP


def test_reject_old():
    assert classify(7, 12, [1, 0, 0, 0, 0], 5) is SwDecision.REJECT_OLD
```

**Step 2:** 跑红（模块不存在）。

**Step 3: 实现**
```python
# src/replay/core/kernel/acceptance.py
from __future__ import annotations

from enum import Enum


class SwDecision(str, Enum):
    ACCEPT_FORWARD = "accept_forward"
    ACCEPT_IN_WINDOW = "accept_in_window"
    REJECT_DUP = "reject_dup"
    REJECT_OLD = "reject_old"


def classify(n: int, h: int, mask: list[int], w: int) -> SwDecision:
    """SW 四分支判定（§5.2）。只判定是否接受，不更新状态（更新走 window_commit）。"""
    if n > h:
        return SwDecision.ACCEPT_FORWARD
    if h - w + 1 <= n <= h:
        return SwDecision.REJECT_DUP if mask[h - n] == 1 else SwDecision.ACCEPT_IN_WINDOW
    return SwDecision.REJECT_OLD
```

**Step 4:** 跑绿。 **Step 5:** 提交 `feat: add SW four-branch acceptance classifier`。

### Task 0.5：`mac_domains.py`（MAC domain 分离，长度前缀编码）

> 修审查 P1：MAC 输入不得用 `"|".join` 拼接（payload 含 `|` 会 delimiter collision）。改用**长度前缀的类型化编码**：每段 = 4B 大端长度前缀 + bytes，杜绝歧义；domain 作首段。补 `crit_prepare_tag` 与碰撞/bytes 测试。

**Files:** Create `src/replay/core/kernel/mac_domains.py`；Test `tests/test_kernel_mac_domains.py`

**Step 1: 失败测试**
```python
# tests/test_kernel_mac_domains.py
from replay.core.kernel.mac_domains import (
    hmac96, normal_req_tag, crit_prepare_tag, crit_confirm_tag, resync_confirm_tag,
)

KEY = "k"


def test_hmac96_is_24_hex_chars():
    assert len(hmac96(KEY, b"DOMAIN", b"X", 1)) == 24


def test_length_prefix_no_delimiter_collision():
    # ("a","bc") 与 ("ab","c") 朴素拼接会碰撞；长度前缀必须区分
    assert hmac96(KEY, b"a", b"bc") != hmac96(KEY, b"ab", b"c")


def test_bytes_payload_with_pipe_unambiguous():
    assert hmac96(KEY, b"D", b"x|y", b"z") != hmac96(KEY, b"D", b"x", b"y|z")


def test_type_tag_distinguishes_int_from_equal_bytes():
    # 修审查 P1-2：int 1 与其 8 字节大端表示必须产生不同 tag（类型语义歧义）
    assert hmac96(KEY, 1) != hmac96(KEY, (1).to_bytes(8, "big", signed=True))
    assert hmac96(KEY, True) != hmac96(KEY, b"\x01")


def test_all_four_domains_distinct():
    tags = {
        normal_req_tag(KEY, 1, 0, 0, 7, "OPEN", b"p", 0),
        crit_prepare_tag(KEY, 1, 0, 0, 7, "OPEN", b"ph", 0),
        crit_confirm_tag(KEY, 1, 0, 0, 7, "OPEN", b"ph", 1, 2, "nr", 5, 0),
        resync_confirm_tag(KEY, 1, 0, 0, 1, 10, 200, "nr", 5, 0),
    }
    assert len(tags) == 4


def test_resync_tag_changes_with_new_h():
    assert resync_confirm_tag(KEY, 1, 0, 0, 1, 10, 200, "nr", 5, 0) \
        != resync_confirm_tag(KEY, 1, 0, 0, 1, 10, 999, "nr", 5, 0)
```

**Step 2:** 跑红。

**Step 3: 实现（长度前缀编码）**
```python
# src/replay/core/kernel/mac_domains.py
from __future__ import annotations

import hashlib
import hmac

_TAG_HEX = 96 // 4  # 24

DOMAIN_NORMAL_REQ = b"HSWCR_NORMAL_REQ"
DOMAIN_CRIT_PREPARE = b"HSWCR_CRIT_PREPARE"
DOMAIN_CRIT_CONFIRM = b"HSWCR_CRIT_CONFIRM"
DOMAIN_RESYNC_CONFIRM = b"HSWCR_RESYNC_CONFIRM"


def _to_typed_bytes(p: object) -> tuple[bytes, bytes]:
    # 返回 (1B 类型标签, 内容)；类型标签防 int↔bytes、bool↔bytes 等类型混淆（修审查 P1-2）
    if isinstance(p, bytes):
        return b"b", p
    if isinstance(p, bool):                    # 注意：必须在 int 之前（bool 是 int 子类）
        return b"?", (b"\x01" if p else b"\x00")
    if isinstance(p, int):
        return b"i", p.to_bytes(8, "big", signed=True)
    return b"s", str(p).encode("utf-8")


def _encode(*parts: object) -> bytes:
    out = bytearray()
    for p in parts:
        tag, b = _to_typed_bytes(p)
        out += tag + len(b).to_bytes(4, "big") + b  # 类型标签 + 4B 长度前缀 + 内容
    return bytes(out)


def hmac96(key: str, *parts: object) -> str:
    return hmac.new(key.encode(), _encode(*parts), hashlib.sha256).hexdigest()[:_TAG_HEX]


def normal_req_tag(key, dev_id, key_id, epoch, ctr, cmd, payload, flags) -> str:
    return hmac96(key, DOMAIN_NORMAL_REQ, dev_id, key_id, epoch, ctr, cmd, payload, flags)


def crit_prepare_tag(key, dev_id, key_id, epoch, ctr, cmd, payload_hash, flags) -> str:
    return hmac96(key, DOMAIN_CRIT_PREPARE, dev_id, key_id, epoch, ctr, cmd, payload_hash, flags)


def crit_confirm_tag(key, dev_id, key_id, epoch, ctr, cmd, payload_hash, pid, nonce_id, nonce_r, ttl, flags) -> str:
    return hmac96(key, DOMAIN_CRIT_CONFIRM, dev_id, key_id, epoch, ctr, cmd,
                  payload_hash, pid, nonce_id, nonce_r, ttl, flags)


def resync_confirm_tag(key, dev_id, key_id, old_epoch, new_epoch, old_h, new_h, nonce_r, ttl, flags) -> str:
    return hmac96(key, DOMAIN_RESYNC_CONFIRM, dev_id, key_id, old_epoch, new_epoch,
                  old_h, new_h, nonce_r, ttl, flags)
```

**Step 4:** 跑绿。 **Step 5:** 提交 `feat: add MAC domain helpers with length-prefixed encoding`。

> **Phase 0 门：** `PYTHONPATH=src:. python3 -m pytest`（现有 + 3 个新 kernel 测试文件全绿）。

---

## Phase 1 · 帧结构 + receiver 切到 kernel + G_hard

> 门：现有 window 语义保持（除被显式迁移的 `test_window_mask_clamped`）；新增 G_hard/帧字段测试绿。

### Task 1.1：扩展 `Frame`（epoch/dev_id/key_id/flags/payload）

**Files:** Modify `src/replay/core/types.py:27-44`（`Frame`）；Test `tests/test_frame_fields.py`

**Step 1: 失败测试**
```python
# tests/test_frame_fields.py
from sim.types import Frame


def test_new_fields_default_and_clone():
    f = Frame(command="OPEN", counter=7, epoch=1, dev_id=2, key_id=0, flags=0, payload=b"\x01")
    assert f.epoch == 1 and f.dev_id == 2 and f.flags == 0 and f.payload == b"\x01"
    c = f.clone()
    assert c.epoch == 1 and c.dev_id == 2 and c.payload == b"\x01"
    assert c == f


def test_backward_compatible_minimal_frame():
    f = Frame(command="PING")
    assert f.epoch == 0 and f.dev_id == 0 and f.key_id == 0 and f.flags == 0 and f.payload == b""
```

**Step 2:** 跑红（`TypeError: unexpected keyword 'epoch'`）。

**Step 3: 实现** — 在 `Frame` 增字段（默认值保证向后兼容）并更新 `clone()`：
```python
@dataclass
class Frame:
    command: str
    counter: int | None = None
    mac: str | None = None
    nonce: str | None = None
    is_attack: bool = False
    # HSW-CR 扩展（研究计划 §3.3）
    dev_id: int = 0
    key_id: int = 0
    epoch: int = 0
    flags: int = 0
    payload: bytes = b""

    def clone(self) -> Frame:
        return Frame(
            command=self.command, counter=self.counter, mac=self.mac, nonce=self.nonce,
            is_attack=self.is_attack, dev_id=self.dev_id, key_id=self.key_id,
            epoch=self.epoch, flags=self.flags, payload=self.payload,
        )
```

**Step 4:** 跑绿 + 全量回归（确认未破坏现有 Frame 用法）。 **Step 5:** 提交 `feat: extend Frame with HSW-CR fields (epoch/dev_id/key_id/flags/payload)`。

### Task 1.2：ReceiverState 位掩码迁移 int→list + verify_with_window 切到 kernel

**Files:** Modify `src/replay/core/types.py`（`ReceiverState.received_mask`）、`src/replay/core/receiver.py:45-87`（`verify_with_window`）、`tests/test_receiver.py:124-130`（`test_window_mask_clamped`）

**Step 1: 迁移既有断言（明确的破坏性改动）** — 把 `test_window_mask_clamped` 改为断言 list 形态：
```python
def test_window_mask_clamped():
    receiver = Receiver(Mode.WINDOW, shared_key=SHARED_KEY, mac_length=MAC_LENGTH, window_size=3)
    for counter in range(1, 10):
        res = receiver.process(create_frame(counter))
        assert res.accepted
        assert len(receiver.state.received_mask) == 3        # 现在是 list[int]
        assert all(b in (0, 1) for b in receiver.state.received_mask)
```

**Step 2:** 跑红：`test_window_mask_clamped` 失败（仍是 int）；其余 window 测试（basic/out_of_order/too_old/too_far）此刻应仍绿。

**Step 3: 实现**
- `ReceiverState.received_mask: list[int] = field(default_factory=list)`（替换 `int = 0`）。
- `verify_with_window` 改为：用 `classify()` 判定四分支；接受时用 `window_commit()` 更新 `(last_counter, received_mask)`；初始帧把 `received_mask` 初始化为 `[1] + [0]*(W-1)`。reason 字符串保持现有值（`window_accept_initial`/`window_accept_new`/`window_accept_old`/`counter_replay`/`counter_too_old`）以兼容现有断言。
- 映射：`classify==ACCEPT_FORWARD`→`window_accept_new`；`ACCEPT_IN_WINDOW`→`window_accept_old`；`REJECT_DUP`→`counter_replay`；`REJECT_OLD`→`counter_too_old`；`last_counter<0`→`window_accept_initial`。

**Step 4:** 跑绿：`tests/test_receiver.py` 全部 PASS（含迁移后的 mask 测试），全量回归绿。
**Step 5:** 提交 `refactor: route window verification through kernel (list bitmap)`。

> 注：`Mode.WINDOW` 与 `Mode.OSCORE_LIKE` 共用此路径（receiver.py:198）。

### Task 1.3：G_hard 闸门 + 前跳 gap 语义（resync 钩子占位）

**Files:** Modify `src/replay/core/types.py`（`SimulationConfig` 增 `g_hard: int = 16`）、`src/replay/core/kernel/acceptance.py`（新增 `needs_resync`）、`src/replay/core/receiver.py`；Test `tests/test_ghard_gate.py`

**Step 1: 失败测试**
```python
# tests/test_ghard_gate.py
from replay.core.kernel.acceptance import needs_resync


def test_forward_jump_within_ghard_is_normal():
    # H=10, n=14 -> jump=4 <= g_hard=8 -> 不触发 resync
    assert needs_resync(14, 10, g_hard=8) is False


def test_forward_jump_over_ghard_triggers_resync():
    # H=10, n=25 -> jump=15 > g_hard=8 -> 触发 resync
    assert needs_resync(25, 10, g_hard=8) is True


def test_backward_never_resync():
    assert needs_resync(8, 10, g_hard=8) is False
```

**Step 2:** 跑红。

**Step 3: 实现**
```python
# acceptance.py 追加
def needs_resync(n: int, h: int, g_hard: int) -> bool:
    """前跳超过 G_hard 闸门则需认证重同步（§5.3）。前跳 gap = n - h。"""
    return n > h and (n - h) > g_hard
```
- **改用防御变体 `Mode.SW_RESYNC`（修第二轮审查 P1-1）**：`enable_resync` 作为 `base_config` 全局 bool，在 `run_many_experiments`/`run_paired_experiments` 的 `dataclasses.replace(base_config, mode=mode)`（experiment.py:316/600）下被一个 batch 内所有 mode 共享，无法同 batch 区分纯 `WINDOW` 与 `SW+Resync`。故 resync 能力改为 **mode 固有属性**：新增 `Mode.SW_RESYNC`，结果天然以 `mode`(=defense_id) 区分。
- resync 能力按 mode 推导（**不用全局 bool**）：`WINDOW`/`OSCORE_LIKE`=纯 SW baseline，前跳越 `g_hard` 仍 `ACCEPT_FORWARD`（不被污染）；`SW_RESYNC`=`WINDOW`+resync，前跳越 `g_hard` → `resync_required`（占位、**不执行命令**，符合 H1）；`HSW_CR` 自带 resync（同 SW_RESYNC 前跳处理）。
- **顺序硬规则（修审查 P1：MAC 必须先于 G_hard）**：`needs_resync`/`resync_required` 判定**只在 MAC 验证通过之后**进行。MAC 失败 → 直接 `mac_mismatch` reject，**绝不**进入 resync 路径（否则伪造 MAC 的大 counter 帧成为 DoS / 状态机污染入口）。`verify_with_window`/`verify_hsw_cr` 内固定顺序：① 字段非空 → ② `authenticator.verify`（失败即 `mac_mismatch`） → ③ `needs_resync`（仅 SW_RESYNC/HSW_CR） → ④ SW 四分支 + `window_commit`。
- 防御集映射（主计划 §9）：`SW`=`WINDOW`；`SW+Resync`=`SW_RESYNC`；消融"Resync on/off" = 同 `g_hard` 下跑 `modes=[WINDOW, SW_RESYNC]` 对比。
- `SimulationConfig` 增 `g_hard: int = 16`（**不再加 enable_resync bool**）；`Mode` 增 `SW_RESYNC = "sw_resync"`；`Receiver.__init__` 接收 `g_hard`，按 `mode` 推导是否 resync。
- 测试：
  - `test_pure_window_forward_jump_not_resync()`：WINDOW 前跳越 g_hard 仍 `ACCEPT_FORWARD`。
  - `test_sw_resync_forward_jump_requires_resync()`：SW_RESYNC 前跳越 g_hard → `resync_required`。
  - `test_resync_required_does_not_mutate_state()`（修审查 P1-2）：`SW_RESYNC` 与 `HSW_CR` 低风险普通帧的 `resync_required` 路径上，`state.last_counter` 与 `state.received_mask` **保持不变**（不得先 `window_commit` 再 reject；窗口更新留给 Phase 2 的 resync confirm）。
  - `test_sw_resync_in_all_window_like_sets()`（修审查 P1-1）：覆盖三处 —— `SW_RESYNC` 能被 `Receiver.process` 受理（不抛 Unsupported mode）；`SimulationSpec(modes=['sw_resync'], window_size=0)` 被拒；聚合结果 `window_size` 非 0。
  - `test_invalid_mac_far_future_does_not_trigger_resync()`（修审查 P1：MAC-before-G_hard）：
    ```python
    def test_invalid_mac_far_future_does_not_trigger_resync():
        receiver = Receiver(Mode.SW_RESYNC, shared_key=SHARED_KEY, mac_length=MAC_LENGTH, window_size=5, g_hard=8)
        receiver.process(create_frame(10))
        bad = Frame(command="CMD", counter=100, mac="bad")
        res = receiver.process(bad)
        assert not res.accepted
        assert res.reason == "mac_mismatch"        # 不是 resync_required
        assert receiver.state.last_counter == 10   # 状态未被污染
    ```

**Step 4:** 跑绿 + 回归。 **Step 5:** 提交 `feat: add G_hard forward-jump gate (resync placeholder)`。

### Task 1.4：契约 + TS 同步（暴露 g_hard）

**Files（全链路传递，修审查 P1 —— 漏任一处则 API/Web/CLI/preset 不一致）：**
- `src/replay/core/experiment.py`：**两处** Receiver 构造（`:117` `simulate_one_run`、`:407` `simulate_one_run_with_trace`）传 `g_hard=config.g_hard`（resync 能力由 `config.mode` 推导，无需额外 bool）。
- `src/replay/core/types.py`：`Mode` 增 `SW_RESYNC = "sw_resync"`；**抽常量消除散落集合（修审查 P1-1）**：`WINDOW_VERIFY_MODES = {WINDOW, SW_RESYNC, OSCORE_LIKE}`（走 window 验证路径）、`WINDOW_SIZED_MODES = WINDOW_VERIFY_MODES | {HSW_CR}`（需要 window_size 的 mode）。
- **三处 window-like 集合改用上述常量（漏一处即出 bug）**：`receiver.py:198` dispatch（原 `{WINDOW, OSCORE_LIKE}` → `WINDOW_VERIFY_MODES`）；`models.py:89` `_validate_window_size`（原 `{WINDOW, HSW_CR, OSCORE_LIKE}` → `WINDOW_SIZED_MODES`，否则 `SW_RESYNC`+`window_size=0` 被误纳）；`experiment.py:271` `_aggregate_results`（原同上 → `WINDOW_SIZED_MODES`，否则结果 `window_size` 被置 0）。
- `src/replay/contracts/models.py`：`SimulationSpec` 增 `g_hard`，`to_runtime_config` 传递，`SimulationSpecPublic` 同步；`modes` 验证接受 `sw_resync`。
- `src/replay/contracts/typescript.py`：手改模板 —— **`export type Mode` union 增 `'sw_resync'`** + `g_hard: number`。
- `main.py`：argparse `--modes` choices 增 `sw_resync`、增 `--g-hard`；`src/replay/cli/app.py` 同步。
- `presets/*.yaml`：若 preset 带 `defense.g_hard` 则读取映射。
- `web/scripts/check-contracts.mjs`：断言 `contracts.ts` 的 `Mode` 含 `sw_resync` 且含 `g_hard`。

**Step 1:** 失败测试 `tests/test_contract_ghard.py`：
```python
from replay.contracts import SimulationSpec, SimulationSpecPublic


def test_spec_accepts_g_hard():
    spec = SimulationSpec(modes=["window"], runs=2, window_size=5, g_hard=32)
    assert spec.g_hard == 32
    assert spec.to_runtime_config().g_hard == 32


def test_spec_accepts_sw_resync_and_public_preserves_it():
    # 修审查 P2：baseline 分流 mode 必须贯通契约 + public 视图（仅断言 g_hard 不够）
    spec = SimulationSpec(modes=["window", "sw_resync"], runs=2, window_size=5, g_hard=32)
    assert "sw_resync" in [str(m) for m in spec.modes]
    pub = SimulationSpecPublic.from_spec(spec)
    assert "sw_resync" in [str(m) for m in pub.modes]
    assert pub.g_hard == 32
```
另补：`tests/test_cli_app.py` 断言 `--modes sw_resync` 可解析；`check-contracts.mjs` 断言 TS `Mode` 含 `sw_resync`。
**Step 2:** 跑红。
**Step 3:** `SimulationSpec` 增 `g_hard: int = Field(default=16, ge=0)`；`to_runtime_config` 加 `g_hard=self.g_hard`。手改 `typescript.py` 模板加 `g_hard: number;`。重生成：
```bash
PYTHONPATH=src python3 -c "from pathlib import Path; from replay.contracts.typescript import write_contract_artifacts; write_contract_artifacts(Path('.'))"
```
强化 `check-contracts.mjs`：断言 `contracts.ts` 含 `g_hard`。
**Step 4:** 跑绿 + `cd web && node scripts/check-contracts.mjs`。 **Step 5:** 提交 `feat: expose g_hard in contracts and TS`。

> **Phase 1 门：** 全量 pytest 绿 + ruff/mypy 不退化 + `check-contracts` 绿。

---

## Phase 1.5 · 双向事件驱动引擎基座（resync/critical 前置）

> 目标：把 `experiment.py` 的单向帧 for 循环升级为 tick/事件驱动调度器，支持反向 `R→T` 信道与 TTL 超时，为 Phase 2（resync）/ Phase 3（两阶段提交）铺路。**关键门：现有所有蒙特卡洛实验数值在新调度器下回归复现（容差内）。**
>
> 说明：本 Phase 改动 `experiment.py` 较深，逐行代码须在 Phase 1 落地后、对照当时 `experiment.py` 真实形态展开。下列为任务结构 + 测试规格 + 接口骨架，执行时用 `superpowers:writing-plans` 对本 Phase 二次细化。

### Task 1.5.1：事件/调度器抽象（新增，不接线）

**Files:** Create `src/replay/core/scheduler.py`；Test `tests/test_scheduler.py`

**测试规格：**
- 事件按 `delivery_tick` 升序弹出；同 tick 用稳定 seq 次序（与现有 `ScheduledFrame` 一致）。
- 支持双向方向标签 `Direction.T2R` / `Direction.R2T`。
- TTL：投递时携带 `expire_tick`，到期未消费的事件被丢弃并可查询“超时计数”。

**接口骨架：**
```python
# scheduler.py
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum


class Direction(str, Enum):
    T2R = "t2r"
    R2T = "r2t"


@dataclass(order=True)
class Event:
    delivery_tick: int
    seq: int
    direction: Direction = Direction.T2R
    frame: object = None
    expire_tick: int | None = None
```

### Task 1.5.2：两套路径都迁到事件驱动 + 回归（修审查 P2）

**Files:** Modify `src/replay/core/experiment.py`（**两套**：`simulate_one_run` 与 `simulate_one_run_with_trace`）；Test `tests/test_event_engine_regression.py`

> 审查 P2：仓库有 `simulate_one_run`（普通蒙特卡洛）与 `simulate_one_run_with_trace`（paired/trace，`experiment.py:390`，由 `run_paired_experiments` `experiment.py:588` 调用）两套路由。只迁前者会让 paired/trace 实验拿不到 R→T/TTL/resync 行为。**两套都必须迁到同一事件驱动调度器（共用实现，避免再次分叉）。**

**测试规格（回归）：** 固定 `seed=42` 覆盖 **(a) 普通路径** 与 **(b) paired 路径**（`run_paired_experiments`）若干配置（no_def / rolling / window，post 与 inline），新调度器产出的 `legit_accepted / attack_success / legit_sent / attack_attempts` 与迁移前**逐值相等**。

**做法：** 迁移前用脚本把**两套路径**结果快照成夹具 `tests/fixtures/engine_baseline.json`（含 paired）；迁移后断言一致。先保证 T2R 单向行为不变，再加 R2T 通道（暂无生产者，仅基座）。

### Task 1.5.3：反向信道冒烟

**测试规格：** 构造一个 R→T 事件（模拟 RESYNC_CHALLENGE）注入调度器，断言它按 tick 到达“发送端”侧回调，且 TTL 到期能被正确丢弃。此为 Phase 2 resync 的接线点。

> **Phase 1.5 门：** `test_event_engine_regression` 全绿（数值与基线一致）+ 反向信道冒烟绿 + 全量回归绿。

---

## 执行建议

- 顺序严格：0 → 1 → 1.5；每个 Task 独立提交。
- Phase 0 纯新增、零风险，可立即开干。
- Phase 1.2 是唯一“破坏性迁移”（int→list），已显式包含被改测试。
- Phase 1.5 落地后，再用 `superpowers:writing-plans` 细化 Phase 2（Authenticated Resync 状态机）。
- 每个门用 @superpowers:verification-before-completion 核验后再进下一 Phase。
