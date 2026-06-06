# HSW-CR Phase 1.5 · 双向事件驱动引擎基座 — 逐行 TDD 实施计划

> **For Claude:** REQUIRED SUB-SKILL: 用 `superpowers:executing-plans` 逐任务实施本计划。
> 本文件是 `docs/plans/2026-06-07-hsw-cr-phase0-1-tdd.md` 中 Phase 1.5 的**二次细化**（对照 Phase 1 落地后的 `experiment.py`/`channel.py` 真实形态展开），并替代该文件 §1.5 的骨架描述。

**Goal:** 把 `experiment.py` 两套帧调度（`simulate_one_run` 的 live `Channel`、`simulate_one_run_with_trace` 的内联堆）统一到单一 `EventScheduler`，引入 `Direction.T2R/R2T` 与 TTL 基座，为 Phase 2（Authenticated Resync 的反向 `R→T` 信道）铺路——且**所有现有蒙特卡洛数值逐值复现**。

**Architecture:** 抽取一个 `EventScheduler`（按方向分队的 `(delivery_tick, seq)` 优先队列 + TTL 过期丢弃），让 `Channel` 内部委托它（公有 `send/flush` API 不变 → `simulate_one_run` 的 RNG 消费顺序逐字节不变），并让 trace 路径用同一个 `EventScheduler` 替换内联 `scheduled`/`send_traced`/`flush_traced`。**只统一调度引擎，不动命令来源/攻击者逻辑**（见下方"范围决策"）。

**Tech Stack:** Python 3.9+（`from __future__ import annotations`）、`heapq`、`dataclasses`、pytest。环境同前：`.venv/bin/python`，`PYTHONPATH=src:.`。

---

## 范围决策（执行前必读 / 已与用户对齐）

**Phase 1.5 只统一"调度引擎"，不统一"命令来源/攻击者逻辑"。**

- 两套路径的**合法差异**是"丢包/延迟决策来源"：`simulate_one_run` 现场掷 `loss_model.dropped(rng)` + `delay_model.delay(rng)`；`simulate_one_run_with_trace` 读预生成的 `trace.legit_dropped/legit_delay/...`。此差异**保留**。
- 两套路径**重复的**是 `(tick, seq)` 堆调度 + `process_arrived` + `record_tx` + flush。本 Phase 把**堆调度**收敛到 `EventScheduler`；`process_arrived`/`record_tx` 暂不强行合并（与调度无关，合并收益低、回归风险高）。
- **不做**：把 for 循环改成"事件完全驱动一切（含合法发送）"的大重写——那是更大改动、对 resync 基座非必需，留作未来。
- 这样既满足主计划"两套都迁到同一事件驱动调度器（共用实现，避免再次分叉）"，又把回归风险压到最低。

> **硬约束（贯穿所有 Task）：**
> 1. **RNG 顺序不变**：`simulate_one_run` 路径里 `loss_model.dropped(rng)` 必须仍先于 `delay_model.delay(rng)`，且仅在"发送尝试"时各掷一次（dropped 掷一次；未丢包才掷 delay）。任何改动不得插入/删除/重排 RNG 调用。
> 2. **`(delivery_tick, seq)` 全序不变**：`tick` 每次发送尝试 +1（含丢包）；`seq` 仅在实际入队（未丢包）时 +1。出队顺序严格按 `(delivery_tick, seq)` 升序。
> 3. **回归判据**：迁移前后，`run_many_experiments` 与 `run_paired_experiments` 在固定 seed 下产出的 `legit_accepted / legit_total / attack_accepted / attack_total`（每 mode 的整数聚合）**逐值相等**（整数，无容差）。
> 引用 @superpowers:test-driven-development、@superpowers:verification-before-completion。

---

## 当前形态速查（细化所依据的真实代码）

- `src/replay/core/channel.py`：`ScheduledFrame(delivery_tick, seq, frame[compare=False])` + `Channel`。`Channel.send(frame)`：`current_tick += 1` → `loss_model.dropped(rng)`（丢包则不入队）→ 否则 `delay = delay_model.delay(rng)`，`heappush(pq, ScheduledFrame(current_tick+delay, seq_counter, frame))`，`seq_counter += 1` → 弹出所有 `delivery_tick <= current_tick`。`flush()`：弹出全部。
- `src/replay/core/experiment.py`：
  - `simulate_one_run`（:102）：用 `Channel`；`process_arrived(channel.send(frame))`，POST_RUN 末尾 `channel.flush()`，结尾再 `channel.flush()`。
  - `simulate_one_run_with_trace`（:392）：内联 `scheduled: list[tuple[int,int,Frame]]` + `send_traced(frame, *, dropped, delay)`（:469）+ `flush_traced()`（:480），逻辑与 `Channel` 同构但用 trace 数组取代 rng。
  - `run_many_experiments`（:308）→ 调 `simulate_one_run`；`run_paired_experiments`（:591）→ 调 `simulate_one_run_with_trace`。
  - 二者 `process_arrived`（:162 / :448）与 `record_tx`（:149 / :435）逐行相同。
- `src/replay/core/trace.py`：`ScenarioTrace.{commands, legit_dropped, legit_delay, attacker_record_dropped, inline_attempt, replay_pick, replay_dropped, replay_delay}` + `digest()`、`legit_drop_count`。
- 已有 `tests/test_experiment.py::test_reproducibility_with_fixed_seed` 证明引擎在固定 seed 下确定性复现。

---

## Phase 1.5 · Tasks

> 门：`tests/test_engine_baseline_regression.py` 全绿（两套路径数值与基线逐值相等）+ `tests/test_scheduler.py` 全绿 + 反向信道冒烟绿 + 全量回归绿 + ruff/mypy 不退化 + `check-contracts` 绿。

### Task 1.5.0：先冻结回归基线夹具（**任何代码改动之前**）

> 必须在动 `channel.py`/`experiment.py` **之前**用当前代码生成基线，否则夹具会带上迁移后的数值，失去回归意义。

**Files:**
- Create: `scripts/gen_engine_baseline.py`
- Create（产物）: `tests/fixtures/engine_baseline.json`

**Step 1: 写基线生成脚本**（`scripts/` 已在 ruff `extend-exclude`，无 lint 负担）
```python
# scripts/gen_engine_baseline.py
"""一次性脚本：用迁移前的引擎冻结两套路径的数值基线到 tests/fixtures/engine_baseline.json。
迁移完成后此脚本不再运行（基线已提交）；如需重生成必须在 Task 1.5.0 提交点的代码上运行。"""
from __future__ import annotations

import json
from pathlib import Path

from replay.core import Mode, SimulationConfig, run_many_experiments, run_paired_experiments
from replay.core.types import AttackMode

SEED = 42
RUNS = 8
MODES = [Mode.NO_DEFENSE, Mode.ROLLING_MAC, Mode.WINDOW, Mode.SW_RESYNC, Mode.CHALLENGE, Mode.HSW_CR, Mode.OSCORE_LIKE]
RISK = {"UNLOCK": 1.0}  # 让 HSW_CR/CHALLENGE 路径产生高风险分支


def _base(attack_mode: AttackMode) -> SimulationConfig:
    return SimulationConfig(
        mode=Mode.NO_DEFENSE,            # 占位，run_* 会按 mode 替换
        attack_mode=attack_mode,
        num_legit=20,
        num_replay=30,
        p_loss=0.1,
        p_reorder=0.1,
        window_size=5,
        g_hard=16,
        rng_seed=SEED,
        command_set=["UNLOCK", "LOCK", "PING"],
        command_risk=RISK,
        risk_high=0.8,
    )


def _snap(stats_list) -> dict:
    return {
        str(s.mode): {
            "legit_accepted": s.legit_accepted,
            "legit_total": s.legit_total,
            "attack_accepted": s.attack_accepted,
            "attack_total": s.attack_total,
        }
        for s in stats_list
    }


def main() -> None:
    baseline: dict = {"seed": SEED, "runs": RUNS, "cases": {}}
    for attack_mode in (AttackMode.POST_RUN, AttackMode.INLINE):
        cfg = _base(attack_mode)
        baseline["cases"][f"normal/{attack_mode.value}"] = _snap(
            run_many_experiments(cfg, modes=MODES, runs=RUNS, seed=SEED, show_progress=False)
        )
        baseline["cases"][f"paired/{attack_mode.value}"] = _snap(
            run_paired_experiments(cfg, modes=MODES, runs=RUNS, seed=SEED, show_progress=False)
        )
    out = Path("tests/fixtures/engine_baseline.json")
    out.write_text(json.dumps(baseline, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {out} with {len(baseline['cases'])} cases")


if __name__ == "__main__":
    main()
```

**Step 2: 生成夹具**
Run: `PYTHONPATH=src:. .venv/bin/python scripts/gen_engine_baseline.py`
Expected: 打印 `wrote tests/fixtures/engine_baseline.json with 4 cases`；文件含 `normal/post`、`normal/inline`、`paired/post`、`paired/inline` 四组、每组 7 个 mode 的 4 个整数。

**Step 3: 人工抽检**（确认基线非全 0、attack_total>0、window/sw_resync 的 legit_accepted 合理）
Run: `PYTHONPATH=src:. .venv/bin/python -c "import json;d=json.load(open('tests/fixtures/engine_baseline.json'));print(d['cases']['normal/post'])"`
Expected: 7 个 mode 的字典，数值非平凡。

**Step 4: 提交基线（无代码改动）**
```bash
git add scripts/gen_engine_baseline.py tests/fixtures/engine_baseline.json
git commit -m "test: freeze pre-migration engine numeric baseline fixture"
```

### Task 1.5.1：`EventScheduler` 抽象（纯新增，不接线）

**Files:**
- Create: `src/replay/core/scheduler.py`
- Test: `tests/test_scheduler.py`

**Step 1: 写失败测试**
```python
# tests/test_scheduler.py
from replay.core.scheduler import Direction, EventScheduler


def _sched():
    return EventScheduler()


def test_tick_monotonic():
    s = _sched()
    assert s.tick() == 1
    assert s.tick() == 2
    assert s.current_tick == 2


def test_due_order_by_tick_then_seq():
    # 同一 current_tick 下，按 (delivery_tick, seq) 升序弹出
    s = _sched()
    s.tick()  # current_tick=1
    s.submit("a", delivery_tick=3)   # seq0
    s.submit("b", delivery_tick=2)   # seq1
    s.submit("c", delivery_tick=2)   # seq2
    assert s.pop_due() == []          # 没有 <=1 的
    s.tick(); s.tick()                # current_tick=3
    assert s.pop_due() == ["b", "c", "a"]  # tick2(seq1,seq2) 先于 tick3(seq0)


def test_seq_only_advances_on_submit_not_tick():
    # tick 不推进 seq；两次 submit 的 seq 必须连续
    s = _sched()
    s.tick(); s.tick()
    s.submit("x", delivery_tick=1)
    s.submit("y", delivery_tick=1)
    # 同 tick，seq 升序 -> x 在 y 前
    assert s.pop_due() == ["x", "y"]


def test_flush_drains_all_remaining():
    s = _sched()
    s.tick()
    s.submit("a", delivery_tick=99)
    s.submit("b", delivery_tick=50)
    assert s.flush() == ["b", "a"]
    assert s.flush() == []


def test_direction_isolation():
    # T2R 与 R2T 互不串扰
    s = _sched()
    s.tick()
    s.submit("down", delivery_tick=1, direction=Direction.T2R)
    s.submit("up", delivery_tick=1, direction=Direction.R2T)
    assert s.pop_due(direction=Direction.T2R) == ["down"]
    assert s.pop_due(direction=Direction.R2T) == ["up"]


def test_ttl_expired_event_dropped_and_counted():
    # expire_tick < current_tick 即过期：不投递，计入 expired_count
    s = _sched()
    s.tick()                                  # current_tick=1
    s.submit("stale", delivery_tick=1, expire_tick=0)   # 0 < 1 -> 过期
    s.submit("fresh", delivery_tick=1, expire_tick=5)
    assert s.pop_due() == ["fresh"]
    assert s.expired_count() == 1


def test_ttl_boundary_not_expired_when_equal():
    # expire_tick == current_tick 仍可投递（过期判定是严格小于）
    s = _sched()
    s.tick()
    s.submit("edge", delivery_tick=1, expire_tick=1)
    assert s.pop_due() == ["edge"]
    assert s.expired_count() == 0
```

**Step 2:** 跑红：`PYTHONPATH=src:. .venv/bin/python -m pytest tests/test_scheduler.py -v` → `ModuleNotFoundError: replay.core.scheduler`。

**Step 3: 实现**
```python
# src/replay/core/scheduler.py
"""单一事件调度器：替代 Channel/trace 路径各自的 (tick, seq) 堆，并加 Direction/TTL 基座（§1.5）。"""
from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from enum import Enum


class Direction(str, Enum):
    T2R = "t2r"   # transmitter -> receiver（现有正向）
    R2T = "r2t"   # receiver -> transmitter（resync/challenge 反向，Phase 2 生产者）


@dataclass(order=True)
class Event:
    delivery_tick: int
    seq: int
    direction: Direction = field(default=Direction.T2R, compare=False)
    frame: object = field(default=None, compare=False)
    expire_tick: int | None = field(default=None, compare=False)


class EventScheduler:
    """按方向分队的 (delivery_tick, seq) 优先队列。tick 每次发送尝试 +1；seq 仅入队 +1。"""

    def __init__(self) -> None:
        self.current_tick = 0
        self._seq = 0
        self._queues: dict[Direction, list[Event]] = {Direction.T2R: [], Direction.R2T: []}
        self._expired: dict[Direction, int] = {Direction.T2R: 0, Direction.R2T: 0}

    def tick(self) -> int:
        self.current_tick += 1
        return self.current_tick

    def submit(
        self,
        frame: object,
        *,
        delivery_tick: int,
        direction: Direction = Direction.T2R,
        expire_tick: int | None = None,
    ) -> None:
        heapq.heappush(
            self._queues[direction],
            Event(delivery_tick, self._seq, direction, frame, expire_tick),
        )
        self._seq += 1

    def _drain(self, direction: Direction, predicate) -> list:
        queue = self._queues[direction]
        arrived: list = []
        while queue and predicate(queue[0]):
            event = heapq.heappop(queue)
            if event.expire_tick is not None and event.expire_tick < self.current_tick:
                self._expired[direction] += 1
                continue
            arrived.append(event.frame)
        return arrived

    def pop_due(self, *, direction: Direction = Direction.T2R) -> list:
        return self._drain(direction, lambda ev: ev.delivery_tick <= self.current_tick)

    def flush(self, *, direction: Direction = Direction.T2R) -> list:
        return self._drain(direction, lambda ev: True)

    def expired_count(self, direction: Direction = Direction.T2R) -> int:
        return self._expired[direction]
```

**Step 4:** 跑绿（8 个测试 PASS）+ `ruff check src/replay/core/scheduler.py tests/test_scheduler.py` + `mypy src`。
**Step 5:** 提交 `feat: add bidirectional EventScheduler with TTL (no wiring)`。

### Task 1.5.2a：`Channel` 内部委托 `EventScheduler`（正向回归）

> 公有 `send`/`flush` 签名与语义**完全不变**，只把内部 `pq`/`current_tick`/`seq_counter` 换成 `EventScheduler`。`simulate_one_run` 不改一行，RNG 顺序天然不变。

**Files:**
- Modify: `src/replay/core/channel.py`（`Channel.__init__`/`send`/`flush`；`ScheduledFrame` 保留供向后兼容，不删）
- Test: `tests/test_engine_baseline_regression.py`（先写 normal 部分）

**Step 1: 写回归测试（normal 两 attack_mode）**
```python
# tests/test_engine_baseline_regression.py
import json
from pathlib import Path

import pytest

from replay.core import Mode, SimulationConfig, run_many_experiments, run_paired_experiments
from replay.core.types import AttackMode

_BASELINE = json.loads((Path("tests/fixtures/engine_baseline.json")).read_text())
SEED = _BASELINE["seed"]
RUNS = _BASELINE["runs"]
MODES = [Mode.NO_DEFENSE, Mode.ROLLING_MAC, Mode.WINDOW, Mode.SW_RESYNC, Mode.CHALLENGE, Mode.HSW_CR, Mode.OSCORE_LIKE]
RISK = {"UNLOCK": 1.0}


def _base(attack_mode: AttackMode) -> SimulationConfig:
    return SimulationConfig(
        mode=Mode.NO_DEFENSE, attack_mode=attack_mode,
        num_legit=20, num_replay=30, p_loss=0.1, p_reorder=0.1,
        window_size=5, g_hard=16, rng_seed=SEED,
        command_set=["UNLOCK", "LOCK", "PING"], command_risk=RISK, risk_high=0.8,
    )


def _snap(stats_list) -> dict:
    return {
        str(s.mode): {
            "legit_accepted": s.legit_accepted, "legit_total": s.legit_total,
            "attack_accepted": s.attack_accepted, "attack_total": s.attack_total,
        }
        for s in stats_list
    }


@pytest.mark.parametrize("attack_mode", [AttackMode.POST_RUN, AttackMode.INLINE])
def test_normal_path_matches_baseline(attack_mode):
    got = _snap(run_many_experiments(_base(attack_mode), modes=MODES, runs=RUNS, seed=SEED, show_progress=False))
    assert got == _BASELINE["cases"][f"normal/{attack_mode.value}"]


@pytest.mark.parametrize("attack_mode", [AttackMode.POST_RUN, AttackMode.INLINE])
def test_paired_path_matches_baseline(attack_mode):
    got = _snap(run_paired_experiments(_base(attack_mode), modes=MODES, runs=RUNS, seed=SEED, show_progress=False))
    assert got == _BASELINE["cases"][f"paired/{attack_mode.value}"]
```

**Step 2:** 跑绿（基线就是当前代码生成的，**此刻应已全绿**）：
Run: `PYTHONPATH=src:. .venv/bin/python -m pytest tests/test_engine_baseline_regression.py -v`
Expected: 4 PASS。（这一步确认夹具与回归测试自洽，是迁移前的安全网。）

**Step 3: 改 `Channel` 委托 `EventScheduler`**
```python
# src/replay/core/channel.py —— send/flush 改为委托；其余（loss/delay 掷骰顺序）一字不动
from .scheduler import EventScheduler  # 顶部加导入

class Channel:
    def __init__(self, p_loss=0.0, p_reorder=0.0, rng=None, *, loss_model=None, delay_model=None):
        self.p_loss = p_loss
        self.p_reorder = p_reorder
        self.rng = rng
        self.loss_model = loss_model if loss_model is not None else IidLoss(p_loss)
        self.delay_model = delay_model if delay_model is not None else ReorderDelay(p_reorder)
        self._scheduler = EventScheduler()

    @property
    def current_tick(self) -> int:        # 兼容旧属性读取（如有）
        return self._scheduler.current_tick

    def send(self, frame: Frame) -> list[Frame]:
        tick = self._scheduler.tick()
        if self.rng is None:
            raise ValueError("Channel requires an RNG")
        if self.loss_model.dropped(self.rng):
            pass
        else:
            delay = self.delay_model.delay(self.rng)
            self._scheduler.submit(frame, delivery_tick=tick + delay)
        return self._scheduler.pop_due()

    def flush(self) -> list[Frame]:
        return self._scheduler.flush()
```
> 注意：掷骰顺序 `dropped(rng)` → `delay(rng)`、`tick` 每 send +1、`seq` 仅入队 +1，与原实现逐一对应。`ScheduledFrame` 类保留（可能有外部引用），不在本 Task 删除。

**Step 4:** 跑绿 + 回归：
Run: `PYTHONPATH=src:. .venv/bin/python -m pytest tests/test_channel.py tests/test_engine_baseline_regression.py -v`
Expected: `test_channel.py` 全绿；`test_normal_path_matches_baseline[post/inline]` 全绿（数值与基线逐值相等）。
（`test_paired_path_*` 此刻也应仍绿——trace 路径尚未改。）

**Step 5:** 提交 `refactor: back Channel with shared EventScheduler (T2R parity)`。

### Task 1.5.2b：trace 路径迁到同一 `EventScheduler`（paired 回归）

**Files:**
- Modify: `src/replay/core/experiment.py`（`simulate_one_run_with_trace`：删 `scheduled`/`send_traced`/`flush_traced` 内联堆，改用 `EventScheduler`）
- Modify（导入）: `experiment.py` 顶部加 `from .scheduler import EventScheduler`，删除不再使用的 `import heapq`（若 `simulate_one_run` 也无 heapq 直用——确认后再删，避免 ruff F401）

**Step 1:** 回归测试已存在（Task 1.5.2a 的 `test_paired_path_matches_baseline`），先跑红的反证：当前 paired 仍绿，是迁移前安全网。迁移后必须仍绿。

**Step 2: 改 `simulate_one_run_with_trace`**
```python
# 替换 tick/seq/scheduled 三个本地变量与 send_traced/flush_traced：
scheduler = EventScheduler()

def send_traced(frame: Frame, *, dropped: bool, delay: int) -> list[Frame]:
    tick = scheduler.tick()
    if not dropped:
        scheduler.submit(frame, delivery_tick=tick + delay)
    return scheduler.pop_due()

def flush_traced() -> list[Frame]:
    return scheduler.flush()
```
> 删除原 `tick = 0`、`seq = 0`、`scheduled: list[...] = []` 三行声明（`recorded` 等其余保留）。`send_traced`/`flush_traced` 的**调用点不变**，只换实现。掷骰来源仍是 trace 数组（`dropped`/`delay` 由调用方从 trace 传入），无 RNG。

**Step 3:** 跑绿 + 回归：
Run: `PYTHONPATH=src:. .venv/bin/python -m pytest tests/test_engine_baseline_regression.py tests/test_trace.py tests/test_experiment.py -v`
Expected: `test_paired_path_matches_baseline[post/inline]` 逐值相等；trace/experiment 测试全绿。

**Step 4:** 全量回归 + 质量门：
Run: `PYTHONPATH=src:. .venv/bin/python -m pytest` → 全绿；`ruff check src tests main.py` 绿；`mypy src` 不退化。
（若删 `import heapq` 后 ruff 报未用则一并清理；若仍被 `simulate_one_run` 外用则保留。）

**Step 5:** 提交 `refactor: route trace simulation through shared EventScheduler (paired parity)`。

### Task 1.5.3：反向信道（R2T）+ TTL 冒烟（Phase 2 接线点）

> 仅基座：注入一个模拟 `RESYNC_CHALLENGE` 的 R2T 事件，断言它按 tick 到达"发送端"侧，且 TTL 到期被正确丢弃。**暂无生产者**——这是 Phase 2 resync 的挂载点。

**Files:**
- Test: `tests/test_reverse_channel.py`

**Step 1: 写测试**
```python
# tests/test_reverse_channel.py
from replay.core.scheduler import Direction, EventScheduler


def test_r2t_event_delivered_at_tick_to_sender_side():
    s = EventScheduler()
    s.tick()                                       # current_tick=1
    s.submit("RESYNC_CHALLENGE", delivery_tick=2, direction=Direction.R2T)
    assert s.pop_due(direction=Direction.R2T) == []   # tick=1，未到
    s.tick()                                       # current_tick=2
    assert s.pop_due(direction=Direction.R2T) == ["RESYNC_CHALLENGE"]


def test_r2t_does_not_leak_into_t2r_stream():
    s = EventScheduler()
    s.tick()
    s.submit("RESYNC_CHALLENGE", delivery_tick=1, direction=Direction.R2T)
    assert s.pop_due(direction=Direction.T2R) == []     # 正向流不受反向事件污染
    assert s.pop_due(direction=Direction.R2T) == ["RESYNC_CHALLENGE"]


def test_r2t_ttl_expiry_drops_challenge():
    s = EventScheduler()
    s.tick(); s.tick()                             # current_tick=2
    s.submit("RESYNC_CHALLENGE", delivery_tick=1, direction=Direction.R2T, expire_tick=1)  # 1<2 过期
    assert s.pop_due(direction=Direction.R2T) == []
    assert s.expired_count(Direction.R2T) == 1
```

**Step 2:** 跑红→（实现已在 1.5.1 完成）实际应直接绿——若绿则说明基座到位；本 Task 是行为锁定，不需新实现。
Run: `PYTHONPATH=src:. .venv/bin/python -m pytest tests/test_reverse_channel.py -v` → 3 PASS。

**Step 3:** 提交 `test: lock reverse-channel (R2T) delivery and TTL expiry`。

> **Phase 1.5 门（用 @superpowers:verification-before-completion 核验）：**
> - `tests/test_scheduler.py` + `tests/test_engine_baseline_regression.py` + `tests/test_reverse_channel.py` 全绿
> - 全量 `PYTHONPATH=src:. .venv/bin/python -m pytest` 绿（数值与基线逐值一致）
> - `ruff check src tests main.py` 绿 + `mypy src` 不退化
> - `cd web && node scripts/check-contracts.mjs` 绿（本 Phase 不碰契约，应天然绿）

---

## 执行建议

- 顺序严格：1.5.0（冻结基线）→ 1.5.1（调度器）→ 1.5.2a（Channel）→ 1.5.2b（trace）→ 1.5.3（反向冒烟）。
- **1.5.0 必须最先**：基线一旦在迁移后生成就失去意义。
- 1.5.2a/1.5.2b 之间随时可跑回归夹具自查——任一数值漂移立即停下排查（多半是 RNG 顺序或 tick/seq 推进被打乱）。
- Phase 1.5 门绿后，再用 `superpowers:writing-plans` 细化 Phase 2（Authenticated Resync 状态机：R2T 生产者 + resync confirm + epoch/H 更新）。
