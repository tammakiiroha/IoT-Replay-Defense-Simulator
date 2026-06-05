# 物理实验模块 README（Linux 实操版）

这份文档基于当前 `physical_experiment` 代码实现整理，目标是让你在 Linux 环境中把三件事完整做完：

1. 验证防御逻辑一致性（A1）
2. 验证 FSK 链路可运行（A2）
3. 做仿真对照并验收（B）

结论先说：
- 不需要先“打包”成安装包。
- 需要在 Linux 真机（Ubuntu 22.04/24.04）跑硬件链路测试，才能完成 A2 的最终验收。
- 现在它已经不是孤立子项目，而是 **Replay 本地权威运行模式** 的一部分：
  Web/API 负责入口与展示，`physical_experiment/` 负责真实链路验证与对照证据。

如果你的目标是让后续 AI 在实机上直接接手执行，优先阅读：
- [`REAL_HARDWARE_RUNBOOK.md`](REAL_HARDWARE_RUNBOOK.md)
- 这份手册比本 README 更偏向“按顺序执行、拿结果、继续做后续试验”

---

## 1. 你要达成的验收目标

### A1 防御逻辑一致性
验证 `Sender/Receiver/Attacker` 状态机与统计口径一致。

- 可在 `--loopback` 完成。
- 不覆盖物理层 FSK。

### A2 FSK 链路可运行
验证 `FrameEncoder/FrameDecoder` + GNU Radio + HackRF TX/RX 闭环可跑通。

- 必须在硬件模式完成。
- `loopback` 不能替代。

### B 仿真对照
在受控条件（如 `p_loss=0,0.1,0.2`）下比较 physical 与 sim 的 LAR/ASR 一致性。

---

## 2. 代码结构（已按文件阅读）

### 配置与总入口
- `physical_experiment/configs/experiment_config.yaml`
- `physical_experiment/scripts/run_validation.py`
- `physical_experiment/scripts/run_hardware_validation.py`
- `physical_experiment/scripts/run_full_experiment.py`

### 运行核心
- `physical_experiment/scripts/experiment_runner.py`
- `physical_experiment/flowgraphs/protocol.py`
- `physical_experiment/flowgraphs/tx_flowgraph.py`
- `physical_experiment/flowgraphs/rx_flowgraph.py`

### 环境与辅助
- `physical_experiment/scripts/doctor.py`
- `physical_experiment/scripts/calibration.py`
- `physical_experiment/analysis/compare_sim_vs_hw.py`

### 第 3 章复现实验链路
- `physical_experiment/scripts/capture.py`
- `physical_experiment/scripts/analyze_frames.py`
- `physical_experiment/scripts/replay.py`
- `physical_experiment/scripts/replay_chapter3.py`

### 其余生成器/备用流图
- `physical_experiment/flowgraphs/attacker_flowgraph.py`
- `physical_experiment/flowgraphs/grc_generator.py`
- `physical_experiment/flowgraphs/*.grc`

---

## 3. Linux 环境要求

## 操作系统
- Ubuntu 22.04 或 24.04

## 硬件
- HackRF One × 2（TX 与 RX 分离）
- SMA 同轴链路 + 衰减器（建议 40 dB 起步）

## Python
- Python >= 3.9

## 系统依赖（建议）
```bash
sudo apt update
sudo apt install -y \
  python3 python3-venv python3-pip \
  gnuradio gr-osmosdr \
  hackrf libhackrf-dev hackrf-tools
```

## Python 依赖
在项目根目录执行：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

如果你要在 Ubuntu 上直接把系统依赖和虚拟环境一次性拉起，可以执行：
```bash
bash physical_experiment/scripts/bootstrap_ubuntu.sh
```

---

## 4. 安全与合规（必须先做）

## 硬件安全
- HackRF RX 最大输入功率约为 `-5 dBm`。
- 强烈建议同轴直连 + 衰减器，先大衰减再逐步调。

## 合规
- 不要在未授权环境进行空口发射。
- 优先同轴/屏蔽环境。

---

## 5. 先做环境自检

```bash
.venv/bin/python physical_experiment/scripts/doctor.py
```

如果需要机器可读输出：
```bash
.venv/bin/python physical_experiment/scripts/doctor.py --json
```

关键检查项：
- OS 版本
- GNU Radio
- gr-osmosdr
- HackRF 驱动
- udev / plugdev
- 设备数（硬件模式需要 2 台）
- ZMQ 端口 5555/5556

---

## 6. 推荐执行顺序（你就按这个跑）

## 阶段 1：先做 A1 + B（Loopback）

### 1) 快速验收（含目标门禁）
```bash
.venv/bin/python physical_experiment/scripts/run_validation.py \
  --loopback --quick --loss-samples 0 --goal-check
```

### 2) 受控丢包采样（仿真对照）
```bash
.venv/bin/python physical_experiment/scripts/run_validation.py \
  --loopback --loss-samples 0,0.1,0.2 --goal-check
```

### 3) 突发丢包敏感性（可选）
```bash
.venv/bin/python physical_experiment/scripts/run_validation.py \
  --loopback --loss-samples 0.1 --loss-model burst
```

---

## 阶段 2：做 A2（硬件 FSK 链路）

先列设备：
```bash
.venv/bin/python physical_experiment/scripts/run_hardware_validation.py --list-devices
```

然后一键硬件编排（推荐）：
```bash
.venv/bin/python physical_experiment/scripts/run_hardware_validation.py \
  --tx-serial <TX_SERIAL> \
  --rx-serial <RX_SERIAL> \
  --attenuation-db 50 \
  --quick
```

这个命令内部会按顺序做：
1. preflight（设备/端口/安全/环境）
2. 启动 TX/RX flowgraph
3. 链路自检（A2 前置）
4. 运行 validation（默认带 `--goal-check`）
5. 自动清理进程

如需跳过链路自检（不推荐）：
```bash
.venv/bin/python physical_experiment/scripts/run_hardware_validation.py \
  --tx-serial <TX_SERIAL> --rx-serial <RX_SERIAL> \
  --attenuation-db 50 --skip-selftest
```

---

## 阶段 3：全流程自动化（可选）

```bash
.venv/bin/python physical_experiment/scripts/run_full_experiment.py
```

快速模式：
```bash
.venv/bin/python physical_experiment/scripts/run_full_experiment.py --quick
```

只看配置不执行：
```bash
.venv/bin/python physical_experiment/scripts/run_full_experiment.py --dry-run
```

---

## 7. 目标门禁与退出码（你最关心）

`run_validation.py --goal-check` 会执行门禁：
- 在 `p_loss=0` 验收点检查
- 必须包含模式：`no_def / rolling / window / challenge`
- 各模式必须通过 CI 对照条件（`lar_valid` + `asr_valid`）
- LAR/ASR 必须满足阈值
- 行为排序必须成立：`no_def ASR > defended ASR`

默认阈值：
- `LAR >= 0.90`
- `no_def ASR >= 0.70`
- `defended ASR <= 0.10`

退出码：
- `0`: 通过
- `2`: 目标门禁失败
- `1`: 其他运行错误

示例（故意制造失败，验证门禁工作）：
```bash
.venv/bin/python physical_experiment/scripts/run_validation.py \
  --loopback --quick --loss-samples 0 --goal-check --goal-lar-min 1.1
```

---

## 8. 关键脚本说明（按执行链路）

## `run_validation.py`
用途：physical vs sim 对照验证主入口。

支持：
- `--loopback`（无硬件）
- `--link-selftest`
- `--loss-samples`、`--loss-model`、`--loss-rate-mode`
- `--goal-check` 及阈值参数

核心逻辑：
1. 跑 physical（`run_physical_experiment`）
2. 跑 sim（`run_simulation`）
3. Wilson CI 对照
4. 输出汇总 + JSON
5. 可选目标门禁

---

## `experiment_runner.py`
用途：统一实验执行引擎（复用 sim 组件 + 接入硬件传输）。

关键点：
- `HardwareTransport`: ZMQ 与 flowgraph 交互
- `LoopbackTransport`: 无硬件路径
- `run_single_experiment`: 单轮合法流量 + 攻击流量
- `run_experiment_sweep`: 扫 mode/window

你需要知道的实现细节：
- 硬件轮次开始前会清空 RX 残留帧，避免跨轮污染。
- 攻击/合法计数按接收帧 `is_attack` 分类。

---

## `run_hardware_validation.py`
用途：硬件一键编排器。

关键点：
- preflight 安全检查（包含衰减评估）
- 自动启动/停止 flowgraph
- 先链路自检，再目标验收
- flowgraph 日志写入 `physical_experiment/logs/`

---

## `protocol.py`
用途：`Frame <-> RF bytes/IQ` 协议转换。

包含：
- 帧格式定义
- CRC16
- FSK 调制/解调
- ZMQ 消息封装

---

## `tx_flowgraph.py` / `rx_flowgraph.py`
用途：GNU Radio 硬件发射/接收端。

关键接口：
- TX 从 ZMQ 拉取 `complex64 IQ` 后送 HackRF sink
- RX 从 HackRF source 接收，检测帧后经 ZMQ 推回 Python

---

## `doctor.py`
用途：环境体检。

你在 Linux 上先跑它，避免无效调试。

---

## `calibration.py`
用途：测量真实链路 `p_loss` / `p_reorder` 与延迟统计。

示例：
```bash
.venv/bin/python physical_experiment/scripts/calibration.py \
  --packets 1000 --label coax_50db
```

---

## `compare_sim_vs_hw.py`
用途：把 sim/hw 结果做图和统计对照。

示例：
```bash
.venv/bin/python physical_experiment/analysis/compare_sim_vs_hw.py \
  --sim-file results/p_loss_sweep.json \
  --hw-pattern "physical_experiment/results/experiment_*.json" \
  --output-dir figures
```

---

## 9. 第3章重放复现实验（可选链路）

## 抓包
```bash
.venv/bin/python physical_experiment/scripts/capture.py \
  --duration 10 --output physical_experiment/results/capture.raw
```

## 帧分析
```bash
.venv/bin/python physical_experiment/scripts/analyze_frames.py \
  --input physical_experiment/results/capture.raw
```

## 重放（默认 dry-run）
```bash
.venv/bin/python physical_experiment/scripts/replay.py \
  --command light --repeat 3 --dry-run
```

## 真实发射（仅授权场景）
```bash
.venv/bin/python physical_experiment/scripts/replay.py \
  --command light --repeat 3 --confirm-tx
```

## 复现第3章完整流程
```bash
.venv/bin/python physical_experiment/scripts/replay_chapter3.py --full --dry-run
```

---

## 10. 常见失败与排查

## `doctor` 报 `gr-osmosdr` 未安装
```bash
sudo apt install -y gr-osmosdr
```

## 检测不到 HackRF
- 检查 USB
- `hackrf_info`
- 检查 udev / 用户组权限

## `run_hardware_validation` preflight 失败
先解决：
- 设备序列号
- 端口占用
- 衰减不足（安全风险）

## flowgraph 启动失败
查看日志目录：
- `physical_experiment/logs/`

## `goal-check` 失败（exit 2）
先看结果 JSON 里的 `goal_validation`：
- 是 `comparison_passed` 失败，还是行为阈值失败
- 是否缺失某个模式

---

## 11. 最终验收标准（建议你按此写论文/报告）

你可以把“完成”定义为以下 6 条全满足：

1. `doctor.py --json` 在 Linux 上 `passed=true`（或仅可接受 warning）
2. `run_hardware_validation.py` preflight 通过
3. 链路自检通过（A2）
4. `run_validation.py --goal-check` 返回 `0`
5. 结果 JSON 含 `goal_validation.passed=true`
6. 对照图/表生成成功（可选但推荐）

---

## 12. 一条龙命令（Linux，推荐）

```bash
# 0) 环境
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt

# 1) 自检
.venv/bin/python physical_experiment/scripts/doctor.py --json

# 2) 先跑 loopback 门禁（A1 + B）
.venv/bin/python physical_experiment/scripts/run_validation.py \
  --loopback --quick --loss-samples 0 --goal-check

# 3) 再跑硬件门禁（A2 + A1 + B）
.venv/bin/python physical_experiment/scripts/run_hardware_validation.py \
  --tx-serial <TX_SERIAL> --rx-serial <RX_SERIAL> \
  --attenuation-db 50 --quick
```

---

## 13. 备注（设计边界）

- `challenge` 模式中的 nonce 分发默认是控制面路径，不是 RF 回传链路。
- 本框架验证的是“当前实现与统计口径的可运行与一致性”，不是“全部现实无线场景最优性”。
- 受控丢包验证是模型一致性验证，不等价于真实信道建模完备性。
