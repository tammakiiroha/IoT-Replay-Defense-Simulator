# HSW-CR G5/G9 · 命令风险二分类 Policy Table + 三冻结 Profile — 逐行 TDD 实施计划

> **For Claude:** REQUIRED SUB-SKILL: 用 `superpowers:executing-plans` 逐任务实施本计划。
> 本文件是主计划 `docs/plans/2026-06-07-hsw-cr-full-protocol-overhaul.md` **§3b/§5（G5+G9）** 的执行细化，对照 Phase 0–4 落地后的真实主线（`origin/main` @ `cef2222`）展开。**执行前先确认下方「待拍板的关键设计决策」。**

**Goal:** 把 HSW_CR 当前「连续阈值 `command_risk.get(c) >= risk_high(0.8)`」的 normal/critical 二分类，升级为忠实实现 §3b 的 **Policy Table**：六维影响度 `I(c)=max_k H_k(c)` + 三触发线 + **strict/standard/permissive 三组冻结 Profile**，部署前离线算好、运行时 O(1) 查表。

**Architecture:** 新增 `core/policy.py`（纯函数 + 数据：`H_k` 向量 → `I(c)` → 三触发线 → 三 Profile → **构造时离线算好 `PolicyTable`**）。`SimulationConfig`/`Receiver` 加 `policy_source`（legacy/default_table/custom，**默认 legacy**）+ `profile` + 每命令 `command_impact`。`Receiver` 与两条引擎路径各**预构建一次 `policy_table`**；3 处分类点（`verify_hsw_cr` 路由、`process_crit_prepare` not_critical 门、`_is_two_phase_critical`）运行时**只调 `policy_table.is_critical(cmd)`**（O(1)，单一真相）。legacy 与 policy 两种判定都收敛进同一个 `PolicyTable`。契约层 `SimulationSpec` 加 `profile`+`policy_source`。

**Tech Stack:** Python 3.9+、现有 `core/`（receiver/experiment/types/commands）、pytest。环境：`.venv/bin/python`，`PYTHONPATH=src:.`，命令前若 cwd 漂移先 `cd /Users/romeitou/Desktop/論文/Replay`。

---

## ⚠️ 范围澄清（务必先读）

- 本计划 = **G5（normal/critical 二分类 + Policy Table）+ G9（三冻结 Profile）** 的**机制**。
- **做**：`I(c)=max H_k` 六维影响度；三触发线（**θ_I 全量；θ_R/ΔU 见 D3 待拍板**）；strict/standard/permissive 三 Profile（θ_I/θ_R/λ 冻结常量，禁运行时反向调参）；预计算 O(1) `is_critical`；3 处分类点改走 policy；契约 `profile`。
- **不做（留后续 Phase，单独 PR）**：设备适用性 **A/B/C/D 判级（§3a）**——相关但可分离，本 Phase 只做命令分类；多设备命令集（车/锁/插座）实验矩阵（可在 policy 机制上后接）；attacker `P_succ` 四步链与闭式 `R̃/ΔU` 的**完整**实现（属 **Phase 5** §6/§7，见 D3）。
- 回归守门：分类仅影响 **HSW_CR**；`STABLE_MODES`（NO_DEFENSE/ROLLING/WINDOW/CHALLENGE/OSCORE）不经命令分类 → 必须零漂移。

---

## 待拍板的关键设计决策（执行前必须确认）

### D1：`policy.py` 放哪？
- **推荐**：`src/replay/core/policy.py`（§3b 指定 `core/policy.py`）。它是**策略/配置**层，不是密码学 kernel 原语，故不进 `core/kernel/`。纯函数 + 冻结数据。

### D2：H_k 影响度从哪来、怎么表达？（含**显式激活模型**，修审查 P1）
- **推荐**：每命令一个 6 维向量 `H_k(c) ∈ {0..4}`，维度 `K={phys, property, privacy, availability, auth, recovery}`（§5）。新增 `SimulationConfig.command_impact: dict[str, tuple[int,int,int,int,int,int]] | None`。`I(c) = max(H_k(c))`。
- 默认主线命令集给一张**冻结** H_k 表（如 `UNLOCK/LOCK/PAIRING/ENABLE_POWER/FACTORY_RESET/FWD/SET_SPEED/...`），放 `policy.py` 常量 `DEFAULT_COMMAND_IMPACT`。`SET_SPEED` 的 normal/critical 争议按 §3b 就地由 H_k(phys) 决定（论文讨论项，不在代码里特判）。

#### ★ 激活模型（修审查 P1：`DEFAULT_COMMAND_IMPACT` / 回退 / Web 只暴露 profile 三者必须无歧义）
显式三态开关 `SimulationConfig.policy_source: Literal["legacy","default_table","custom"] = "legacy"`：
- **`"legacy"`（默认，不变 P4）**：忽略 policy table，分类**完全等于**旧 `command_risk>=risk_high`。Phase 0–4 既有 HSW_CR 测试、baseline、Web 现状**零改动**。**`profile` 在 legacy 下不生效**（避免「看似可选实则无效」）。
- **`"default_table"`**：用 `DEFAULT_COMMAND_IMPACT` + 选定 `profile` 构建 PolicyTable。`profile` 此时**生效**。
- **`"custom"`**：用显式提供的 `SimulationConfig.command_impact` + `profile` 构建。`command_impact is None` 时报错（fail-fast，不静默回退）。
- **关键**：默认表**不**自动激活（否则一启用就破 P4）；`profile` 只有在 `policy_source != "legacy"` 时才影响判定。Web/API 先只暴露 `profile` + `policy_source`（不暴露重的 `command_impact`，留 UI/API phase），但 `policy_source="custom"` 在 Web 下因无 `command_impact` 会被拒——Web 仅允许 `legacy`/`default_table`（见 D6）。

### D3：三触发线做到哪一条？（**关键 scope 决策**）
§5 触发线：`c∈C_critical ⟺ I(c)≥θ_I ∨ R̃_SW(c)≥θ_R ∨ ΔU(c)>0`。
- **θ_I 行**：`I(c)≥θ_I`，**全确定、无外部依赖**，本 Phase **全量实现**。
- **θ_R / ΔU 行**：`R̃_SW(c)=(I(c)/4)·P_succ,SW(c)`、`ΔU(c)=[R̃_SW-R̃_CR]-λ·[Cost_CR-Cost_SW]`——依赖 attacker **四步链 `P_succ`（§6）** 与 Cost 模型，而 attacker/闭式模型是 **Phase 5** 的内容。在 Phase 5 之前没有权威 `P_succ` 来源。
- **推荐（A，与用户「G5/G9 先于 Phase 5」一致）**：本 Phase **θ_I 行为主**，`PolicyTable` 接口**预留** `risk_sw`/`delta_u` 两个**可选输入**（caller 提供则参与 OR 判定，不提供则该行不激活）。**完整 P_succ 驱动的 θ_R/ΔU 推迟到 Phase 5 接 attacker 模型时填**。三 Profile 的 θ_R/λ 常量先**定义并冻结**（备用），但 G5/G9 验收只断言 θ_I 行为。
- **备选（B）**：本 Phase 就实现简化版 `P_succ,SW`（静态信道近似，不含 adaptive attacker）。**否决理由**：会先于 Phase 5 引入一套「攻击评估口径」，正是用户要避免的「同时改防御策略 + 攻击评估」。
- **请你裁决 A/B。** 推荐 A。

### D4：三 Profile 怎么表达？
- **推荐**：`policy.py` 冻结常量表（`Profile` = `str` Enum: strict/standard/permissive；`PROFILE_PARAMS: dict[Profile, ProfileParams]`，`ProfileParams=(θ_I:int, θ_R:float, λ:float)`）。**standard 为主线默认**（θ_I=3, θ_R=0.01, λ=1）。禁运行时反向调参 → 参数是模块常量，不从 config 覆盖（config 只选 `profile` 名）。
  | Profile | θ_I | θ_R | λ |
  |---|---:|---:|---:|
  | strict | 2 | 0.005 | 0.25 |
  | **standard** | 3 | 0.01 | 1 |
  | permissive | 4 | 0.02 | 2 |

### D5：分类点如何改、运行时入口（修审查 P1：运行时只走预计算 `PolicyTable`，不散调）
- **运行时唯一入口 = `PolicyTable.is_critical(cmd)`（O(1) 集合查找）**，**不是**三处各自散调 `classify_critical(...)`（那会绕过预计算、违反 P3）。
- `core/policy.py::classify_critical(...)` 降级为 **PolicyTable 的构表 helper**（构造时对 `command_set` 逐命令算一次，离线决定 `critical: frozenset`），**不在运行时逐帧调用**。
- **预构建一次**：
  - `Receiver.__init__` 末尾 `self.policy_table = PolicyTable.from_config(policy_source, profile, command_impact, command_set, command_risk, risk_high)`（legacy 下 PolicyTable 内部等价旧阈值，仍走同一 `is_critical` 接口，统一真相）。
  - `simulate_one_run` / `simulate_one_run_with_trace` **各自预构建一次** `policy_table = PolicyTable.from_config(config...)`（供引擎侧 `_is_two_phase_critical` 用），不每帧重建。
- 3 处分类点统一改成 `policy_table.is_critical(cmd)`：
  - `receiver.py:167` `verify_hsw_cr` 的 `is_high_risk` → `self.policy_table.is_critical(frame.command)`（经 `process()` HSW_CR 分支传入或 receiver 自持）；
  - `receiver.py:412` `process_crit_prepare` not_critical 门 → `self.policy_table.is_critical(...)`；
  - `experiment.py:104` `_is_two_phase_critical(config, command)` → 内部用预构建的 `policy_table.is_critical(command)`（签名改为接受 `policy_table`，或引擎闭包持有）。
- `Receiver.__init__`/`SimulationConfig` 加 `profile: str = "standard"`、`policy_source: str = "legacy"`、`command_impact`。受 receiver/engine 透传。
- **DRY 真相**：legacy 与 policy 两种判定都收敛到**同一个** `PolicyTable.is_critical`，3 处调用点零分支逻辑（P1）。

### D6：契约面 + `critical_command_count` 语义（修审查 P2：语义写死）
- **`SimulationSpec` 加**：`profile: Literal["strict","standard","permissive"]="standard"` + `policy_source: Literal["legacy","default_table"]="legacy"`（Web 不允许 `custom`，因无 `command_impact`；fail-fast 见 D2）。`to_config` 透传。`command_impact` 不进 Web spec（范围边界，同 Phase 4 `reboot_at_legit_index`）。
- **`critical_command_count` 语义（钉死，已拍板加）**：**= 本 run 中 sender 侧合法命令里、被 policy 判为 critical 并实际走两阶段路径的数量**。精确计在**引擎合法发送路径**（`experiment.py` 主循环 `if _is_two_phase_critical(...)` 为真处 `cost_stats.critical_command_count += 1`），**只此一处**。
  - **不**统计 attacker replay（is_attack 帧不计）；
  - **不**在 receiver `process_crit_prepare` 再计一次（避免被攻击流量污染 / 重复计数）；
  - 即「legit 两阶段命令计数」，纯 sender 视角、与攻击流量解耦——保 profile 对比指标干净。
- 六段导出面（同 Phase 3/4）：`CostStats.critical_command_count → SimulationRunResult → AggregateStats + as_dict() → Pydantic → TS/json → web static fallback`，含 `as_dict` 专测 + check-contracts 断言 + `npm run build`。

> **请确认 D1=core/policy.py、D2=H_k 向量 + 默认冻结表 + **`policy_source` 三态激活（legacy 默认）**、D3=A（θ_I 主，θ_R/ΔU 预留接口留 Phase 5）、D4=三 Profile 冻结常量（standard 默认）、D5=**运行时只走预构建 `PolicyTable.is_critical`**（classify_critical 仅构表）、D6=`SimulationSpec.profile`+`policy_source` + `critical_command_count`（engine 合法两阶段路径单点计数）。** 确认后我把「分类点改接 + 契约」Task 逐行定稿。

---

## 硬约束（贯穿，blocker 守门）

1. **(P1) 单一真相分类**：运行时 normal/critical 判定只走预构建的 `policy_table.is_critical(cmd)`，3 处调用点不得散调 `classify_critical` 或各自写阈值（DRY）。
2. **(P2) Profile 冻结**：θ_I/θ_R/λ 是模块常量，运行时不可反向调参；config 只能选 `profile` 名 + `policy_source`，不能覆盖参数值。
3. **(P3) O(1) 查表 + 预构建**：`PolicyTable` 在 `Receiver.__init__` 与两条引擎路径**各构造一次**（离线算好 `C_critical: frozenset`），运行时 `is_critical` 为集合查找；**不逐帧调用 `classify_critical`**。
4. **(P4) 向后兼容（默认 legacy）**：`policy_source="legacy"`（默认）时分类逐值等于旧 `command_risk>=risk_high`，`profile` 不生效；默认 H_k 表**不自动激活**。Phase 0–4 既有 HSW_CR 测试、baseline、Web 零改动通过。
5. **(P5) §8.6 冻结规格优先**：policy 以研究计划 §8.6 为准（`test_split_chapters_do_not_override_implementation_canonical_spec` 精神）；分章节文档不得覆盖实现规格。
6. **(P6) 不动攻击评估口径**：本 Phase 不引入 attacker `P_succ`/闭式 `R̃/ΔU` 的实现（留 Phase 5）；不改 `attack_success/legit_accepted` 归因。
7. **回归零影响**：`STABLE_MODES` 必须逐值零漂移（分类仅作用于 HSW_CR）。
> 引用 @superpowers:test-driven-development、@superpowers:verification-before-completion。

---

## 当前形态速查（细化所依据的真实代码，@ cef2222）

- `src/replay/core/receiver.py`：
  - `verify_hsw_cr`（:160-176）`is_high_risk = (command_risk or {}).get(frame.command,0.0) >= risk_high`（:167）→ 决定 nonce/challenge 路由。
  - `Receiver.__init__`（:245-259）持 `command_risk`/`risk_high`。
  - `process_crit_prepare`（:412）`if (command_risk or {}).get(frame.command,0.0) < risk_high: return not_critical`。
- `src/replay/core/experiment.py`：`_is_two_phase_critical`（:100-104）`return (command_risk or {}).get(command,0.0) >= risk_high`；两路径 `Receiver(...)` 构造透传 `command_risk`/`risk_high`（:251/642）；主循环 `_is_two_phase_critical` 路由（:383/829）。
- `src/replay/core/types.py`：`SimulationConfig.command_risk`（:180）/`risk_high=0.8`（:181）/`command_set`（:160）。**无 `profile`/`command_impact`。**
- `src/replay/core/commands.py`：`DEFAULT_COMMANDS=[FWD,BACK,LEFT,RIGHT,STOP]`。**无 H_k 影响度。**
- `src/replay/contracts/models.py`：`SimulationSpec`（:47）含 `command_risk`/`risk_high`（:86-87）+ `to_config`（:113+）。**无 `profile`。**
- 回归安全网：`tests/test_engine_baseline_regression.py`（`STABLE_MODES` + `command_risk={"UNLOCK":1.0}`，risk_high=0.8）+ `tests/fixtures/engine_baseline.json`。

---

## G5/G9 · Tasks

> 门：policy 单元 + 三 Profile + 3 分类点改接 + 向后兼容 + 契约 全绿 + `test_engine_baseline_regression`(STABLE_MODES) 逐值相等 + 全量 pytest 绿 + ruff/mypy 不退化 + check-contracts + `npm run build` 绿。

### Task G0：`core/policy.py` 影响度 + Profile + 分类纯函数（核心机制）

**Files:** Create `src/replay/core/policy.py`；Test `tests/test_policy.py`

**要点（纯函数 + 冻结数据）：**
- `Profile` = `str` Enum {STRICT="strict", STANDARD="standard", PERMISSIVE="permissive"}。
- `ProfileParams` = `@dataclass(frozen=True)`（`theta_i: int`, `theta_r: float`, `lam: float`）；`PROFILE_PARAMS: dict[Profile, ProfileParams]`（D4 表，standard=主线默认）。
- `impact_index(h_vec: tuple[int,...]) -> int`：`return max(h_vec)`（I(c)=max H_k，§5）。
- `classify_critical(cmd, *, policy_source, profile, command_impact, command_risk, risk_high) -> bool`（**构表 helper，非运行时入口**）：按 `policy_source` 三态（D2）：`legacy` → `(command_risk or {}).get(cmd,0.0) >= risk_high`；`default_table`/`custom` → `impact_index(H_k[cmd]) >= θ_I(profile)`（D3=A：θ_I 行；θ_R/ΔU 预留可选入参，缺省不激活）。`custom` 且 `command_impact is None` → raise（fail-fast）。
- `DEFAULT_COMMAND_IMPACT: dict[str, tuple[int,...]]`（主线命令 6 维冻结表，§3b）。
- `PolicyTable`（**运行时唯一入口，预计算 O(1)，P1/P3**）：`from_config(*, policy_source, profile, command_impact, command_set, command_risk, risk_high) -> PolicyTable`，构造时对 `command_set` 逐命令调 `classify_critical(...)` 算好 `critical: frozenset[str]`；`is_critical(cmd) -> bool` = 集合查找。**legacy 也走此构造**（critical 集 = 旧阈值算出的集），统一真相。

**测试要点：** θ_I 边界（I==θ_I critical、I<θ_I normal）；三 Profile 同命令不同判定（strict 升更多）；`policy_source="legacy"` 的 `PolicyTable.is_critical` 逐值等于旧 `risk>=risk_high`（P4）；`custom` 缺 `command_impact` raise；`default_table` 用 `DEFAULT_COMMAND_IMPACT`；Profile 参数冻结（standard=3/0.01/1）。
**Step 5:** 提交 `feat: add policy table (impact index, frozen profiles, source-gated classifier)`。

### Task G1：`SimulationConfig` + `Receiver` 加 `profile`/`command_impact`

**Files:** Modify `src/replay/core/types.py`（`SimulationConfig` + 可能 `SimulationRunResult` critical_command_count，见 D6）、`src/replay/core/receiver.py`（`__init__` 加 `profile`/`command_impact`）；Test `tests/test_policy_config.py`

**要点：** `SimulationConfig` 加 `policy_source: str = "legacy"`、`profile: str = "standard"`、`command_impact: dict[str, tuple[int,...]] | None = None`（带默认、向后兼容）。`Receiver.__init__` 接这三者并在末尾**预构建** `self.policy_table = PolicyTable.from_config(policy_source=..., profile=..., command_impact=..., command_set=..., command_risk=..., risk_high=...)`。默认值（legacy/standard）+ policy_table 预构建钉测试。
**Step 5:** 提交 `feat: thread policy_source/profile/command_impact and prebuild policy_table`。

### Task G2：3 处分类点改调预构建 `policy_table.is_critical`（DRY 单一真相，P1）

**Files:** Modify `src/replay/core/receiver.py`（`verify_hsw_cr` is_high_risk、`process_crit_prepare` not_critical 门 → 调 policy）、`src/replay/core/experiment.py`（`_is_two_phase_critical` → 调 policy；两路径 `Receiver(...)` 透传 `profile`/`command_impact`）；Test `tests/test_policy_routing.py`

**要点：** 3 点运行时只调**预构建** `policy_table.is_critical(cmd)`（P1/P3，不散调 `classify_critical`）：
- `receiver.py:167` `verify_hsw_cr` 的 `is_high_risk` → `receiver.policy_table.is_critical(frame.command)`（verify_hsw_cr 是模块函数：在 `process()` HSW_CR 分支算好 `is_critical` 传入，或把 `policy_table` 作参数传入）。
- `receiver.py:412` `process_crit_prepare` not_critical 门 → `self.policy_table.is_critical(frame.command)`。
- `experiment.py`：两路径开头**各预构建一次** `policy_table = PolicyTable.from_config(config...)`；`_is_two_phase_critical` 改签名为 `_is_two_phase_critical(config, command, policy_table)`（或引擎闭包持有），内部 `return config.mode is Mode.HSW_CR and policy_table.is_critical(command)`。
- **blocker 测试：**
  - `test_policy_routes_critical_by_impact`（`policy_source="default_table"`/`custom` + standard → I≥3 的命令走两阶段、I<3 走 window）。
  - `test_legacy_default_matches_old_risk_threshold`（P4：`policy_source="legacy"`（默认）→ 行为逐值等于旧 risk>=0.8；用现有 HSW_CR 集成场景对照）。
  - `test_profile_strict_upgrades_more_commands`（同命令集 strict 比 standard 更多 critical）。
**Step 5:** 提交 `feat: route HSW_CR critical classification through prebuilt policy_table`。

### Task G3：契约/指标同步（`profile` + 可选 `critical_command_count`，**D6 确认后定稿**）

**Files:** Modify `src/replay/core/cost.py`（`critical_command_count`）、`src/replay/core/experiment.py`（**单点计数**：主循环 `if _is_two_phase_critical(...)` 为真处 `cost_stats.critical_command_count += 1`，两路径各一处；run-result 填充 + `_aggregate_results` 汇总）、`src/replay/core/types.py`（`SimulationRunResult` + `AggregateStats` + `as_dict()`）、`src/replay/contracts/models.py`（`SimulationSpec.profile`+`policy_source` + `to_config`；`SimulationResultRecord.critical_command_count` + `from_aggregate`）、`src/replay/contracts/typescript.py`、`web/scripts/check-contracts.mjs`、`web/lib/static-simulator.ts`；Test `tests/test_contract_policy.py`。重生成 `contracts.ts`/`contracts.json`。

**做法：** `SimulationSpec` 加 `profile`(Literal,默认 standard)+`policy_source`(Literal legacy/default_table,默认 legacy；**Web 不收 custom**)透传到 config。`critical_command_count` 按 **D6 钉死语义单点计数**（engine 合法两阶段路径,is_attack 帧不计,receiver 侧不重复计），走 Phase 3/4 同款**六段导出面**（`CostStats→SimulationRunResult→AggregateStats→as_dict()→Pydantic→TS/json→web static fallback`，含 `as_dict` 专测 + static fallback + check-contracts 断言 + `npm run build`）。
- **计数语义测试**：`test_critical_command_count_counts_only_legit_two_phase`（legit critical 计数 == 两阶段命令数；attacker replay 不增；receiver 不重复计）。
**Step 5:** 提交 `feat: expose policy profile/source and legit critical-command count in contracts and TS`。

> **G5/G9 门（用 @superpowers:verification-before-completion 核验）：**
> - blocker 全绿：`test_policy_routes_critical_by_impact`、`test_legacy_default_matches_old_risk_threshold`、`test_profile_strict_upgrades_more_commands`、`test_critical_command_count_counts_only_legit_two_phase`
> - policy 单元（impact/profile/classify/table + policy_source 三态）+ 路由 + 契约 全绿
> - `test_engine_baseline_regression`(STABLE_MODES) 逐值相等（P7 零漂移）
> - 全量 pytest 绿 + ruff/mypy 不退化 + check-contracts + `npm run build` 双绿
> - **P6 复核**：grep 确认未引入 attacker `P_succ`/`R̃/ΔU` 实现、未改 `attack_success/legit_accepted` 归因

---

## 执行建议

- 顺序：G0（policy.py）→ G1（config/receiver 透传）→ **【确认 D1–D6】** → G2（3 点改接）→ G3（契约）。
- G0/G1 歧义低，确认前即可开工；**G2/G3 等 D1–D6（尤其 D3 三触发线范围、D6 指标）拍板后再写逐行**。
- 每个 Task 后跑 `test_engine_baseline_regression`(STABLE_MODES) 自查零漂移。
- **带入 Phase 2/3/4 教训**：(a) 单一真相分类防散落（P1/DRY）；(b) 向后兼容回退保既有测试（P4）；(c) 指标若加则六段导出面 + `as_dict` 别漏 + web static fallback（P5 教训）；(d) **不顺手碰攻击评估口径（P6）**——θ_R/ΔU 的 P_succ 驱动留 Phase 5。
- G5/G9 门绿后，另开 **Phase 5（adaptive 攻击者 + 闭式 P_succ/R̃/ΔU 双重验证）**，届时回填 θ_R/ΔU 两条触发线 + 设备 A/B/C/D（§3a）。
