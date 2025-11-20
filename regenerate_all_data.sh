#!/bin/bash

# Regenerate All Experimental Data
# This script regenerates all experimental data according to EXPERIMENTAL_PARAMETERS.md

set -e  # Exit on error

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║         重新生成实验数据                                          ║"
echo "║      Regenerating Experimental Data                            ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Fixed parameters (from EXPERIMENTAL_PARAMETERS.md)
RUNS=200
SEED=42
NUM_LEGIT=20
NUM_REPLAY=100

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔧 核心参数 / Core Parameters"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  runs: $RUNS"
echo "  seed: $SEED"
echo "  num_legit: $NUM_LEGIT"
echo "  num_replay: $NUM_REPLAY"
echo ""

# Experiment 1: Packet Loss Impact
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 实验1: 丢包率影响 / Experiment 1: Packet Loss Impact"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  p_loss: 0.0 → 0.30 (步长 0.05)"
echo "  p_reorder: 0.0 (固定)"
echo "  4种防御模式"
echo ""

python3 scripts/run_sweeps.py \
  --runs $RUNS \
  --seed $SEED \
  --num-legit $NUM_LEGIT \
  --num-replay $NUM_REPLAY \
  --p-loss-values 0.0 0.05 0.10 0.15 0.20 0.25 0.30 \
  --fixed-p-reorder 0.0 \
  --p-loss-output results/p_loss_sweep.json \
  --p-reorder-output results/temp_p_reorder.json \
  --window-output results/temp_window.json

# 只保留 p_loss_sweep.json，删除临时文件
rm -f results/temp_p_reorder.json results/temp_window.json

echo "✅ 实验1完成"
echo ""

# Experiment 2: Packet Reordering Impact
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 实验2: 乱序率影响 / Experiment 2: Packet Reordering Impact"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  p_reorder: 0.0 → 0.30 (步长 0.05)"
echo "  p_loss: 0.10 (固定，单变量控制)"
echo "  4种防御模式"
echo ""

python3 scripts/run_sweeps.py \
  --runs $RUNS \
  --seed $SEED \
  --num-legit $NUM_LEGIT \
  --num-replay $NUM_REPLAY \
  --p-reorder-values 0.0 0.05 0.10 0.15 0.20 0.25 0.30 \
  --fixed-p-loss 0.10 \
  --p-loss-output results/temp_p_loss.json \
  --p-reorder-output results/p_reorder_sweep.json \
  --window-output results/temp_window.json

# 只保留 p_reorder_sweep.json，删除临时文件
rm -f results/temp_p_loss.json results/temp_window.json

echo "✅ 实验2完成"
echo ""

# Experiment 3: Window Size Tradeoff
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 实验3: 窗口大小权衡 / Experiment 3: Window Size Tradeoff"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  window_size: 1, 3, 5, 7, 9, 15, 20"
echo "  p_loss: 0.15, p_reorder: 0.15 (中等压力)"
echo "  attack_mode: inline (更严格的测试)"
echo "  只测试window模式"
echo ""

python3 scripts/run_sweeps.py \
  --runs $RUNS \
  --seed $SEED \
  --num-legit $NUM_LEGIT \
  --num-replay $NUM_REPLAY \
  --window-values 1 3 5 7 9 15 20 \
  --window-p-loss 0.15 \
  --window-p-reorder 0.15 \
  --attack-mode inline \
  --p-loss-output results/temp_p_loss.json \
  --p-reorder-output results/temp_p_reorder.json \
  --window-output results/window_sweep.json

# 只保留 window_sweep.json，删除临时文件
rm -f results/temp_p_loss.json results/temp_p_reorder.json

echo "✅ 实验3完成"
echo ""

# Generate figures
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📈 生成图表 / Generating Figures"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ -f scripts/plot_results.py ]; then
    python3 scripts/plot_results.py --formats png
    echo "✅ 图表已生成到 figures/ 目录"
else
    echo "⚠️  未找到 scripts/plot_results.py"
fi
echo ""

# Summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ 所有实验数据已重新生成"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "生成的文件:"
echo "  • results/p_loss_sweep.json (实验1: 7点 × 4模式 = 28条)"
echo "  • results/p_reorder_sweep.json (实验2: 7点 × 4模式 = 28条)"
echo "  • results/window_sweep.json (实验3: 7个窗口大小)"
echo "  • figures/*.png"
echo ""
echo "参数配置文档: EXPERIMENTAL_PARAMETERS.md"
echo ""
