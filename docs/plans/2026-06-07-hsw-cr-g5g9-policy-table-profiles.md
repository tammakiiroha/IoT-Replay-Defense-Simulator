# HSW-CR G5/G9 · 命令风险二分类 Policy Table + 三冻结 Profile — 逐行 TDD 实施计划

> **For Claude:** REQUIRED SUB-SKILL: 用 `superpowers:executing-plans` 逐任务实施本计划。
> 本文件是主计划 `docs/plans/2026-06-07-hsw-cr-full-protocol-overhaul.md` **§3b/§5（G5+G9）** 的执行细化，对照 Phase 0–4 落地后的真实主线（`origin/main` @ `cef2222`）展开。**执行前先确认下方「待拍板的关键设计决策」。**

**Goal:** 把 HSW_CR 当前「连续阈值 `command_risk.get(c) >= risk_high(0.8)`」的 normal/critical 二分类，升级为忠实实现 §3b 的 **Policy Table**：六维影响度 `I(c)=max_k H_k(c)` + 三触发线 + **strict/standard/permissive 三组冻结 Profile**，部署前离线算好、运行时 O(1) 查表。

**Architecture:** 新增 `core/policy.py`（纯函数 + 数据：`H_k` 向量 → `I(c)` → 三触发线 → 三 Profile → 预计算 `PolicyTable.is_critical(cmd)`）；`SimulationConfig`/`Receiver` 加 `profile` + 每命令 `command_impact`（H_k）；把 3 处分类点（`verify_hsw_cr` nonce 路由、`process_crit_prepare` not_critical 门、`_is_two_phase_critical`）改走 policy table；**保留 `command_risk`/`risk_high` 作向后兼容回退**（无 policy 输入时仍按旧阈值）。契约层 `SimulationSpec` 加 `profile`。

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

### D2：H_k 影响度从哪来、怎么表达？
- **推荐**：每命令一个 6 维向量 `H_k(c) ∈ {0..4}`，维度 `K={phys, property, privacy, availability, auth, recovery}`（§5）。新增 `SimulationConfig.command_impact: dict[str, tuple[int,int,int,int,int,int]] | None`。`I(c) = max(H_k(c))`。
- 默认主线命令集给一张**冻结** H_k 表（如 `UNLOCK/LOCK/PAIRING/ENABLE_POWER/FACTORY_RESET/FWD/SET_SPEED/...`），放 `policy.py` 常量 `DEFAULT_COMMAND_IMPACT`。`SET_SPEED` 的 normal/critical 争议按 §3b 就地由 H_k(phys) 决定（论文讨论项，不在代码里特判）。
- **向后兼容**：未提供 `command_impact` 时，分类回退到旧 `command_risk>=risk_high`（保 Phase 0–4 既有 HSW_CR 测试不破）。

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

### D5：分类点如何改、怎么保向后兼容？
- **推荐**：新增 `core/policy.py::classify_critical(cmd, *, profile, command_impact, command_risk, risk_high) -> bool`（单一真相分类函数）：
  - 若 `command_impact` 提供 → `I(c)=max(H_k); return I(c) >= θ_I(profile)`（+ D3=A 时叠加可选 risk_sw/delta_u 行）。
  - 否则 → 回退 `command_risk.get(c,0) >= risk_high`（旧行为）。
- 3 处调用点统一改调 `classify_critical(...)`：
  - `receiver.py:167` `verify_hsw_cr` 的 `is_high_risk`；
  - `receiver.py:412` `process_crit_prepare` 的 not_critical 门；
  - `experiment.py:104` `_is_two_phase_critical`。
- `Receiver.__init__`/`SimulationConfig` 加 `profile: str = "standard"`、`command_impact`。受 receiver/engine 透传。

### D6：契约面到哪？
- **推荐**：`SimulationSpec` 加 `profile: Literal["strict","standard","permissive"]="standard"`（+ to-config 透传）。**可选**：`SimulationResultRecord` 加观测计数 `critical_command_count`（本 run 被分类为 critical 的命令数，中性观测，便于 profile 对比）。`command_impact` 较重，**先不进 Web spec**（同 Phase 4 `reboot_at_legit_index` 的范围边界——留 UI/API phase）。**请确认是否本 Phase 就加 `critical_command_count` 指标**（推荐加，六段导出面一次写全）。

> **请确认 D1=core/policy.py、D2=H_k 向量 + 默认冻结表 + 向后兼容回退、D3=A（θ_I 主，θ_R/ΔU 预留接口留 Phase 5）、D4=三 Profile 冻结常量（standard 默认）、D5=单一 classify_critical + 3 点改调 + profile 透传、D6=SimulationSpec.profile（+ 可选 critical_command_count）。** 确认后我把「分类点改接 + 契约」Task 逐行定稿。

---

## 硬约束（贯穿，blocker 守门）

1. **(P1) 单一真相分类**：normal/critical 判定只走 `policy.classify_critical`，3 处调用点不得各自写阈值逻辑（DRY）。
2. **(P2) Profile 冻结**：θ_I/θ_R/λ 是模块常量，运行时不可反向调参；config 只能选 profile 名，不能覆盖参数值。
3. **(P3) O(1) 查表**：`PolicyTable` 部署前（构造时）离线算好 `C_critical` 集，运行时 `is_critical` 为集合查找。
4. **(P4) 向后兼容**：未提供 `command_impact` 时，HSW_CR 分类逐值等于旧 `risk>=risk_high`（Phase 0–4 既有 HSW_CR 测试零改动通过）。
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
- `classify_critical(cmd, *, profile, command_impact, command_risk, risk_high) -> bool`：
  - `command_impact` 含 `cmd` → `impact_index(...) >= PROFILE_PARAMS[profile].theta_i`（D3=A：θ_I 行；θ_R/ΔU 预留可选入参，缺省不激活）。
  - 否则回退 `(command_risk or {}).get(cmd,0.0) >= risk_high`（P4）。
- `DEFAULT_COMMAND_IMPACT: dict[str, tuple[int,...]]`（主线命令 6 维冻结表，§3b）。
- `PolicyTable`（预计算 O(1)，P3）：`from_config(profile, command_impact, command_set) -> PolicyTable`，构造时算好 `critical: frozenset[str]`；`is_critical(cmd) -> bool` = 集合查找。

**测试要点：** θ_I 边界（I==θ_I critical、I<θ_I normal）；三 Profile 同命令不同判定（strict 升更多）；向后兼容回退逐值等于旧阈值；`PolicyTable.is_critical` 与 `classify_critical` 一致；Profile 参数冻结（standard=3/0.01/1）。
**Step 5:** 提交 `feat: add policy table (impact index, frozen profiles, critical classifier)`。

### Task G1：`SimulationConfig` + `Receiver` 加 `profile`/`command_impact`

**Files:** Modify `src/replay/core/types.py`（`SimulationConfig` + 可能 `SimulationRunResult` critical_command_count，见 D6）、`src/replay/core/receiver.py`（`__init__` 加 `profile`/`command_impact`）；Test `tests/test_policy_config.py`

**要点：** `SimulationConfig` 加 `profile: str = "standard"`、`command_impact: dict[str, tuple[int,...]] | None = None`（带默认、向后兼容）。`Receiver.__init__` 接 `profile="standard"`/`command_impact=None` 存属性。默认值钉测试。
**Step 5:** 提交 `feat: thread profile/command_impact through config and receiver`。

### Task G2：3 处分类点改接 `classify_critical`（DRY 单一真相，P1）

**Files:** Modify `src/replay/core/receiver.py`（`verify_hsw_cr` is_high_risk、`process_crit_prepare` not_critical 门 → 调 policy）、`src/replay/core/experiment.py`（`_is_two_phase_critical` → 调 policy；两路径 `Receiver(...)` 透传 `profile`/`command_impact`）；Test `tests/test_policy_routing.py`

**要点：** 3 点统一 `from .policy import classify_critical`，参数从 receiver/config 取（`profile`/`command_impact`/`command_risk`/`risk_high`）。**verify_hsw_cr 是模块函数**，需把 `profile`/`command_impact` 经 `process()` 透传（或在 `process()` HSW_CR 分支算好 is_critical 传入）。
- **blocker 测试：**
  - `test_policy_routes_critical_by_impact`（提供 command_impact + standard → I≥3 的命令走两阶段、I<3 走 window）。
  - `test_backward_compat_without_impact_matches_risk_threshold`（P4：无 command_impact → 行为逐值等于旧 risk>=0.8；用现有 HSW_CR 集成场景对照）。
  - `test_profile_strict_upgrades_more_commands`（同命令集 strict 比 standard 更多 critical）。
**Step 5:** 提交 `feat: route HSW_CR critical classification through policy table`。

### Task G3：契约/指标同步（`profile` + 可选 `critical_command_count`，**D6 确认后定稿**）

**Files:** Modify `src/replay/contracts/models.py`（`SimulationSpec.profile` + `to_config`；若 D6 选加计数：`SimulationResultRecord.critical_command_count` + `from_aggregate`）、`src/replay/contracts/typescript.py`、`web/scripts/check-contracts.mjs`、`web/lib/static-simulator.ts`（若加计数）、（若加计数）`src/replay/core/types.py` `AggregateStats`+`as_dict()` + `experiment.py` 填充/汇总；Test `tests/test_contract_policy.py`。重生成 `contracts.ts`/`contracts.json`。

**做法：** `SimulationSpec` 加 `profile`（Literal，默认 standard）透传到 `SimulationConfig.profile`。若 D6 加 `critical_command_count`，走 Phase 3/4 同款**六段导出面**（含 `as_dict` 专测 + static fallback + check-contracts 断言 + `npm run build`）。
**Step 5:** 提交 `feat: expose policy profile (and critical-command count) in contracts and TS`。

> **G5/G9 门（用 @superpowers:verification-before-completion 核验）：**
> - blocker 全绿：`test_policy_routes_critical_by_impact`、`test_backward_compat_without_impact_matches_risk_threshold`、`test_profile_strict_upgrades_more_commands`
> - policy 单元（impact/profile/classify/table）+ 路由 + 契约 全绿
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
