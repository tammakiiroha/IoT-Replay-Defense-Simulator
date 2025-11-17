# 仿真工具详解手册

> 目标：帮助阅读者从 0 开始理解整个 replay 仿真框架，包括系统模型、文件职责、运行方式、实验设计与论文写法。可直接用于卒论附录或组会说明。

---

## 1. 为什么需要这套仿真
- **攻击背景**：攻击者可以监听遥控器发送的射频帧，录制后在任意时刻重放。
- **研究问题**：无防御和不同防御（滚动码 + MAC / 滚动码 + 窗口 / Challenge–Response）在同样攻击模型下，
  - 重放攻击成功率是多少？
  - 合法命令被执行的比例是多少？
- **仿真意义**：将真实遥控协议抽象成可配置的仿真模型，快速比较各方案的安全性与可用性，生成论文所需的表格与图形。

---

## 2. 目录结构与模块对应关系
```
Replay/
├── main.py                 # 命令行入口，跑单组或少量实验
├── scripts/
│   └── run_sweeps.py       # 自动扫描 p_loss / window 的辅助脚本
├── sim/
│   ├── attacker.py         # 攻击者模型（监听 + 重放）
│   ├── channel.py          # 简单丢包信道
│   ├── commands.py         # 默认命令集合 + trace 读取
│   ├── experiment.py       # 单轮仿真 + Monte Carlo 多轮统计
│   ├── receiver.py         # 接收端在四种模式下的验证逻辑
│   ├── security.py         # HMAC 计算与常量时间比较
│   ├── sender.py           # 发送端帧构造（counter / nonce / MAC）
│   ├── types.py            # 所有枚举、配置、结果数据类
│   └── __init__.py         # 统一导出 API
├── traces/
│   └── sample_trace.txt    # 示例命令序列，可替换为真实遥控日志
├── results/                # 已运行实验的 JSON 输出（图表数据）
└── docs/                   # 文档目录（包含本手册）
```

---

## 3. 系统模型（论文可直接引用）
1. **角色与信道**
   - 发送端（遥控器）：按指定顺序发送命令帧，可附加计数器或 nonce。
   - 接收端（玩具车）：根据防御模式验证帧并决定是否执行。
   - 攻击者：被动监听，记录合法帧，在合法阶段之后或期间重放。
   - 无线信道：对每一帧以概率 `p_loss` 丢失；攻击者监听也可配置丢包概率 `attacker_loss`。
2. **防御模式 (`Mode`)**
   - `no_def`: 永远接受；baseline。
   - `rolling`: 发送端使用单调递增计数器 + MAC；接收端验证 MAC 并要求 `ctr > last_ctr`。
   - `window`: 在 rolling 基础上允许 `last_ctr < ctr ≤ last_ctr + W`；解决丢包导致的不同步问题。
   - `challenge`: 理想的 Challenge–Response；接收端先发 nonce，只有匹配当前 nonce 的响应才被接受。
3. **攻击调度 (`AttackMode`)**
   - `post`: 合法阶段结束后集中重放 `num_replay` 次。
   - `inline`: 正常通信过程中，以概率 `p_inline` 插入最多 `burst` 个重放帧。
4. **指标**
   - 合法受理率 = `legit_accepted / legit_sent`
   - 攻击成功率 = `attack_success / attack_attempts`
   - 每个配置做 `runs` 次 Monte Carlo，输出平均值和标准差。

---

## 4. 关键代码行为分解
### 4.1 `sim/types.py`
- 把所有配置集中在 `SimulationConfig`：
  ```python
  SimulationConfig(
      mode=Mode.ROLLING_MAC,
      attack_mode=AttackMode.POST_RUN,
      num_legit=20,
      num_replay=100,
      p_loss=0.05,
      window_size=5,
      mac_length=8,
      challenge_nonce_bits=32,
      inline_attack_probability=0.3,
      inline_attack_burst=1,
      shared_key="sim_shared_key",
      rng_seed=42,
  )
  ```
- `AggregateStats` 将多轮结果转成 JSON 友好的结构，字段包括 `avg_legit_rate`, `std_legit_rate`, `avg_attack_rate`, `std_attack_rate`, `p_loss`, `window_size`, `attack_mode` 等。

### 4.2 `sim/security.py`
- `compute_mac(token, command, key, mac_length)` 使用 HMAC-SHA256，按需截断，例如只保留前 8 个 hex 字符。
- `constant_time_compare` 保证比较 MAC 时不暴露时序差异（模拟真实实现的最佳实践）。

### 4.3 `sim/sender.py`
- `Sender.next_frame(command, nonce=None)`
  - 无防御：返回 `Frame(command)`。
  - rolling/window：内部 `tx_counter += 1`，附加 counter + MAC。
  - challenge：必须传入 nonce，使用 `compute_mac(nonce, command)` 生成 MAC。

### 4.4 `sim/receiver.py`
- `verify_with_rolling_mac`：要求 `counter` 存在、MAC 正确且 `ctr > last_ctr`。
- `verify_with_window`：在 MAC 通过后，允许 `ctr` 落在 `(last_ctr, last_ctr + W]`；首次帧 (`last_ctr = -1`) 会直接接受并初始化。
- `verify_challenge_response`：
  1. 检查 `frame.nonce` 与 `state.expected_nonce` 匹配。
  2. 重新计算 `MAC(nonce, command)`。
  3. 接受后清空 nonce，防止重复使用。
- `Receiver.issue_nonce(rng, bits)`：Challenge 模式下生成随机 nonce，并要求发送端在下一帧附带。

### 4.5 `sim/attacker.py`
- `observe(frame, rng)`：攻击者是否录到这帧取决于 `record_loss`。
- `pick_frame(rng)`：随机挑选已记录帧重放，返回 `Frame` 副本，防止原始数据被破坏。

### 4.6 `sim/channel.py`
- `should_drop(p_loss, rng)`：统一控制合法帧和攻击帧的丢包，便于模拟不同信道质量。

### 4.7 `sim/experiment.py`
- `simulate_one_run(config)`：
  1. 逐条发送合法命令，记录受理情况。
  2. inline 模式：在合法帧之间插入攻击帧。
  3. post 模式：合法阶段结束后执行攻击回放。
  4. 返回 `SimulationRunResult`，包含合法/攻击计数。
- `run_many_experiments(base_config, modes, runs)`：
  1. 用 `dataclasses.replace` 克隆配置并替换 `mode`。
  2. 每轮运行 `simulate_one_run`，收集结果。
  3. 计算平均值和标准差，包装成 `AggregateStats` 列表。

### 4.8 `main.py` & `scripts/run_sweeps.py`
- `main.py`：用于单组配置，支持 `--output-json` 保存结果。
- `run_sweeps.py`：
  - `--p-loss-values` 批量扫丢包
  - `--window-values` 批量扫窗口
  - `--window-size-base` 指定 p_loss 扫描时 window 模式使用的固定窗口
  - 生成两个 JSON：`results/p_loss_sweep.json`, `results/window_sweep.json`

---

## 5. 操作指南
### 5.1 运行单组实验
```bash
python3 main.py \
  --modes no_def rolling window challenge \
  --runs 500 \
  --num-legit 20 \
  --num-replay 100 \
  --p-loss 0.0 \
  --window-size 5 \
  --attack-mode post \
  --seed 42 \
  --output-json results/ideal_p0.json
```
输出内容包含 Mode / Runs / Attack / p_loss / Window / 平均成功率 / 标准差。

### 5.2 使用真实命令 trace
```bash
python3 main.py \
  --modes rolling window \
  --runs 300 \
  --num-legit 30 \
  --num-replay 200 \
  --p-loss 0.05 \
  --window-size 5 \
  --attack-mode inline \
  --inline-attack-prob 0.4 \
  --commands-file traces/sample_trace.txt \
  --seed 99 \
  --output-json results/trace_inline.json
```
`traces/sample_trace.txt` 可替换为自己从 URH 导出的实际操作日志。

### 5.3 批量扫描
```bash
python3 scripts/run_sweeps.py \
  --runs 300 \
  --modes no_def rolling window challenge \
  --p-loss-values 0 0.01 0.05 0.1 0.2 \
  --window-values 1 3 5 7 9 \
  --window-size-base 5 \
  --attack-mode inline \
  --inline-attack-prob 0.4 \
  --inline-attack-burst 2 \
  --commands-file traces/sample_trace.txt \
  --seed 123 \
  --p-loss-output results/p_loss_sweep.json \
  --window-output results/window_sweep.json
```
- `p_loss` 扫描：window 模式使用 `W=5`
- `window` 扫描：独立输出，不影响前者
- 生成的 JSON 可直接导入 Pandas/Excel/Matplotlib 画图

---

## 6. 已生成的参考数据
- `results/ideal_p0.json`: 理想信道下四种模式的 baseline
- `results/p_loss_sweep.json`: inline 攻击 + `W=5` 的丢包扫描
- `results/window_w{W}_p05.json`: `p_loss=0.05` 时不同窗口大小对合法率/攻击率的影响
- `results/trace_inline.json`: 使用真实 trace + inline 攻击的验证数据

这些文件中都包含均值和标准差，可以直接做论文的表格或图表（示例见 README 和手册中自带的 LaTeX/Markdown 表）。

---

## 7. 论文写作建议（要点）
1. **模型描述**：引用本手册第 3 节（角色、防御、攻击、信道），说明仿真假设。
2. **实验条件**：列出 CLI 参数对应的数值，如 `num_legit=20`, `num_replay=100`, `runs=300`, `p_loss=0~0.2`, `W=5` 等。
3. **结果展示**：
   - 表格：理想信道 vs 各模式、p_loss 扫描表、窗口扫描表
   - 图形：p_loss vs Legit/Attack 曲线、Window vs Legit 折线
4. **结论与考察**：
   - 无防御始终 100% 攻击成功
   - 滚动/窗口在 p_loss 增大时合法率仍占优势，攻击率保持 ~0
   - `W=1` 虽安全但可用性差，`W=3-5` 是较好的折中
   - Challenge 模式作为上界，凸显单向滚动方案在硬件简单性上的优势
5. **实机一致性**：用真实 trace 验证仿真趋势，说明该模型不仅适用于随机序列，也适用于真实遥控操作。

---

## 8. 常见问题 FAQ
1. **为什么 inline 模式出现轻微攻击成功率？**
   - 当 `p_loss > 0` 时，合法帧可能被丢弃而老帧仍在窗口内，所以极小概率出现旧帧被当作新帧接受（尤其在窗口模式）。这是仿真刻意保留的“最坏情况”以利分析。
2. **Challenge 模式是否过于理想？**
   - 是的，它需要双向通信和额外 nonce，因此作为“安全上界”用于对比。论文中可据此讨论实现代价与安全收益。
3. **如何复现实验？**
   - 所有命令都支持 `--seed`，用相同 seed + 参数即可复现。
   - JSON 输出保留了 `p_loss`, `window_size`, `attack_mode` 等字段，便于记录和审查。
4. **如何加入更多命令或实际协议？**
   - 在 `commands.py` 中修改 `DEFAULT_COMMANDS` 或使用 `--commands-file` 输入实际抓包对应的命令表即可。

---

如需进一步定制（如加入新的攻击模式、统计其它指标、自动绘图脚本），可以在此手册基础上扩展相应模块。

---

## 9. 附录：脚本内部流程详解

### 9.1 `main.py` 的执行顺序
1. **解析命令行参数**（`parse_args`）  
   - 使用 `argparse` 定义所有 CLI 选项：`--modes`、`--runs`、`--num-legit`、`--attack-mode`、`--inline-attack-prob` 等。  
   - `--modes` 默认包含 `Mode` 枚举中所有值，若用户输入非法值会给出提示。
2. **读取命令 trace**  
   - 如果提供 `--commands-file`，调用 `load_command_sequence` 逐行读取命令（忽略空行与以 `#` 开头的注释）。  
   - 否则使用 `DEFAULT_COMMANDS` 随机抽取。
3. **构造 `SimulationConfig`**  
   - 固定字段如 `num_legit`, `num_replay`, `p_loss`, `window_size` 等直接来自 CLI。  
   - `attack_mode = AttackMode(args.attack_mode)`，`inline_attack_probability = args.inline_attack_prob` 等。  
   - `rng_seed = args.seed` 确保所有模式共享同一主随机数。
4. **Monte Carlo 核心**  
   - 调用 `run_many_experiments(base_config, modes, runs=args.runs, seed=args.seed)`：  
     ```python
     stats = run_many_experiments(base_config, modes=modes, runs=args.runs, seed=args.seed)
     ```  
   - 函数内部会对 `modes` 中每个值执行 `runs` 次 `simulate_one_run`，返回 `AggregateStats` 列表。
5. **输出**  
   - `_print_table(stats)` 按列对齐输出：Mode / Runs / Attack / p_loss / Window / Avg Legit / Std Legit / Avg Attack / Std Attack。  
   - 若指定 `--output-json`，将 `[entry.as_dict() for entry in stats]` 转成 JSON 存盘，并在终端打印保存路径。

> **总结**：`main.py` 做的就是「参数解析 → 构造配置 → 调用 `run_many_experiments` → 打印/保存结果」，逻辑清晰、便于扩展。

### 9.2 `scripts/run_sweeps.py` 的执行顺序
1. **确保可导入 `sim` 包**  
   - 脚本开头通过 `ROOT = Path(__file__).resolve().parents[1]` 获取项目根路径，并将其加入 `sys.path`，从而可以 `import sim.*`。
2. **解析 sweep 参数**  
   - `--p-loss-values` 和 `--window-values` 使用 `nargs="*"`，允许输入一系列浮点/整型。  
   - `--window-size-base` 用于 p_loss 扫描时窗口模式的固定窗口。  
   - 其它参数（`--attack-mode`, `--inline-attack-prob`, `--seed`, `--commands-file` 等）与 `main.py` 类似。
3. **准备基准配置**  
   - 与 `main.py` 类似，但将 `mode` 暂设为 `Mode.NO_DEFENSE`，后续通过 `dataclasses.replace` 替换。  
   - 包括 trace、随机种子、inline 参数等都在这里设置。
4. **执行两类扫描**  
   - `_sweep_p_loss`：对每个 `p_loss` 更新配置后调用 `run_many_experiments`，并在所得 `AggregateStats` 基础上加入 `{ "sweep_type": "p_loss", "sweep_value": value }`。  
   - `_sweep_window`：对每个 `window_size` 重复同样操作（此时 `p_loss` 固定为 `base_config` 的值，通常为 0 或用户另设）。  
   - 两个函数都返回 `List[dict]`，方便统一写入 JSON。
5. **写文件 & 打印确认**  
   - `_write_json(path, payload)` 会确保父目录存在，然后使用 `json.dumps(..., indent=2)` 写入。  
   - 程序结束时打印 `Saved p_loss sweep: ...`，方便确认路径。

> **总结**：`run_sweeps.py` 是对 `main.py` 的批处理封装。核心仍旧是 `run_many_experiments`，只是自动循环多个参数、统一写 JSON，免去手动多次输入的麻烦。

### 9.3 `simulate_one_run` 的伪代码
```text
初始化 sender / receiver / attacker
for i in range(num_legit):
    command = choose_command()
    nonce = receiver.issue_nonce(...) if mode == CHALLENGE else None
    frame = sender.next_frame(command, nonce)
    legit_sent += 1
    if 信道未丢:
        result = receiver.process(frame)
        if accepted: legit_accepted += 1
    if attack_mode == INLINE:
        attempts, success = 执行 inline 攻击
        attack_attempts += attempts
        attack_success += success
    attacker.observe(frame)  # 无论是否丢包

if attack_mode == POST:
    attempts, success = 执行 post 攻击
    attack_attempts += attempts
    attack_success += success

返回 SimulationRunResult
```

### 9.4 `run_many_experiments` 的伪代码
```text
master_rng = Random(seed)
aggregates = []
for mode in modes:
    config = replace(base_config, mode=mode)
    legit_rates = []
    attack_rates = []
    for _ in range(runs):
        child_seed = master_rng.randint(...)
        result = simulate_one_run(config, rng=Random(child_seed))
        legit_rates.append(result.legit_accept_rate)
        attack_rates.append(result.attack_success_rate)
    aggregates.append(AggregateStats(平均/标准差, p_loss, window_size, attack_mode, ...))
return aggregates
```

通过这一层包装，`main.py` 和 `run_sweeps.py` 都无需关心内部细节，只需配置参数即可得到统计结果。

---

## 10. 附录：常用参数含义速查表

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--modes` | 所有模式 | 指定要仿真的接收端防御方案：`no_def`（无防御）、`rolling`（滚动计数器 + MAC）、`window`（滚动 + 窗口）、`challenge`（挑战响应）。可一次输入多个。 |
| `--runs` | 200 / 300 | Monte Carlo 迭代次数。每组参数重复运行 `runs` 次，取平均值和标准差。 |
| `--num-legit` | 20 | 每轮实验合法发送端发送的帧数，模拟一次操作的长度。 |
| `--num-replay` | 100 | post 攻击模式下的重放尝试次数。inline 模式通常设为 0，因为攻击次数由概率控制。 |
| `--p-loss` | 0.0 | 信道丢包概率，合法帧与攻击帧都适用。`0.05` 表示 5% 的帧会在传输途中丢失。 |
| `--window-size` | 5 | `window` 模式允许的计数器窗口宽度 W，用来折中丢包容错与安全性。对其它模式无影响。 |
| `--commands-file` | 无 | 指向真实命令序列文件（每行一个命令，支持 `#` 注释）。缺省时从 `DEFAULT_COMMANDS` 随机抽取。 |
| `--mac-length` | 8 | MAC 截断长度（hex 字符数），用于模拟不同标签长度对安全性的影响。 |
| `--shared-key` | `"sim_shared_key"` | 发送端与接收端共享的密钥 K，供 HMAC 计算使用。 |
| `--attacker-loss` | 0.0 | 攻击者监听丢包概率。设为 0 代表攻击者总能录到帧，>0 则表示攻击者也可能漏收。 |
| `--attack-mode` | `post` | 攻击调度方式：`post`（合法阶段结束后集中重放）或 `inline`（合法期间插播攻击帧）。 |
| `--inline-attack-prob` | 0.3 / 0.4 | inline 模式下，在每个合法帧之后触发攻击的概率 `p_inline`。 |
| `--inline-attack-burst` | 1 / 2 | inline 模式一次最多连续插入的攻击帧数量。 |
| `--challenge-nonce-bits` | 32 | Challenge 模式生成随机 nonce 的位数。 |
| `--seed` | 无 | 全局随机种子；指定后可以完全复现实验。 |
| `--output-json` | 无 | 将本次 `AggregateStats` 保存为 JSON，方便绘图或写论文表格。 |
| `--p-loss-values`（sweep） | `[0, 0.01, 0.05, 0.1, 0.2]` | `run_sweeps.py` 用来批量扫描的丢包率列表。 |
| `--window-values`（sweep） | `[1, 3, 5, 7, 9]` | `run_sweeps.py` 用来批量扫描的窗口宽度列表。 |
| `--window-size-base`（sweep） | 5 | 在 `p_loss` 扫描中，window 模式使用的固定窗口大小，避免被 `--window-values` 覆盖。 |
| `--p-loss-output` / `--window-output` | `results/*.json` | 批量扫描的输出路径，包含每个 sweep 值与模式下的统计数据。 |

可以将此表格直接引用到论文附录或实验章节，帮助读者快速理解每个参数的含义。
