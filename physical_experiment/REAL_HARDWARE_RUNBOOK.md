# 物理实验实机运行手册（给后续 AI / 工程人员）

这份文档的目标不是解释论文背景，而是让下一位 AI 或工程人员在 Ubuntu 真机上直接把 `physical_experiment` 跑起来，并且知道跑完以后怎么继续做后续试验。

如果只能看一份文档，优先看这份；如果要补背景，再看 [`README.md`](README.md)。

---

## 1. 这份手册解决什么问题

它覆盖 4 件事：

1. 在 Ubuntu 上把依赖装完整。
2. 在实机上安全地启动 HackRF TX/RX 链路。
3. 跑通当前项目定义的验证流程：`A1`、`A2`、`B`。
4. 在基线通过后，继续做可复现的后续试验。

它不解决 2 件事：

1. 不替代真实硬件环境本身；没有 2 台 HackRF 就不能完成 A2。
2. 不替代频谱合规判断；默认只建议同轴 + 衰减器的受控环境。

---

## 2. 一眼看懂的执行入口

### Canonical 入口

- 配置文件：`physical_experiment/configs/experiment_config.yaml`
- Ubuntu 引导脚本：`physical_experiment/scripts/bootstrap_ubuntu.sh`
- 环境体检：`physical_experiment/scripts/doctor.py`
- Loopback 验证：`physical_experiment/scripts/run_validation.py`
- 实机一键编排：`physical_experiment/scripts/run_hardware_validation.py`
- 全流程自动化：`physical_experiment/scripts/run_full_experiment.py`

### 结果产物默认位置

- 结果 JSON / CSV：`physical_experiment/results/`
- Flowgraph / orchestrator 日志：`physical_experiment/logs/`
- 报告：`physical_experiment/reports/`

说明：
- `run_validation.py` 会直接写 `physical_experiment/results/selftest_*.json` 或 `physical_experiment/results/validation_*.json`
- `run_hardware_validation.py` 会把 TX/RX flowgraph 日志写进 `physical_experiment/logs/`
- `run_full_experiment.py` 会额外在日志目录写 `runtime_config_*.yaml`，这是实机追溯时最重要的配置快照

---

## 3. 实机前提条件

### 操作系统

- Ubuntu 22.04 或 Ubuntu 24.04

### 必需硬件

- HackRF One 2 台
- SMA 同轴链路
- 衰减器，建议总衰减不低于 40 dB，推荐从 50 dB 起步

### 必需软件

- Python >= 3.9
- GNU Radio
- gr-osmosdr
- hackrf / hackrf-tools

### 明确的安全边界

- 不要默认空口发射
- 不要在未确认衰减器前直接把 TX 接到 RX
- `run_hardware_validation.py` 默认把 RX 安全当成硬约束；如果要跳过，必须显式传 `--i-know-what-im-doing`

---

## 4. 标准执行顺序

后续 AI 在 Ubuntu 真机上，按这个顺序执行，不要跳步。

### Step 1. 安装环境

在仓库根目录执行：

```bash
bash physical_experiment/scripts/bootstrap_ubuntu.sh
```

如果不想用引导脚本，则手动执行：

```bash
sudo apt update
sudo apt install -y \
  python3 python3-venv python3-pip \
  gnuradio gr-osmosdr \
  hackrf libhackrf-dev hackrf-tools

python3 -m venv .venv
. .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

### Step 2. 跑环境体检

```bash
.venv/bin/python physical_experiment/scripts/doctor.py --json
```

通过条件：

- OS 满足 Ubuntu 要求
- GNU Radio / gr-osmosdr 可用
- HackRF 驱动可用
- 双设备模式下能检测到 2 台 HackRF

如果需要修复提示：

```bash
.venv/bin/python physical_experiment/scripts/doctor.py --fix
```

### Step 3. 先跑 Loopback 门禁

这一轮不依赖硬件，用来确认 Python 逻辑、统计口径、结果输出都是通的。

```bash
.venv/bin/python physical_experiment/scripts/run_validation.py \
  --config physical_experiment/configs/experiment_config.yaml \
  --loopback --quick --loss-samples 0 --goal-check
```

通过条件：

- 退出码为 `0`
- 生成 `physical_experiment/results/validation_*.json`
- 结果里 `goal_validation.passed = true`

### Step 4. 列出 HackRF 并确认序列号

```bash
.venv/bin/python physical_experiment/scripts/run_hardware_validation.py \
  --config physical_experiment/configs/experiment_config.yaml \
  --list-devices
```

把识别出的两台设备分配为：

- `TX_SERIAL`
- `RX_SERIAL`

### Step 5. 跑硬件基线验证

```bash
.venv/bin/python physical_experiment/scripts/run_hardware_validation.py \
  --config physical_experiment/configs/experiment_config.yaml \
  --tx-serial <TX_SERIAL> \
  --rx-serial <RX_SERIAL> \
  --attenuation-db 50 \
  --quick
```

这条命令会自动做：

1. preflight
2. 启动 RX/TX flowgraph
3. `link-selftest`
4. validation + `goal-check`
5. 自动清理进程

通过条件：

- preflight 通过
- `link-selftest` 通过
- 主 validation 退出码为 `0`

### Step 6. 需要正式采样时，跑 loss sweep

```bash
.venv/bin/python physical_experiment/scripts/run_hardware_validation.py \
  --config physical_experiment/configs/experiment_config.yaml \
  --tx-serial <TX_SERIAL> \
  --rx-serial <RX_SERIAL> \
  --attenuation-db 50 \
  --loss-samples 0,0.1,0.2
```

这一步用于论文里的实测 vs sim 对照，不建议在基线没通过前执行。

---

## 5. 结果怎么判定

### `doctor.py`

- 退出码 `0`：环境检查通过
- 退出码 `1`：存在错误项

### `run_validation.py`

- 退出码 `0`：验证通过
- 退出码 `2`：`goal-check` 不通过
- 退出码 `1`：其他运行错误

### `run_hardware_validation.py`

- 退出码 `0`：整条硬件验证链通过
- 退出码 `2`：链路自检失败或目标门禁失败
- 退出码 `1`：preflight / flowgraph / 其他运行错误

### 实机最小验收结论

要把“当前版本已在 Ubuntu 真机上跑通”判定为成立，至少满足：

1. `doctor.py --json` 通过
2. `run_validation.py --loopback ... --goal-check` 通过
3. `run_hardware_validation.py --quick` 通过
4. `physical_experiment/results/` 下产生新的 `selftest_*.json` 和 `validation_*.json`
5. `physical_experiment/logs/` 下产生新的 `rx_flowgraph_*.log` 和 `tx_flowgraph_*.log`

---

## 6. 实机失败时先看哪里

按这个顺序排查，不要一开始就改代码。

### 1) `doctor.py` 失败

优先排查：

- `gr-osmosdr` 未安装
- `hackrf_info` 不可用
- 用户不在 `plugdev`
- 系统不是 Ubuntu

### 2) `--list-devices` 看不到 2 台 HackRF

优先排查：

- USB 连接
- 供电
- `hackrf_info`
- 是否两台设备都被系统识别

### 3) preflight 失败

常见原因：

- `--attenuation-db` 太小
- 端口 5555 / 5556 被占用
- 传入了同一台设备做 TX/RX

### 4) flowgraph 启动失败

看：

- `physical_experiment/logs/rx_flowgraph_*.log`
- `physical_experiment/logs/tx_flowgraph_*.log`

常见原因：

- GNU Radio / osmosdr 环境异常
- 设备被占用
- 设备序列号错误

### 5) `link-selftest` 失败

优先排查：

- 同轴连接方向
- 衰减过大或过小
- 频率 / 增益配置
- RX/TX 设备分配是否反了

---

## 7. AI 在实机上应该回传哪些证据

如果后续 AI 在 Ubuntu 上执行完，需要把下面这些信息整理回来，才能高效继续调试或出报告：

1. `doctor.py --json` 原始输出
2. `run_hardware_validation.py` 的完整终端输出
3. 最新的 `physical_experiment/results/selftest_*.json`
4. 最新的 `physical_experiment/results/validation_*.json`
5. 最新的 `physical_experiment/logs/rx_flowgraph_*.log`
6. 最新的 `physical_experiment/logs/tx_flowgraph_*.log`
7. 如果跑了全流程，再附上最新的 `physical_experiment/logs/runtime_config_*.yaml`

没有这些证据，就不要轻易下结论说“代码有问题”还是“硬件链路有问题”。

---

## 8. 后续试验怎么继续做

基线通过后，后续试验建议按下面 4 类推进。

### A. 衰减与增益稳健性

目标：
- 找到稳定区间，而不是只证明某一个点能跑

建议做法：

```bash
for att in 40 50 60; do
  .venv/bin/python physical_experiment/scripts/run_hardware_validation.py \
    --config physical_experiment/configs/experiment_config.yaml \
    --tx-serial <TX_SERIAL> \
    --rx-serial <RX_SERIAL> \
    --attenuation-db "$att" \
    --quick
done
```

如果某个点失败，保留日志，不要先删除失败结果。

### B. loss sweep 正式对照

目标：
- 验证实测与 sim 的一致性是否在多个 `p_loss` 采样点上成立

建议做法：

```bash
.venv/bin/python physical_experiment/scripts/run_hardware_validation.py \
  --config physical_experiment/configs/experiment_config.yaml \
  --tx-serial <TX_SERIAL> \
  --rx-serial <RX_SERIAL> \
  --attenuation-db 50 \
  --loss-samples 0,0.1,0.2
```

### C. 全流程自动化

目标：
- 生成更完整的结果、报告、图表和 runtime config 快照

建议做法：

```bash
.venv/bin/python physical_experiment/scripts/run_full_experiment.py \
  --config physical_experiment/configs/experiment_config.yaml
```

快速模式：

```bash
.venv/bin/python physical_experiment/scripts/run_full_experiment.py \
  --config physical_experiment/configs/experiment_config.yaml \
  --quick
```

### D. 第 3 章重放链路

目标：
- 做抓包、分析、重放、构造命令等独立实验

推荐顺序：

1. `capture.py`
2. `analyze_frames.py`
3. `replay.py`
4. `replay_chapter3.py`

执行前提：

- 只在授权、受控、合规的环境下做
- 默认先用 `--dry-run`

---

## 9. AI 操作规则

后续 AI 在真机上工作时，默认遵守这些规则：

1. 不要在脚本里硬编码设备序列号，优先通过 `--tx-serial` / `--rx-serial` 或配置文件传入。
2. 不要跳过 Loopback 基线，除非已有同版本的最近一次通过记录。
3. 不要省略 `--attenuation-db`。
4. 不要先改代码；先保留结果、日志、runtime config，再做判断。
5. 如果只是实机参数问题，优先改 `physical_experiment/configs/experiment_config.yaml`，不要把参数写死到脚本。
6. 如果验证失败，先判断是环境问题、硬件问题、链路问题还是代码问题，再决定是否改动仓库。

---

## 10. 最短执行清单

这是给后续 AI 的最短版本，直接照抄即可：

```bash
bash physical_experiment/scripts/bootstrap_ubuntu.sh

.venv/bin/python physical_experiment/scripts/doctor.py --json

.venv/bin/python physical_experiment/scripts/run_validation.py \
  --config physical_experiment/configs/experiment_config.yaml \
  --loopback --quick --loss-samples 0 --goal-check

.venv/bin/python physical_experiment/scripts/run_hardware_validation.py \
  --config physical_experiment/configs/experiment_config.yaml \
  --list-devices

.venv/bin/python physical_experiment/scripts/run_hardware_validation.py \
  --config physical_experiment/configs/experiment_config.yaml \
  --tx-serial <TX_SERIAL> \
  --rx-serial <RX_SERIAL> \
  --attenuation-db 50 \
  --quick
```

如果这 5 步全通过，说明当前版本已经具备在 Ubuntu 真机上完成目的实验的基础能力。
