#!/usr/bin/env python3
"""
生成学术风格的系统架构图
用于论文发表
"""

import matplotlib
matplotlib.use('Agg')  # 使用非交互式后端

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
from pathlib import Path

# 设置字体（使用macOS原生日文字体）
plt.rcParams['font.family'] = ['AppleGothic', 'Hiragino Sans', 'sans-serif']
plt.rcParams['font.size'] = 10
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['pdf.fonttype'] = 42  # TrueType fonts for better compatibility

def create_box(ax, x, y, width, height, label, sublabel=None,
               facecolor='white', edgecolor='black', linewidth=1.5,
               fontsize=10, style='round'):
    """创建一个带标签的矩形框"""

    if style == 'round':
        box = FancyBboxPatch((x - width/2, y - height/2), width, height,
                             boxstyle="round,pad=0.03,rounding_size=0.05",
                             facecolor=facecolor, edgecolor=edgecolor,
                             linewidth=linewidth, zorder=2)
    else:
        box = FancyBboxPatch((x - width/2, y - height/2), width, height,
                             boxstyle="square,pad=0.02",
                             facecolor=facecolor, edgecolor=edgecolor,
                             linewidth=linewidth, zorder=2)

    ax.add_patch(box)

    if sublabel:
        ax.text(x, y + 0.08, label, ha='center', va='center',
                fontsize=fontsize, fontweight='bold', zorder=3)
        ax.text(x, y - 0.1, sublabel, ha='center', va='center',
                fontsize=fontsize-2, fontstyle='italic', color='#444444', zorder=3)
    else:
        ax.text(x, y, label, ha='center', va='center',
                fontsize=fontsize, fontweight='bold', zorder=3)

    return box

def create_arrow(ax, start, end, style='->', color='black', linewidth=1.2):
    """创建箭头"""
    ax.annotate('', xy=end, xytext=start,
                arrowprops=dict(arrowstyle=style, color=color,
                               lw=linewidth, shrinkA=2, shrinkB=2),
                zorder=1)

def create_layer_background(ax, y_center, height, label, width=4.8):
    """创建层背景"""
    rect = mpatches.Rectangle((-width/2, y_center - height/2), width, height,
                               facecolor='#f8f8f8', edgecolor='#cccccc',
                               linewidth=0.8, linestyle='--', zorder=0)
    ax.add_patch(rect)
    ax.text(-width/2 + 0.08, y_center + height/2 - 0.12, label,
            fontsize=9, fontweight='bold', color='#666666',
            va='top', ha='left', zorder=1)

def main():
    project_root = Path(__file__).resolve().parents[1]
    figures_dir = project_root / "figures"
    figures_dir.mkdir(exist_ok=True)

    # 创建图形
    fig, ax = plt.subplots(1, 1, figsize=(8, 10))
    ax.set_xlim(-3, 3)
    ax.set_ylim(-0.5, 8.5)
    ax.set_aspect('equal')
    ax.axis('off')

    # 定义位置参数
    box_width = 1.4
    box_height = 0.5
    layer_width = 5.5

    # ==================== 层背景 ====================
    # 入力層
    create_layer_background(ax, 7.5, 1.2, '入力層 (Input Layer)', layer_width)
    # シミュレーション層
    create_layer_background(ax, 5.5, 1.8, 'シミュレーション層 (Simulation Layer)', layer_width)
    # 評価層
    create_layer_background(ax, 3.2, 1.2, '評価層 (Evaluation Layer)', layer_width)
    # 出力層
    create_layer_background(ax, 1.2, 1.2, '出力層 (Output Layer)', layer_width)

    # ==================== 入力層 ====================
    create_box(ax, -1.0, 7.5, box_width, box_height,
               'コマンドシーケンス', 'traces/*.txt')
    create_box(ax, 1.0, 7.5, box_width, box_height,
               'シミュレーション設定', 'SimulationConfig')

    # ==================== シミュレーション層 ====================
    # 送信者
    create_box(ax, -1.5, 6.0, box_width*0.9, box_height,
               '送信者', 'Sender')
    # チャネル
    create_box(ax, 0, 5.5, box_width*0.9, box_height,
               'チャネル', 'Channel')
    # 受信者
    create_box(ax, 1.5, 6.0, box_width*0.9, box_height,
               '受信者', 'Receiver')
    # 攻撃者（虚线边框表示对手）
    create_box(ax, 1.5, 4.9, box_width*0.9, box_height,
               '攻撃者', 'Attacker',
               facecolor='#f0f0f0', edgecolor='black', linewidth=1.5)

    # ==================== 評価層 ====================
    create_box(ax, -0.7, 3.2, box_width, box_height,
               '統計集計', 'RunStats')
    create_box(ax, 1.0, 3.2, box_width, box_height,
               '可視化', 'Matplotlib')

    # ==================== 出力層 ====================
    create_box(ax, -0.7, 1.2, box_width, box_height,
               'JSON結果', 'results/*.json')
    create_box(ax, 1.0, 1.2, box_width, box_height,
               'PNG図表', 'figures/*.png')

    # ==================== 箭头连接 ====================
    # 入力層 -> 送信者
    create_arrow(ax, (-1.0, 7.5 - box_height/2 - 0.05), (-1.5, 6.0 + box_height/2 + 0.05))
    create_arrow(ax, (1.0, 7.5 - box_height/2 - 0.05), (-1.2, 6.0 + box_height/2 + 0.05))

    # 送信者 -> チャネル
    create_arrow(ax, (-1.5 + box_width*0.45, 6.0 - box_height/2),
                 (0 - box_width*0.4, 5.5 + box_height/2))

    # チャネル -> 受信者
    create_arrow(ax, (0 + box_width*0.4, 5.5 + box_height/2 - 0.1),
                 (1.5 - box_width*0.45, 6.0 - box_height/2 + 0.05))

    # チャネル -> 攻撃者
    create_arrow(ax, (0 + box_width*0.4, 5.5 - box_height/2 + 0.1),
                 (1.5 - box_width*0.45, 4.9 + box_height/2 - 0.05))

    # 攻撃者 -> 受信者（虚线，表示攻击路径）
    ax.annotate('', xy=(1.5, 6.0 - box_height/2 - 0.02),
                xytext=(1.5, 4.9 + box_height/2 + 0.02),
                arrowprops=dict(arrowstyle='->', color='black',
                               lw=1.2, linestyle='dashed', shrinkA=2, shrinkB=2),
                zorder=1)

    # 受信者 -> 統計集計
    create_arrow(ax, (1.5 - box_width*0.3, 6.0 - box_height/2 - 0.05),
                 (-0.7 + box_width*0.3, 3.2 + box_height/2 + 0.05))

    # 統計集計 -> 可視化
    create_arrow(ax, (-0.7 + box_width/2 + 0.05, 3.2),
                 (1.0 - box_width/2 - 0.05, 3.2))

    # 統計集計 -> JSON結果
    create_arrow(ax, (-0.7, 3.2 - box_height/2 - 0.05),
                 (-0.7, 1.2 + box_height/2 + 0.05))

    # 可視化 -> PNG図表
    create_arrow(ax, (1.0, 3.2 - box_height/2 - 0.05),
                 (1.0, 1.2 + box_height/2 + 0.05))

    # 添加图例说明虚线箭头
    ax.plot([], [], 'k--', linewidth=1.2, label='攻撃経路 (Attack Path)')
    ax.plot([], [], 'k-', linewidth=1.2, label='データフロー (Data Flow)')
    ax.legend(loc='lower right', fontsize=8, framealpha=0.9)

    # 保存为PDF（矢量图，适合论文）
    plt.tight_layout()
    plt.savefig(figures_dir / 'system_architecture.pdf',
                format='pdf', dpi=300, bbox_inches='tight', pad_inches=0.1)
    plt.savefig(figures_dir / 'system_architecture.png',
                format='png', dpi=300, bbox_inches='tight', pad_inches=0.1)

    print("✅ 图表已保存:")
    print("   - figures/system_architecture.pdf (矢量图，推荐用于论文)")
    print("   - figures/system_architecture.png (位图)")

if __name__ == '__main__':
    main()
