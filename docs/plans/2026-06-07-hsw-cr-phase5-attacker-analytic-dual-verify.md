# HSW-CR Phase 5 · 自适应攻击者 + 闭式数学模型 + 双重验证 — 逐行 TDD 实施计划

> **For Claude:** REQUIRED SUB-SKILL: 用 `superpowers:executing-plans` 逐任务实施本计划。
> 本文件是主计划 `docs/plans/2026-06-07-hsw-cr-full-protocol-overhaul.md` **§6/§7（G7+G10+增量1+增量3）** 的执行细化，对照 Phase 0–4 + G5/G9 落地后的真实主线（`origin/main` @ `4b22e39`）展开。**执行前先确认下方「待拍板的关键设计决策」。**

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

## 待拍板的关键设计决策（执行前必须确认）

### D1：攻击者怎么抽象？baseline 怎么保零漂移？
- **推荐**：抽 `AttackerStrategy` 协议（`observe(frame, rng)` + `pick_frame(rng, *, context) -> Frame | None`）。`RandomReplay` = **现有 `Attacker` 逻辑原样搬过去**（observe 带 record_loss、pick_frame 随机/按 target_commands），作为 baseline。`AdaptiveReplay` 新增。
- `SimulationConfig.attacker_strategy: str = "random"`（默认）。引擎据此 new strategy。**默认 random + 调用序列不变 → baseline 逐值零漂移**（关键：rng 抽取顺序、pick 逻辑必须与现状字节一致）。
- 备选否决：直接在 `Attacker` 里加 if/else 分支（违反 OCP，且容易扰动 baseline rng 序列）。

### D2：位置 x × 强度 g 怎么建模？（**G10 安全核心**）
§6：`x ∈ {x_tx, x_rx, x_ind}`、`g ∈ {strong, weak}`，影响 `P_record`（记录成功率）与 `P_deliver^A`（攻击帧送达率）。
- **推荐**：新增 `SimulationConfig.attacker_position: str = "ind"`、`attacker_inject_strength: str = "strong"`，映射到两个概率：
  - `P_record`：x_tx 高（能录到接收端没收到的帧→lost-frame 风险高）、x_rx 低（重复重放易被窗口拒）、x_ind 取决于捕获质量（用现有 `attacker_record_loss` 表达，即 P_record=1-record_loss）。
  - `P_deliver^A`：strong 高送达、weak 低送达（攻击帧经信道时额外的丢弃概率）。
- **零漂移约束**：默认 `(ind,strong)` 必须映射到**现状行为**（P_record=1-record_loss、P_deliver=现有信道 p_loss，不额外丢）。非默认组合才改变概率。
- **请你裁决映射表的具体数值**（每个 (x,g) → (P_record, P_deliver^A) 系数）——这是论文威胁模型参数，需与 §6 对齐；本计划先给占位映射，确认后定稿。

### D3：闭式模型放哪、做哪些函数？（**低风险，先做**）
- **推荐**：`src/replay/core/analytic/models.py` **纯函数**（零引擎/状态耦合）：
  - `a_W(r, p_loss, w) -> float`：lost-frame replay 接受概率 = `1.0 if 0<=r<w else p_loss**(r-w+1)`（§6.2）。
  - `lar_w(w, q_reorder) -> float`：几何乱序可用性 = `1 - q_reorder**w`。
  - `p_forge(q, tag_bits) -> float`：`q / 2**tag_bits`。
  - `p_compromise(asr, n_attack) -> float`：`1 - (1-asr)**n_attack`。
  - `w_star(...)`：窗口目标 `min{W: LAR(W)>=LAR_target ∧ R_normal(W)<=... ∧ R_crit(W)<=...}`（给定 target 求最小 W）。
- 单元测试纯数学边界（r<W→1、r=W→p_loss、单调性等）。**先做（Task P0），与攻击者解耦。**

### D4：AdaptiveReplay 三策略怎么实现？
§6 增量3：①lost-frame 窗口（挑 `r<W` 的帧）②诱导 resync（发 ctr 大跳跃帧绕窗）③critical delayed（重放旧 critical REQ 赌无 PendingUserIntent）。
- **推荐**：`AdaptiveReplay` 持 `context`（W、g_hard、policy_table 等防御参数，引擎构造时注入），`pick_frame` 按策略选最优帧。三策略可由 `attacker_strategy ∈ {"adaptive_lostframe","adaptive_resync","adaptive_critical"}` 或一个组合 `"adaptive"` 选择。
- **能力边界（§6）**：不破 MAC（`P_forge≤q/2^ℓ_t`）、不猜 nonce、不绕状态机——AdaptiveReplay 只能在**已录制的合法帧**里挑/重排，不能伪造。测试钉死这条。
- **请确认**：三策略是各自独立 `attacker_strategy` 值，还是一个 `"adaptive"` 内部自动选？推荐**各自独立值**（实验矩阵每策略一组对比，§9）。

### D5：双重验证图怎么做、验收标准？
- **推荐**：`scripts/plot_analytic_vs_mc.py`：扫 `W∈{1,2,3,4,5,6,8,12}`，对每个 W 跑 MC（lost-frame replay 场景）得 ASR 散点 + 95% CI（`wilson_ci`），叠加解析 `a_W` 曲线。产出 PNG/SVG + 一个 JSON（解析值、MC 均值、CI）。
- **验收断言（blocker）**：`tests/test_dual_verification.py`——在扫描点上**解析值落入 MC 95% CI**（或相对偏差 < 阈值）。这一图同时证明「实现正确 + 模型正确」。
- 脚本用 matplotlib（仅脚本依赖，不进 core/ 运行时）。

### D6：契约面到哪？
- **推荐**：`SimulationSpec` 加 `attacker_strategy`/`attacker_position`/`attacker_inject_strength`（Literal，默认 random/ind/strong）+ to_config 透传 + TS/static fallback。**可选观测计数**：`attack_attempts_by_strategy` 较重，**先不加**；本 Phase 复用现有 `attack_success/attack_attempts`（不改归因，仅新增攻击者选择维度）。
- **不动**：`attack_success/legit_accepted` 归因语义（攻击者增强只改"攻击者怎么选帧/信道概率"，不改"什么算 accept/attack success"）。

> **请确认 D1=AttackerStrategy 抽象（random 默认零漂移）、D2=位置×强度映射（默认=现状；映射数值待你定）、D3=analytic/models.py 纯函数先做、D4=AdaptiveReplay 三独立策略 + 能力边界、D5=双重验证图 + 解析∈MC-CI 验收、D6=SimulationSpec 加 attacker 三字段、不动归因。** 确认后我把「攻击者接线 + 双重验证」Task 逐行定稿。

---

## 硬约束（贯穿，blocker 守门）

1. **(A1) baseline 零漂移**：`attacker_strategy="random"` + `(ind,strong)` 默认 → 逐值等于现状（rng 抽取顺序、pick 逻辑字节一致）；`STABLE_MODES` 与所有现有 attacker 测试零改动通过。
2. **(A2) 攻击者能力边界**：AdaptiveReplay 只能挑/重排**已录制的合法帧**，不能伪造 MAC/猜 nonce/绕状态机（§6）。
3. **(A3) 闭式纯函数**：`analytic/models.py` 零引擎/状态耦合，纯数学；与攻击者解耦先做。
4. **(A4) 双重验证可证伪**：解析 vs MC 在扫描点须落入 CI（不是事后凑），blocker 测试钉死。
5. **(A5) 不动归因/指标体系**：不改 `attack_success/legit_accepted` 语义；完整 metrics/实验矩阵留 Phase 6。
6. **回归零影响**：`test_engine_baseline_regression`(STABLE_MODES) 逐值相等。
> 引用 @superpowers:test-driven-development、@superpowers:verification-before-completion。

---

## 当前形态速查（@ 4b22e39）

- `src/replay/core/attacker.py`：`Attacker{record_loss, target_commands, _recorded}` + `observe`/`pick_frame`/`clear`。**无 strategy 抽象、无 adaptive。**
- `src/replay/core/experiment.py`：两路径构造 `Attacker(record_loss=config.attacker_record_loss, target_commands=...)`；attack 帧经 `channel.send` / `attempt_replay`（trace）。
- `src/replay/core/types.py`：`SimulationConfig` 有 `attacker_record_loss`/`inline_attack_*`；**无 attacker_position/strategy/inject_strength**。
- `src/replay/core/stats.py`：`wilson_ci`（双重验证 CI 用）。
- `src/replay/core/`：**无 `analytic/` 包**。
- 回归安全网：`tests/test_engine_baseline_regression.py`（STABLE_MODES）+ 现有 attacker 相关测试。

---

## Phase 5 · Tasks

> 门：analytic 单元 + attacker 策略 + 双重验证 blocker 全绿 + `test_engine_baseline_regression`(STABLE_MODES) 逐值相等 + 全量 pytest 绿 + ruff/mypy 不退化 + check-contracts + `npm run build` 绿。

### Task P0：`core/analytic/models.py` 闭式模型（纯函数，先做，低风险）

**Files:** Create `src/replay/core/analytic/__init__.py`、`src/replay/core/analytic/models.py`；Test `tests/test_analytic_models.py`

**要点：** `a_W`/`lar_w`/`p_forge`/`p_compromise`/`w_star` 纯函数（D3）。测试钉数学边界：`a_W(r<w)==1.0`、`a_W(r=w)==p_loss`、`a_W` 对 r 单调非增、`lar_w` 对 w 单调增、`p_compromise(asr,N)` 随 N 增、`p_forge` 量纲。
**Step 5:** 提交 `feat: add closed-form analytic models (a_W/LAR/P_forge/P_compromise/W*)`。

### Task P1：`AttackerStrategy` 抽象 + `RandomReplay` baseline（零漂移搬迁）

**Files:** Modify `src/replay/core/attacker.py`（抽 `AttackerStrategy` 协议 + `RandomReplay` = 现逻辑）；Test `tests/test_attacker_strategy.py`

**要点：** `RandomReplay` 与现 `Attacker.observe/pick_frame` **逐行等价**（rng 序列、pick 逻辑字节一致）。`Attacker` 保留为 `RandomReplay` 的别名或薄壳，**现有引擎构造与所有 attacker 测试零改动通过**（A1）。
- **blocker：** `test_random_replay_matches_legacy_attacker`（同 seed/同录制 → pick 序列逐值相同）。
**Step 5:** 提交 `feat: extract AttackerStrategy with RandomReplay baseline (byte-identical)`。

### Task P2：位置×强度映射（默认=现状，A1）

**Files:** Modify `src/replay/core/types.py`（`attacker_position`/`attacker_inject_strength`）、`src/replay/core/attacker.py`/`experiment.py`（映射到 P_record/P_deliver）；Test `tests/test_attacker_position.py`

**要点（D2 确认后定稿数值）：** `(ind,strong)` 默认 → P_record=1-record_loss、P_deliver=现状（零漂移）。非默认组合改变记录/送达概率。
- **blocker：** `test_default_position_strength_zero_drift`（默认组合逐值等于现状）。
**Step 5:** 提交 `feat: add attacker position x strength channel mapping (default unchanged)`。

### Task P3：`AdaptiveReplay` 三策略（**D2/D4 确认后定稿**）

**Files:** Modify `src/replay/core/attacker.py`（`AdaptiveReplay` + context 注入）、`src/replay/core/experiment.py`（按 `attacker_strategy` 选 strategy + 注入防御 context）、`src/replay/core/types.py`（`attacker_strategy`）；Test `tests/test_adaptive_attacker.py`

**要点：** 三策略（lost-frame 窗口 / 诱导 resync / critical delayed）；只挑/重排已录制合法帧（A2，不伪造）。
- **blocker：** `test_adaptive_lostframe_targets_r_lt_W`、`test_adaptive_critical_replays_old_req`、`test_adaptive_cannot_forge_mac`（能力边界）、`test_adaptive_vs_random_asr_differs`（对抗实验）。
**Step 5:** 提交 `feat: add AdaptiveReplay strategies (lost-frame/induce-resync/critical-delayed)`。

### Task P4：双重验证图 + 验收（增量1/3）

**Files:** Create `scripts/plot_analytic_vs_mc.py`；Test `tests/test_dual_verification.py`

**要点（D5）：** 扫 `W∈{1,2,3,4,5,6,8,12}`，MC lost-frame ASR ± `wilson_ci` 95% CI，叠 `a_W` 解析曲线；产 PNG/SVG + JSON。
- **blocker：** `test_analytic_within_mc_ci`（扫描点解析 `a_W` 落入 MC 95% CI，A4）。
**Step 5:** 提交 `feat: add analytic-vs-MC dual-verification plot and acceptance test`。

### Task P5：契约同步（attacker 三字段，**D6 确认后定稿**）

**Files:** Modify `src/replay/contracts/models.py`（`SimulationSpec`+`SimulationSpecPublic` 加三字段 + to_config/from_spec）、`src/replay/contracts/typescript.py`、`web/scripts/check-contracts.mjs`、`web/lib/static-simulator.ts`、`web/components/simulator-panel.tsx`（DEFAULT_SPEC）；Test `tests/test_contract_attacker.py`。重生成 `contracts.ts`/`contracts.json`。

**要点：** `attacker_strategy`/`attacker_position`/`attacker_inject_strength`（Literal，默认 random/ind/strong）贯通 spec→config→TS→web。**含 G5/G9 教训**：`npm run build` 若报 `DEFAULT_SPEC/publicSpec` 缺字段，连 `simulator-panel.tsx`/`static-simulator.ts` 一起补默认值。
**Step 5:** 提交 `feat: expose attacker strategy/position/strength in contracts and TS`。

> **Phase 5 门（用 @superpowers:verification-before-completion 核验）：**
> - blocker 全绿：`test_random_replay_matches_legacy_attacker`、`test_default_position_strength_zero_drift`、`test_adaptive_cannot_forge_mac`、`test_analytic_within_mc_ci`
> - analytic 单元 + attacker 策略 + 双重验证 + 契约 全绿
> - `test_engine_baseline_regression`(STABLE_MODES) 逐值相等
> - 全量 pytest 绿 + ruff/mypy 不退化 + check-contracts + `npm run build` 双绿
> - **A5 复核**：grep 确认未改 `attack_success/legit_accepted` 归因；未提前做 `core/metrics.py` 全套

---

## 执行建议

- 顺序：P0（analytic，解耦先做）→ P1（strategy 抽象 + baseline 零漂移）→ **【确认 D1–D6（尤其 D2 映射数值、D4 三策略）】** → P2（位置×强度）→ P3（adaptive）→ P4（双重验证）→ P5（契约）。
- P0/P1 歧义低，确认前即可开工；**P2–P5 等 D 拍板后逐行**。
- 每个 Task 后跑 `test_engine_baseline_regression`(STABLE_MODES) 自查零漂移（A1）。
- **带入 Phase 2/3/4 + G5/G9 教训**：(a) baseline 零漂移靠默认 opt-out + rng 序列字节一致；(b) 能力边界测试钉死（不伪造 MAC）；(c) 契约六段导出面 + web fallback（simulator-panel/static-simulator）别漏；(d) **不顺手做全套 metrics/实验矩阵（留 Phase 6）**。
- Phase 5 门绿后，另开 **Phase 6（指标体系 §8 + 实验矩阵/消融 §9）**，回填 ASR 双口径 / 经验 P_compromise / 零观测 UCB / 全矩阵脚本。
