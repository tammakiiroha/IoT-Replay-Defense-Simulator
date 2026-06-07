# HSW-CR Phase 5 · 自适应攻击者 + 闭式数学模型 + 双重验证 — 逐行 TDD 实施计划

> **For Claude:** REQUIRED SUB-SKILL: 用 `superpowers:executing-plans` 逐任务实施本计划。
> 本文件是主计划 `docs/plans/2026-06-07-hsw-cr-full-protocol-overhaul.md` **§6/§7（G7+G10+增量1+增量3）** 的执行细化，对照 Phase 0–4 + G5/G9 落地后的真实主线（`origin/main` @ `4b22e39`）展开。**D1–D6 已拍板（见下节），可逐 Task 执行。**

**Goal:** 把弱威胁模型（随机记录+随机重放）升级为 §6 的**位置×强度 + lost-frame + 自适应攻击者**（G10），新增 §7 **闭式数学模型**（`a_W`、`LAR(W)`、`P_forge`、`P_compromise`、`W*`，G7），并产出**双重验证图**（解析曲线 vs 蒙特卡洛散点同图，增量1/3）。

**Architecture:** 新增 `core/analytic/models.py`（**纯函数**闭式模型，零引擎耦合）；`core/attacker.py` 抽 `AttackerStrategy` 接口（`RandomReplay`=现状 baseline / `AdaptiveReplay`=三策略），引擎按 `attacker_strategy`/`attacker_position`/`attacker_inject_strength` 选用；新增 `scripts/plot_analytic_vs_mc.py` 叠图。**默认 = 现状（RandomReplay + 既有信道），baseline 零漂移。**

**Tech Stack:** Python 3.9+、现有 `core/`（attacker/experiment/channel/stats）、`stats.wilson_ci`、pytest、matplotlib（仅脚本）。环境：`.venv/bin/python`，`PYTHONPATH=src:.`，命令前若 cwd 漂移先 `cd /Users/romeitou/Desktop/論文/Replay`。

---

## ⚠️ 范围澄清（务必先读）

- 本计划 = **G7（闭式模型）+ G10（攻击者增强）+ 增量1/3（双重验证）** 三块。
- **做**：`analytic/models.py`（`a_W`/`lar_w`/`p_forge`/`p_compromise`/`w_star` 纯函数）；`AttackerStrategy` 可插拔（RandomReplay/AdaptiveReplay 三策略：lost-frame 窗口 / 诱导 resync / critical delayed）；位置×强度信道映射；`plot_analytic_vs_mc.py` 双重验证图 + 验收断言。
- **不做（留 Phase 6，单独 PR）**：完整**指标体系 `core/metrics.py`**（ASR 双口径 / 经验 P_compromise / 零观测 UCB，§8）；完整**实验矩阵 + 消融脚本**（§9）；real-trace。本 Phase 只产出双重验证所需的最小观测 + 闭式函数，不铺全套指标/矩阵。
- 回归守门：攻击者增强**默认 opt-out**（`attacker_strategy="random"` + position/strength 映射到现状参数）；`STABLE_MODES` 与现有 attacker 行为必须**逐值零漂移**。

---

## 关键设计决策（D1–D6 已于 2026-06-08 review 拍板）

### D1：攻击者怎么抽象？baseline 怎么保零漂移？
- **推荐**：抽 `AttackerStrategy` 协议（`observe(frame, rng)` + `pick_frame(rng, *, context) -> Frame | None`）。`RandomReplay` = **现有 `Attacker` 逻辑原样搬过去**（observe 带 record_loss、pick_frame 随机/按 target_commands），作为 baseline。`AdaptiveReplay` 新增。
- `SimulationConfig.attacker_strategy: str = "random"`（默认）。引擎据此 new strategy。**默认 random + 调用序列不变 → baseline 逐值零漂移**（关键：rng 抽取顺序、pick 逻辑必须与现状字节一致）。
- 备选否决：直接在 `Attacker` 里加 if/else 分支（违反 OCP，且容易扰动 baseline rng 序列）。

### D2：位置 x × 强度 g 怎么建模？（**G10 安全核心** · 已拍板）
§6：`x ∈ {x_tx, x_rx, x_ind}`、`g ∈ {strong, weak}`，影响 `P_record`（记录成功率）与 `P_deliver^A`（攻击帧送达率）。
- **拍板**：新增 `SimulationConfig.attacker_position: str = "ind"`、`attacker_inject_strength: str = "strong"`，映射到两个概率（`p_loss = config.p_loss`、`record_loss = config.attacker_record_loss`）：

  ```text
  P_record（位置 → 能否录到该帧）:
    ind : P_record = 1 - record_loss                       # 默认=现状（记录与信道送达无关）
    tx  : P_record = 1.0                                    # 攻击者在发送端，能录到 receiver 没收到的帧
    rx  : P_record = (1 - p_loss) * (1 - record_loss)       # 仅 receiver 实际送达的帧可录

  P_deliver^A（强度 → 攻击帧能否送达 receiver）:
    strong : P_deliver^A = 1 - p_loss                       # 默认=现状，无额外 attack-only 丢弃
    weak   : P_deliver^A = 0.5 * (1 - p_loss)               # 额外 attack-only 弱注入丢弃
  ```

- **落地语义（两条路径都要写死）**：
  - **`ind` / `strong`（默认）= 既有调用顺序逐字节不变**：
    - live（`experiment.py:421-424`）：保持 `record_tx(frame) → attacker.observe(frame, local_rng) → channel.send(frame)`，observe 在 send 前，record_loss 抽签序不动。
    - paired（`experiment.py:876-877`, `trace.py:71-86`）：保持 `if not trace.attacker_record_dropped[index]: recorded.append(...)`；attack 帧送达保持 `trace.replay_dropped[index]`。
  - **`tx`**：忽略 record_loss / `attacker_record_dropped`，恒记录（不依赖记录丢弃抽签结果；live 仍在 send 前 observe，paired 仍在原位 append）。
  - **`rx`**：只记录 receiver 实际送达的合法帧——
    - live：记录决策**移到合法帧 `process_arrived` 之后**（按送达结果决定是否 observe）；
    - paired：append 条件改为 `if (not trace.legit_dropped[index]) and (not trace.attacker_record_dropped[index])`（与 `legit_dropped` 联动）。
  - **`weak`**：攻击帧在既有信道丢弃之外再加一道 attack-only 丢弃（命中 0.5）——
    - live：attack 帧 `channel.send` 前多抽一次 `local_rng`（仅 weak 分支，default strong 不抽）；
    - paired：在 `generate_trace` **末尾追加**新数组 `attack_extra_dropped`（§append 技巧，保持既有抽取顺序 → 非 weak 逐字节不变），attack 帧送达 = `(not replay_dropped) and (not attack_extra_dropped)`。
- **A1 零漂移**：上述 `tx/rx/weak` 改动**全部 opt-in**，默认 `(ind,strong)` 走原路径、原抽签序、原数据数组长度 → `STABLE_MODES` 与现有 attacker 测试逐值不变。`test_default_position_strength_zero_drift` 钉死。

### D3：闭式模型放哪、做哪些函数？（**低风险，先做**）
- **推荐**：`src/replay/core/analytic/models.py` **纯函数**（零引擎/状态耦合）：
  - `a_W(r, p_loss, w) -> float`：lost-frame replay 接受概率 = `1.0 if 0<=r<w else p_loss**(r-w+1)`（§6.2）。
  - `lar_w(w, q_reorder) -> float`：几何乱序可用性 = `1 - q_reorder**w`。
  - `p_forge(q, tag_bits) -> float`：`q / 2**tag_bits`。
  - `p_compromise(asr, n_attack) -> float`：`1 - (1-asr)**n_attack`。
  - `w_star(candidate_windows, *, q_reorder, lar_target, r_normal_by_w, r_crit_by_w, r_norm_target, r_crit_target) -> int | None`：
    在 `candidate_windows`（升序可迭代）里求满足全部约束的**最小 W**——
    `lar_w(W, q_reorder) >= lar_target ∧ r_normal_by_w[W] <= r_norm_target ∧ r_crit_by_w[W] <= r_crit_target`；
    无解返回 `None`。`r_normal_by_w`/`r_crit_by_w` 是 `{W: risk}` 映射（风险由调用方按策略表预算给定，纯函数不耦合引擎）。
- 单元测试纯数学边界（r<W→1、r=W→p_loss、单调性等）+ `w_star` 三类约束分别卡边界、无解返回 `None`。**先做（Task P0），与攻击者解耦。**

### D4：AdaptiveReplay 三策略怎么实现？（已拍板）
§6 增量3：①lost-frame 窗口（挑 `r<W` 的帧）②诱导 resync（挑已录制、counter gap 越闸的旧帧）③critical delayed（重放旧 critical REQ 赌无 PendingUserIntent）。
- **拍板：四个独立枚举值，本 Phase 不做自动 `"adaptive"`**：`attacker_strategy ∈ {"random","adaptive_lostframe","adaptive_resync","adaptive_critical"}`（`Literal`，默认 `"random"`）。实验矩阵每策略一组对比（§9，Phase 6）。
- **`AdaptiveReplay` 持 `context`**（W=`window_size`、`g_hard`、policy_table 等防御参数，引擎构造时注入），按策略筛候选帧 + 确定性挑选。
- **能力边界（§6，A2，测试钉死）**：只破不了 MAC（`P_forge≤q/2^ℓ_t`）、不猜 nonce、不绕状态机——只能在**已录制的合法帧**里挑/重排，不能伪造任何字段。具体到三策略：
  - `adaptive_lostframe`：从 `recorded` 里挑 `counter` 满足 `0 <= (h - frame.counter) < W`（落窗内、对应可能丢失的槽）的帧。
  - `adaptive_resync`：**不得伪造 far-future counter**；只能从 `recorded` 里挑一个**已录制合法帧**且其 counter 相对接收端当前 `state.last_counter`（=`h`）满足 `frame.counter - h > g_hard`（即触发 `needs_resync(n,h,g_hard)`：`n>h and (n-h)>g_hard`，见 `kernel/acceptance.py:25`）。若 `recorded` 里没有这种帧则 `pick` 返回 `None`（攻击无能为力，不得凭空造帧）。
  - `adaptive_critical`：从 `recorded` 里挑旧的 `FLAG_CRIT_PREPARE` 帧重放（赌 receiver 无 `PendingUserIntent`），不伪造 prepare/confirm。
- **blocker 测试**：`test_adaptive_resync_only_picks_recorded_gap_frames`（造一个 `recorded` 不含越闸帧的场景 → `pick` 必 `None`，证明不伪造）、`test_adaptive_cannot_forge_mac`。

### D4b：strategy 如何同时覆盖 live 与 paired 两条路径？（finding #3，已拍板）
现状 paired 路径（`experiment.py:675,804-812,876-877`）**完全绕过 `Attacker` 类**：自维护 `recorded` 列表 + `pick_replay(raw_pick)`（`candidates[raw_pick % len]`），用 `trace.replay_pick` 做确定性选择。若不补接线，`adaptive_*` 只在 live 路径生效。
- **拍板：`AttackerStrategy` 协议提供两个挑选入口，保证两条路径 baseline 都逐字节不变**：
  - `pick_frame(rng, *, context) -> Frame | None` —— **live 路径**用；`RandomReplay` = 现 `Attacker.pick_frame`（`rng.choice` 逻辑）字节一致。
  - `pick_recorded(raw_pick, recorded, *, context) -> Frame | None` —— **paired 路径**用；`RandomReplay` = 现 `pick_replay` 逻辑（`target_commands` 过滤 + `candidates[raw_pick % len]`）字节一致。
  - 记录入口 `observe`/`record`：live 复用 `observe(frame, rng)`；paired 由引擎按 `trace.attacker_record_dropped`（+D2 的 rx 联动）决定是否把帧交给 strategy 的 `recorded`。
- **接线**：paired 路径把 `recorded` 与 `pick_replay` 改为委托给 `strategy.pick_recorded(trace.replay_pick[replay_index], recorded, context=...)`；`RandomReplay` 实现逐值复刻现逻辑（`test_random_replay_matches_legacy_paired` blocker），`AdaptiveReplay` 在 `pick_recorded` 里先按策略筛候选、再用 `raw_pick` 做确定性挑选（paired 仍 trace-deterministic，不引入新 RNG 抽取）。
- **A1**：默认 `random` 下，live 与 paired 的 pick 序列都必须与现状逐值相同。

### D5：双重验证图怎么做、验收标准？（已拍板）
**核心：解析量与 MC 估计量必须是同一个量。`a_W(r, p_loss, w)` 是固定 offset `r` 的条件接受概率，所以 MC 必须固定 `r`，逐点比较——不是对随机 `r` 求边际。**
- **拍板（finding #2，二选一取 A）**：**固定 `r` 网格逐点比较**。定义 `R_GRID`（如 `{0,1,2,3,4,6,8}`）与 `W_GRID`（如 `{1,2,3,4,5,6,8,12}`），对每个 `(W, r, p_loss)` 三元组：
  - 解析点 = `a_W(r, p_loss, W)`；
  - MC 点 = 受控 MC 估计的 `P(accept | offset=r, w=W, p_loss)`。
  - （备选 B：先定义 `R` 的分布 `R_GRID`，比较 `mean_r a_W(r,...)` 与**同分布**采样的 MC。本计划取 A，因每个解析值都有同 `r` 的 MC 估计量一一对应，最可证伪；若改 B 需同时改 MC 采样为同分布。）
- **受控 MC（同时验证实现+模型）**：`scripts/plot_analytic_vs_mc.py` 用**真实 `Receiver` 窗口逻辑**（`receiver.process` / `classify`），在隔离 harness 里只变 `(r, w, p_loss)`——把 receiver 推进到已知 `h`，注入一个 offset 恰为 `r` 的重放帧，按 `p_loss` 抽信道丢弃，统计接受率。这样 MC 估的就是 `a_W` 同一条件概率，既测「`Receiver` 实现正确」又测「闭式模型正确」。**不用全 `SimulationConfig` 跑**（会混入 reorder/challenge/critical 等 confound，与 `a_W` 不是同一量）。
- 产出：每个 `(W,r,p_loss)` 的 ASR 散点 + 95% CI（`wilson_ci`），叠加解析 `a_W` 曲线；PNG/SVG + JSON（解析值、MC 均值、CI、n_trials）。
- **验收断言（blocker，A4）**：`tests/test_dual_verification.py`——**对 `R_GRID×W_GRID` 全部扫描点，解析 `a_W(r,p_loss,W)` 落入该点 MC 95% CI**（不是事后凑阈值）。
- 脚本用 matplotlib（仅脚本依赖，不进 core/ 运行时）。

### D6：契约面到哪？
- **推荐**：`SimulationSpec` 加 `attacker_strategy`/`attacker_position`/`attacker_inject_strength`（Literal，默认 random/ind/strong）+ to_config 透传 + TS/static fallback。**可选观测计数**：`attack_attempts_by_strategy` 较重，**先不加**；本 Phase 复用现有 `attack_success/attack_attempts`（不改归因，仅新增攻击者选择维度）。
- **不动**：`attack_success/legit_accepted` 归因语义（攻击者增强只改"攻击者怎么选帧/信道概率"，不改"什么算 accept/attack success"）。

> **已拍板（2026-06-08 review）：** D1=AttackerStrategy 抽象（random 默认零漂移）✅；D2=位置×强度映射表已定稿（`ind/strong`=现状零漂移，`tx/rx/weak` opt-in，附 live/paired 落地语义）✅；D3=`analytic/models.py` 纯函数先做，`w_star` 签名已定 ✅；D4=四独立枚举值 `random/adaptive_lostframe/adaptive_resync/adaptive_critical`（不做自动 `"adaptive"`）+ 能力边界写死（adaptive_resync 只挑越闸已录制帧、不伪造）✅；D4b=strategy 双入口覆盖 live+paired（`pick_frame`/`pick_recorded`）✅；D5=固定 `r` 网格逐点、受控 MC 复用真实 `Receiver`、解析∈MC-CI 验收 ✅；D6=`SimulationSpec` 加 attacker 三字段、**不动归因**✅。
> **唯一可回退点**：D5 取方案 A（固定 `r` 逐点）；若你要方案 B（R 分布取均值）告知即可切。

---

## 硬约束（贯穿，blocker 守门）

1. **(A1) baseline 零漂移**：`attacker_strategy="random"` + `(ind,strong)` 默认 → **live 与 paired 两条路径都**逐值等于现状（rng 抽取顺序、`raw_pick % len` 逻辑、trace 数组长度字节一致）；`STABLE_MODES` 与所有现有 attacker 测试零改动通过。
2. **(A2) 攻击者能力边界**：AdaptiveReplay 只能挑/重排**已录制的合法帧**，不能伪造 MAC/猜 nonce/绕状态机（§6）。**特别地 `adaptive_resync` 不得凭空造 far-future counter**——只能选已录制且 `frame.counter - h > g_hard` 的帧，否则 `pick` 返回 `None`。测试钉死。
3. **(A3) 闭式纯函数**：`analytic/models.py` 零引擎/状态耦合，纯数学；与攻击者解耦先做。
4. **(A4) 双重验证可证伪**：MC 与解析必须是**同一个量**——`a_W(r,p_loss,w)` 固定 `r`，故 MC 固定 `r` 逐点估 `P(accept|offset=r)`；`R_GRID×W_GRID` 全扫描点解析值落入该点 MC CI（不是事后凑），blocker 钉死。
5. **(A5) 不动归因/指标体系**：不改 `attack_success/legit_accepted` 语义；完整 metrics/实验矩阵留 Phase 6。
6. **回归零影响**：`test_engine_baseline_regression`(STABLE_MODES) 逐值相等。
> 引用 @superpowers:test-driven-development、@superpowers:verification-before-completion。

---

## 当前形态速查（@ 4b22e39）

- `src/replay/core/attacker.py`：`Attacker{record_loss, target_commands, _recorded}` + `observe`/`pick_frame`/`clear`。**无 strategy 抽象、无 adaptive。**
- `src/replay/core/experiment.py`：**两条路径攻击者实现不同**——
  - **live 路径**（`275`,`421-440`）：构造 `Attacker(record_loss=..., target_commands=...)`，`record_tx → observe(before send) → channel.send`，attack 帧 `pick_frame(local_rng)` + `channel.send`。
  - **paired 路径**（`675`,`804-833`,`876-877`）：**完全不用 `Attacker` 类**，自维护 `recorded` 列表 + `pick_replay(raw_pick)=candidates[raw_pick % len]`，记录靠 `trace.attacker_record_dropped`、attack 帧送达靠 `trace.replay_dropped/replay_delay`、确定性选择靠 `trace.replay_pick`。→ Phase 5 接线必须同时覆盖此路径（D4b）。
- `src/replay/core/trace.py`：`generate_trace` 抽 `legit_dropped`/`attacker_record_dropped`/`replay_pick`/`replay_dropped`（`71-86`）；resync/critical/reboot 数组**末尾追加**保非相关模式零漂移（D2 weak 的 `attack_extra_dropped` 沿用此技巧）。
- `src/replay/core/types.py`：`SimulationConfig` 有 `attacker_record_loss`/`inline_attack_*`；**无 attacker_position/strategy/inject_strength**。
- `src/replay/core/stats.py`：`wilson_ci`（双重验证 CI 用）。
- `src/replay/core/`：**无 `analytic/` 包**。
- 回归安全网：`tests/test_engine_baseline_regression.py`（STABLE_MODES）+ 现有 attacker 相关测试。

---

## Phase 5 · Tasks

> 门：analytic 单元 + attacker 策略 + 双重验证 blocker 全绿 + `test_engine_baseline_regression`(STABLE_MODES) 逐值相等 + 全量 pytest 绿 + ruff/mypy 不退化 + check-contracts + `npm run build` 绿。

### Task P0：`core/analytic/models.py` 闭式模型（纯函数，先做，低风险）

**Files:** Create `src/replay/core/analytic/__init__.py`、`src/replay/core/analytic/models.py`；Test `tests/test_analytic_models.py`

**要点：** `a_W`/`lar_w`/`p_forge`/`p_compromise`/`w_star` 纯函数（D3）。`w_star` 用 D3 定稿签名 `w_star(candidate_windows, *, q_reorder, lar_target, r_normal_by_w, r_crit_by_w, r_norm_target, r_crit_target) -> int | None`。测试钉数学边界：`a_W(r<w)==1.0`、`a_W(r=w)==p_loss`、`a_W` 对 r 单调非增、`lar_w` 对 w 单调增、`p_compromise(asr,N)` 随 N 增、`p_forge` 量纲；`w_star` 三约束分别卡边界 + 无解返回 `None`。
**Step 5:** 提交 `feat: add closed-form analytic models (a_W/LAR/P_forge/P_compromise/W*)`。

### Task P1：`AttackerStrategy` 抽象 + `RandomReplay` baseline（零漂移搬迁）

**Files:** Modify `src/replay/core/attacker.py`（抽 `AttackerStrategy` 协议 + `RandomReplay` = 现逻辑）；Test `tests/test_attacker_strategy.py`

**要点（D1+D4b）：** `AttackerStrategy` 协议双挑选入口——`pick_frame(rng, *, context)`（live）+ `pick_recorded(raw_pick, recorded, *, context)`（paired）+ `observe(frame, rng)`。`RandomReplay`：`pick_frame` 复刻现 `Attacker.pick_frame`（`rng.choice`）、`pick_recorded` 复刻现 paired `pick_replay`（`target_commands` 过滤 + `candidates[raw_pick % len]`），**两入口都逐字节等价**。`Attacker` 保留为 `RandomReplay` 别名或薄壳，**现有引擎构造与所有 attacker 测试零改动通过**（A1）。
- **blocker：** `test_random_replay_matches_legacy_attacker`（live：同 seed/同录制 → pick 序列逐值相同）、`test_random_replay_matches_legacy_paired`（paired：同 `trace.replay_pick` → `candidates[raw_pick % len]` 逐值相同）。
**Step 5:** 提交 `feat: extract AttackerStrategy with RandomReplay baseline (byte-identical, live+paired)`。

### Task P2：位置×强度映射（默认=现状，A1）

**Files:** Modify `src/replay/core/types.py`（`attacker_position: Literal["ind","tx","rx"]="ind"`/`attacker_inject_strength: Literal["strong","weak"]="strong"`）、`src/replay/core/experiment.py`（live：rx 把 observe 移到送达后、weak 加 attack-only 抽签）、`src/replay/core/trace.py`（paired：rx 用 `legit_dropped` 联动；weak 末尾追加 `attack_extra_dropped` 数组）；Test `tests/test_attacker_position.py`

**要点（D2 定稿表）：**
- `P_record`：ind=`1-record_loss`（默认）/ tx=`1.0` / rx=`(1-p_loss)*(1-record_loss)`。
- `P_deliver^A`：strong=`1-p_loss`（默认）/ weak=`0.5*(1-p_loss)`。
- **零漂移纪律**：`(ind,strong)` 走原调用顺序、原抽签序、原 trace 数组长度（不加 `attack_extra_dropped`）；`tx/rx/weak` 全 opt-in。weak 的 `attack_extra_dropped` 必须**追加在 `generate_trace` 末尾**（§append 技巧），非 weak 不抽。
- **blocker：** `test_default_position_strength_zero_drift`（默认组合 live+paired 逐值等于现状 + `STABLE_MODES` 不变）、`test_rx_records_only_delivered`、`test_weak_extra_drop_appended_no_baseline_drift`。
**Step 5:** 提交 `feat: add attacker position x strength channel mapping (default unchanged)`。

### Task P3：`AdaptiveReplay` 三策略（D4/D4b 已定稿）

**Files:** Modify `src/replay/core/attacker.py`（`AdaptiveReplay` + context 注入，实现 `pick_frame`+`pick_recorded`）、`src/replay/core/experiment.py`（按 `attacker_strategy` 选 strategy + 注入防御 context + paired 路径委托 `pick_recorded`，D4b）、`src/replay/core/types.py`（`attacker_strategy: Literal["random","adaptive_lostframe","adaptive_resync","adaptive_critical"]="random"`）；Test `tests/test_adaptive_attacker.py`

**要点（D4/D4b）：** 三策略 + **覆盖 live 与 paired**（paired 经 `pick_recorded` 委托，不引入新 RNG 抽取，仍 trace-deterministic）。能力边界（A2，只挑/重排已录制合法帧，不伪造任何字段）：
- `adaptive_lostframe`：挑 `0 <= h - frame.counter < W` 的帧。
- `adaptive_resync`：只挑 `frame.counter - h > g_hard`（触发 `needs_resync`）的**已录制**帧；无则返回 `None`，**绝不造 far-future counter**。
- `adaptive_critical`：重放旧 `FLAG_CRIT_PREPARE` 帧，不伪造 prepare/confirm。
- **blocker：** `test_adaptive_lostframe_targets_r_lt_W`、`test_adaptive_resync_only_picks_recorded_gap_frames`（无越闸帧→`None`，钉死不伪造）、`test_adaptive_critical_replays_old_req`、`test_adaptive_cannot_forge_mac`、`test_adaptive_works_in_paired_path`（paired 也生效）、`test_adaptive_vs_random_asr_differs`（对抗实验）。
**Step 5:** 提交 `feat: add AdaptiveReplay strategies (lost-frame/induce-resync/critical-delayed, live+paired)`。

### Task P4：双重验证图 + 验收（增量1/3）

**Files:** Create `scripts/plot_analytic_vs_mc.py`；Test `tests/test_dual_verification.py`

**要点（D5，方案 A 固定 `r` 逐点）：** 定义 `R_GRID`（如 `{0,1,2,3,4,6,8}`）、`W_GRID`（如 `{1,2,3,4,5,6,8,12}`）；**受控 MC 复用真实 `Receiver` 窗口逻辑**——把 receiver 推到已知 `h`、注入 offset 恰为 `r` 的重放帧、按 `p_loss` 抽信道丢弃、统计接受率（不跑全 `SimulationConfig`，避免 reorder/challenge confound）。每个 `(W,r,p_loss)`：MC ASR ± `wilson_ci` 95% CI，叠解析 `a_W(r,p_loss,W)`；产 PNG/SVG + JSON（解析值/MC 均值/CI/n_trials）。
- **blocker（A4）：** `test_analytic_within_mc_ci`——`R_GRID×W_GRID` **全扫描点**解析 `a_W` 落入该点 MC 95% CI（同一条件概率，非事后凑阈值）。
**Step 5:** 提交 `feat: add analytic-vs-MC dual-verification plot and acceptance test`。

### Task P5：契约同步（attacker 三字段，D6 已定稿）

**Files:** Modify `src/replay/contracts/models.py`（`SimulationSpec`+`SimulationSpecPublic` 加三字段 + to_config/from_spec）、`src/replay/contracts/typescript.py`、`web/scripts/check-contracts.mjs`、`web/lib/static-simulator.ts`、`web/components/simulator-panel.tsx`（DEFAULT_SPEC）；Test `tests/test_contract_attacker.py`。重生成 `contracts.ts`/`contracts.json`。

**要点：** `attacker_strategy`/`attacker_position`/`attacker_inject_strength`（Literal，默认 random/ind/strong）贯通 spec→config→TS→web。**含 G5/G9 教训**：`npm run build` 若报 `DEFAULT_SPEC/publicSpec` 缺字段，连 `simulator-panel.tsx`/`static-simulator.ts` 一起补默认值。
**Step 5:** 提交 `feat: expose attacker strategy/position/strength in contracts and TS`。

> **Phase 5 门（用 @superpowers:verification-before-completion 核验）：**
> - blocker 全绿：`test_random_replay_matches_legacy_attacker`、`test_random_replay_matches_legacy_paired`、`test_default_position_strength_zero_drift`、`test_adaptive_cannot_forge_mac`、`test_adaptive_resync_only_picks_recorded_gap_frames`、`test_adaptive_works_in_paired_path`、`test_analytic_within_mc_ci`
> - analytic 单元 + attacker 策略 + 双重验证 + 契约 全绿
> - `test_engine_baseline_regression`(STABLE_MODES) 逐值相等
> - 全量 pytest 绿 + ruff/mypy 不退化 + check-contracts + `npm run build` 双绿
> - **A5 复核**：grep 确认未改 `attack_success/legit_accepted` 归因；未提前做 `core/metrics.py` 全套

---

## 执行建议

- 顺序：P0（analytic，解耦先做）→ P1（strategy 抽象 + baseline 零漂移，**live+paired 双入口**）→ P2（位置×强度，D2 表）→ P3（adaptive，**覆盖 paired**）→ P4（双重验证，固定 `r` 受控 MC）→ P5（契约）。
- **D1–D6 已拍板（见上）**，全程可逐 Task 执行；每个 Task 后跑零漂移自查。
- **P1 的 paired 委托是 P3 adaptive 在 paired 生效的前提**——P1 必须先把 `pick_recorded` 接进 paired 路径并证明字节一致，否则 P3 只在 live 生效。
- 每个 Task 后跑 `test_engine_baseline_regression`(STABLE_MODES) 自查零漂移（A1）。
- **带入 Phase 2/3/4 + G5/G9 教训**：(a) baseline 零漂移靠默认 opt-out + rng 序列字节一致；(b) 能力边界测试钉死（不伪造 MAC）；(c) 契约六段导出面 + web fallback（simulator-panel/static-simulator）别漏；(d) **不顺手做全套 metrics/实验矩阵（留 Phase 6）**。
- Phase 5 门绿后，另开 **Phase 6（指标体系 §8 + 实验矩阵/消融 §9）**，回填 ASR 双口径 / 经验 P_compromise / 零观测 UCB / 全矩阵脚本。
