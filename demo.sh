#!/bin/bash
# Replay Attack Simulation - Demo Script for Presentation
# 卒業論文答辩演示脚本

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                                                                ║"
echo "║        Replay Attack Defense Simulation Demonstration         ║"
echo "║        リプレイ攻撃防御シミュレーション - デモンストレーション    ║"
echo "║                                                                ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "This demo will showcase the replay attack simulation toolkit"
echo "demonstrating different defense mechanisms under network stress."
echo ""
read -p "Press ENTER to start the demo..." dummy

# Demo 1: Compare all defense mechanisms (baseline)
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "DEMO 1: Baseline Comparison (No Packet Loss)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
python main.py \
    --demo \
    --modes no_def rolling window challenge \
    --runs 100 \
    --num-legit 20 \
    --num-replay 100 \
    --p-loss 0.0 \
    --p-reorder 0.0

read -p "Press ENTER to continue to next demo..." dummy

# Demo 2: Impact of packet loss
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "DEMO 2: Network Stress Test (10% Packet Loss)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
python main.py \
    --demo \
    --modes rolling window challenge \
    --runs 100 \
    --num-legit 20 \
    --num-replay 100 \
    --p-loss 0.1 \
    --p-reorder 0.0

read -p "Press ENTER to continue to next demo..." dummy

# Demo 3: Impact of packet reordering
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "DEMO 3: Packet Reordering Test (30% Reorder Rate)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
python main.py \
    --demo \
    --modes rolling window challenge \
    --runs 100 \
    --num-legit 20 \
    --num-replay 100 \
    --p-loss 0.0 \
    --p-reorder 0.3

read -p "Press ENTER to continue to next demo..." dummy

# Demo 4: Selective replay attack
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "DEMO 4: Selective Replay Attack (Targeting 'UNLOCK' command)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
python main.py \
    --demo \
    --modes rolling window challenge \
    --runs 100 \
    --num-legit 20 \
    --num-replay 100 \
    --target-commands UNLOCK \
    --p-loss 0.0 \
    --p-reorder 0.0

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                                                                ║"
echo "║                    DEMONSTRATION COMPLETE                      ║"
echo "║                                                                ║"
echo "║  All defense mechanisms have been tested and compared.         ║"
echo "║  Results show the effectiveness of each approach.              ║"
echo "║                                                                ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

