# 演示指南 / Demo Guide

## 🎯 答辩演示效果指南

本指南专为卒業論文答辩演示设计，帮助你展示最酷炫、最专业的仿真效果。

---

## ✨ 重要更新！

**所有运行现在默认都有酷炫的视觉效果！**

- ✅ 无需 `--demo` 参数
- ✅ 自动显示进度条和统计
- ✅ 专业的ASCII标题
- ✅ 实时进度更新

如果你想要安静模式（无视觉效果），使用 `--quiet` 参数。

---

## ⚡ 快速演示（推荐用于答辩）

### 方案 A：使用自动演示脚本

```bash
./demo.sh
```

**效果：**
- ✅ 4个连续的演示场景
- ✅ 自动暂停，等待你讲解
- ✅ 每个场景都有清晰的标题
- ✅ 实时进度显示

**演示场景：**
1. 基线对比（无网络损失）
2. 网络压力测试（10%丢包）
3. 乱序测试（30%乱序率）
4. 选择性重放攻击

---

### 方案 B：单个命令演示（手动控制）

#### 演示 1：对比所有防御机制（无网络压力）

```bash
python main.py \
    --modes no_def rolling window challenge \
    --runs 100 \
    --num-legit 20 \
    --num-replay 100 \
    --p-loss 0.0 \
    --p-reorder 0.0
```

**注意：** 不再需要 `--demo` 参数，视觉效果现在是默认的！

**演示重点：**
- 展示无防御（no_def）下攻击成功率100%
- Rolling Counter 防御效果
- Sliding Window 的优势
- Challenge-Response 的完美防御

**预期结果：**
```
no_def     → 攻击成功率: ~100%
rolling    → 攻击成功率: ~0%
window     → 攻击成功率: ~0%
challenge  → 攻击成功率: 0%
```

---

#### 演示 2：网络压力测试（丢包场景）

```bash
python main.py \
    --modes rolling window challenge \
    --runs 100 \
    --num-legit 20 \
    --num-replay 100 \
    --p-loss 0.1 \
    --p-reorder 0.0
```

**演示重点：**
- 10%丢包率下，Rolling Counter 的正规接受率下降
- Sliding Window 的容错能力
- Challenge-Response 仍然完美

**预期结果：**
```
rolling    → 正规接受率: ~40% （严重下降）
window     → 正规接受率: ~95% （维持高可用）
challenge  → 正规接受率: ~90% （良好）
```

---

#### 演示 3：乱序场景测试

```bash
python main.py \
    --modes rolling window \
    --runs 100 \
    --num-legit 20 \
    --num-replay 100 \
    --p-loss 0.0 \
    --p-reorder 0.3
```

**演示重点：**
- 30%乱序率下，Rolling Counter 完全失效
- Sliding Window 专为此场景设计

**预期结果：**
```
rolling  → 正规接受率: ~20% （严重失效）
window   → 正规接受率: ~98% （完美处理乱序）
```

---

#### 演示 4：选择性重放攻击

```bash
python main.py \
    --modes rolling window challenge \
    --runs 100 \
    --num-legit 20 \
    --num-replay 100 \
    --target-commands UNLOCK \
    --p-loss 0.0 \
    --p-reorder 0.0
```

**演示重点：**
- 攻击者只针对高价值命令（如UNLOCK）
- 展示更真实的攻击场景

---

## 🎬 演示模式的特色功能

### 1. 视觉化标题横幅

```
================================================================================
║                                                                              ║
║                   REPLAY ATTACK DEFENSE SIMULATION TOOLKIT                   ║
║                            リプレイ攻撃防御シミュレーションツールキット                            ║
║                                                                              ║
================================================================================
```

### 2. 参数清晰展示

```
📋 SIMULATION PARAMETERS:
   └─ Defense Modes: window, rolling, challenge
   └─ Monte Carlo Runs: 100
   └─ Legitimate Transmissions: 20 per run
   └─ Replay Attempts: 100 per run
   └─ Packet Loss Rate: 5.00%
   └─ Packet Reorder Rate: 0.00%
   └─ Window Size: 5
   └─ Attack Mode: post
```

### 3. 初始化动画

```
🔬 INITIALIZING SIMULATION ENVIRONMENT...
   ✓ Channel model initialized
   ✓ Attacker model configured
   ✓ Cryptographic modules loaded
   ✓ Defense mechanisms ready
```

### 4. 实时进度条

```
🛡️  TESTING DEFENSE MODE: WINDOW
   Progress: [█████████████████████████░░░░░░░░░░░░░░░░░░░░░░░░░] 50/100 runs
   ├─ Legit Accept: 96.5% | Attack Success: 0.2%
```

### 5. 分阶段结果展示

```
   ✓ Mode 'window' completed:
     ├─ Legitimate Acceptance: 96.50% ± 3.21%
     └─ Attack Success Rate: 0.20% ± 0.75%
```

### 6. 最终结果表格

```
================================================================================
SIMULATION COMPLETE - FINAL RESULTS
================================================================================

Mode       Runs  Attack  p_loss  p_reorder  Window  Avg Legit  Std Legit  Avg Attack  Std Attack
---------  ----  ------  ------  ---------  ------  ---------  ---------  ----------  ----------
no_def     100   post    0.00    0.00       5        100.00%     0.00%      100.00%      0.00%
rolling    100   post    0.00    0.00       5        100.00%     0.00%        0.00%      0.00%
window     100   post    0.00    0.00       5        100.00%     0.00%        0.00%      0.00%
challenge  100   post    0.00    0.00       5        100.00%     0.00%        0.00%      0.00%
```

---

## 💡 答辩演示技巧

### 时间控制

| 演示类型 | 运行次数 | 预计耗时 | 推荐场景 |
|---------|---------|---------|---------|
| **快速演示** | 20-30次 | 10-20秒 | 快速展示概念 |
| **标准演示** | 50-100次 | 30-60秒 | 完整展示一个场景 |
| **详细演示** | 200次 | 1-2分钟 | 深入讲解统计意义 |

### 讲解要点

**在程序运行时（进度条显示）：**
1. 解释 Monte Carlo 仿真的原理
2. 说明每次运行的随机性
3. 指出实时显示的中间结果
4. 强调统计显著性（标准差）

**在结果显示时：**
1. 对比不同防御机制的效果
2. 解释为什么某些机制在特定场景下失效
3. 指出 Window 机制的优势
4. 讨论实际应用中的权衡

---

## 🎨 自定义演示

### 调整运行次数（控制时间）

```bash
# 快速演示（10秒）
python main.py --modes window --runs 20

# 标准演示（30秒）
python main.py --modes window --runs 50

# 详细演示（1分钟）
python main.py --modes window --runs 100

# 安静模式（无视觉效果）
python main.py --quiet --modes window --runs 100
```

### 调整网络参数（展示不同场景）

```bash
# 理想网络
python main.py --modes window --runs 50 --p-loss 0.0 --p-reorder 0.0

# 轻微丢包
python main.py --modes window --runs 50 --p-loss 0.05 --p-reorder 0.0

# 高丢包率
python main.py --modes window --runs 50 --p-loss 0.2 --p-reorder 0.0

# 高乱序率
python main.py --modes window --runs 50 --p-loss 0.0 --p-reorder 0.3

# 恶劣网络（同时丢包+乱序）
python main.py --modes window --runs 50 --p-loss 0.1 --p-reorder 0.2
```

---

## 📊 推荐演示流程（15分钟答辩）

### 1. 开场（2分钟）
- 运行：`./demo.sh` 的第一个场景
- 讲解：项目背景和目标

### 2. 核心演示（8分钟）
- **场景1**（3分钟）：基线对比
  - 展示无防御的脆弱性
  - 对比所有防御机制
  
- **场景2**（3分钟）：网络压力测试
  - 展示Rolling Counter的局限
  - 突出Window机制的优势
  
- **场景3**（2分钟）：乱序场景
  - 展示Window机制的核心价值

### 3. 技术深入（3分钟）
- 展示代码结构
- 解释Sliding Window的位掩码实现
- 回答评审问题

### 4. 总结（2分钟）
- 展示实验数据和图表
- 讨论实际应用价值
- 未来研究方向

---

## 🔇 安静模式（无视觉效果）

如果不需要视觉效果（例如批量实验或自动化脚本），使用 `--quiet` 参数：

```bash
python main.py \
    --quiet \
    --modes window rolling challenge \
    --runs 200 \
    --num-legit 20 \
    --num-replay 100 \
    --p-loss 0.05
```

这将只显示最终结果表格，适合：
- 批量实验
- 数据收集
- 自动化脚本
- 重定向输出到文件

---

## 🎯 常见问题

### Q1: 演示时进度条会卡住吗？
A: 不会。每10次运行更新一次，保证流畅。

### Q2: 可以跳过初始化动画吗？
A: 可以使用 `--quiet` 参数完全跳过所有视觉效果。

### Q3: 如何让演示更快？
A: 减少 `--runs` 参数，例如从100减到30。

### Q4: 能否保存演示结果？
A: 可以，添加 `--output-json results/demo.json` 参数。

### Q5: 演示时屏幕字太小怎么办？
A: 增大终端字体：`Cmd/Ctrl + +`

### Q6: 视觉效果是默认的吗？
A: **是的！** 所有运行现在默认都有视觉效果。使用 `--quiet` 可以禁用。

### Q7: `--demo` 参数还存在吗？
A: 不再需要！视觉效果现在是默认的。旧的 `--demo` 参数已被移除。

---

## 📝 演示检查清单

答辩前确认：

- [ ] 虚拟环境已激活（`source .venv/bin/activate`）
- [ ] 所有依赖已安装（`pip install -r requirements.txt`）
- [ ] `demo.sh` 有执行权限（`chmod +x demo.sh`）
- [ ] 测试运行过至少一次
- [ ] 终端字体足够大（建议16pt以上）
- [ ] 终端窗口全屏显示
- [ ] 准备好讲解内容
- [ ] 预计好每个演示的时间

---

## 🎓 Good Luck with Your Defense!

记住：演示不仅是展示代码运行，更重要的是：
1. **展示你的理解**：解释为什么这样设计
2. **展示你的能力**：如何实现核心算法
3. **展示你的思考**：讨论权衡和改进

祝你答辩成功！🎉

