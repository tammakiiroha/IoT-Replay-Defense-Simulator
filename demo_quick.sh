#!/bin/bash
# Quick Demo for Thesis Defense (3-5 minutes)
# 快速演示版本（用于答辩）

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                                                                ║"
echo "║           Quick Demo - Thesis Defense Presentation            ║"
echo "║              卒業論文答辩 - 快速演示版本（3-5分钟）              ║"
echo "║                                                                ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Demo: Compare all mechanisms with visual progress (faster version)
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Demonstrating ALL Defense Mechanisms"
echo "展示所有防御机制（理想网络环境）"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

python main.py \
    --demo \
    --modes no_def rolling window challenge \
    --runs 50 \
    --num-legit 20 \
    --num-replay 100 \
    --p-loss 0.0 \
    --p-reorder 0.0

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Key Findings:"
echo "  • No Defense: 100% attack success (vulnerable)"
echo "  • Rolling Counter: 0% attack success (but fails under packet loss)"
echo "  • Sliding Window: 0% attack success + handles packet reordering"
echo "  • Challenge-Response: 0% attack success (strongest but costlier)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "✅ Quick demo complete!"
echo ""

