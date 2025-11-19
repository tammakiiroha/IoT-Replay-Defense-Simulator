#!/usr/bin/env python3
"""
Interactive Menu System for Replay Attack Simulation
交互式菜单系统 - 无需记住命令参数
"""

import subprocess
import sys
from typing import List, Optional


def print_header():
    """显示程序标题"""
    print("\n" + "="*80)
    print("║" + " "*78 + "║")
    print("║" + "Replay Attack Simulation - Interactive Menu".center(78) + "║")
    print("║" + "リプレイ攻撃シミュレーション - 対話型メニュー".center(78) + "║")
    print("║" + "重放攻击仿真 - 交互式菜单".center(78) + "║")
    print("║" + " "*78 + "║")
    print("="*80 + "\n")


def get_choice(prompt: str, options: List[str], allow_multiple: bool = False) -> str:
    """显示选项并获取用户选择"""
    print(prompt)
    for i, option in enumerate(options, 1):
        print(f"  {i}. {option}")
    
    while True:
        if allow_multiple:
            choice = input(f"\n请选择 (输入数字，多个用空格分隔，例如: 1 2 3): ").strip()
        else:
            choice = input(f"\n请选择 (输入数字 1-{len(options)}): ").strip()
        
        try:
            if allow_multiple:
                nums = [int(x) for x in choice.split()]
                if all(1 <= n <= len(options) for n in nums):
                    return " ".join(str(n) for n in nums)
            else:
                num = int(choice)
                if 1 <= num <= len(options):
                    return str(num)
            print(f"❌ 请输入有效的数字 (1-{len(options)})")
        except ValueError:
            print("❌ 请输入数字")


def get_numeric_input(prompt: str, default: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """获取数值输入"""
    while True:
        user_input = input(f"{prompt} (默认: {default}): ").strip()
        if not user_input:
            return default
        try:
            value = float(user_input)
            if min_val <= value <= max_val:
                return value
            print(f"❌ 请输入 {min_val} 到 {max_val} 之间的数字")
        except ValueError:
            print("❌ 请输入有效的数字")


def quick_demo_menu():
    """快速演示菜单"""
    print("\n" + "="*80)
    print("🎯 快速演示场景 Quick Demo Scenarios")
    print("="*80 + "\n")
    
    scenarios = [
        ("基线对比 Baseline", "所有4种防御机制对比 (理想网络)", 
         "--modes no_def rolling window challenge --runs 100 --num-legit 20 --num-replay 100 --p-loss 0.0 --p-reorder 0.0"),
        ("丢包测试 Packet Loss", "10%丢包率下的防御效果", 
         "--modes rolling window challenge --runs 100 --num-legit 20 --num-replay 100 --p-loss 0.1 --p-reorder 0.0"),
        ("乱序测试 Reordering", "30%乱序率下的防御效果", 
         "--modes rolling window --runs 100 --num-legit 20 --num-replay 100 --p-loss 0.0 --p-reorder 0.3"),
        ("恶劣网络 Harsh Network", "丢包+乱序的极端条件", 
         "--modes window challenge --runs 100 --num-legit 20 --num-replay 100 --p-loss 0.15 --p-reorder 0.3"),
        ("选择性攻击 Selective", "针对UNLOCK命令的攻击", 
         "--modes rolling window challenge --runs 100 --num-legit 20 --num-replay 100 --target-commands UNLOCK --p-loss 0.0 --p-reorder 0.0"),
        ("快速测试 Quick Test", "30次快速运行（约30秒）", 
         "--modes window rolling --runs 30 --num-legit 10 --num-replay 50 --p-loss 0.05 --p-reorder 0.0"),
    ]
    
    for i, (name, desc, _) in enumerate(scenarios, 1):
        print(f"  {i}. {name}")
        print(f"     {desc}")
        print()
    
    print(f"  0. 返回主菜单 Back to Main Menu\n")
    
    choice = input("请选择场景 (0-6): ").strip()
    
    if choice == "0":
        return
    
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(scenarios):
            name, desc, cmd = scenarios[idx]
            print(f"\n🚀 启动场景: {name}")
            print(f"   {desc}\n")
            run_command(cmd)
        else:
            print("❌ 无效的选择")
    except ValueError:
        print("❌ 请输入数字")


def custom_experiment_menu():
    """自定义实验菜单"""
    print("\n" + "="*80)
    print("🔧 自定义实验设置 Custom Experiment Setup")
    print("="*80 + "\n")
    
    # 1. 选择防御机制
    print("【步骤 1/7】选择防御机制 Defense Mechanisms")
    print("-" * 80)
    defense_options = [
        "无防御 No Defense (基线)",
        "滚动计数器 Rolling Counter + MAC",
        "滑动窗口 Sliding Window",
        "挑战响应 Challenge-Response",
        "全部对比 All mechanisms (推荐)"
    ]
    defense_choice = get_choice("", defense_options)
    
    if defense_choice == "5":
        modes = "no_def rolling window challenge"
    else:
        mode_map = {1: "no_def", 2: "rolling", 3: "window", 4: "challenge"}
        modes = mode_map[int(defense_choice)]
    
    # 2. 运行次数
    print("\n【步骤 2/7】Monte Carlo 运行次数")
    print("-" * 80)
    runs_options = [
        "20次 - 快速测试 (约10-20秒)",
        "50次 - 标准测试 (约30-60秒) [推荐答辩]",
        "100次 - 详细测试 (约1-2分钟)",
        "200次 - 严格测试 (约2-4分钟)",
        "自定义 Custom"
    ]
    runs_choice = get_choice("", runs_options)
    runs_map = {1: 20, 2: 50, 3: 100, 4: 200}
    
    if runs_choice == "5":
        runs = int(get_numeric_input("输入运行次数", 50, 1, 1000))
    else:
        runs = runs_map[int(runs_choice)]
    
    # 3. 正规传输次数
    print("\n【步骤 3/7】正规传输次数 Legitimate Transmissions")
    print("-" * 80)
    num_legit = int(get_numeric_input("每次运行的正规传输次数", 20, 1, 100))
    
    # 4. 重放攻击次数
    print("\n【步骤 4/7】重放攻击次数 Replay Attempts")
    print("-" * 80)
    num_replay = int(get_numeric_input("每次运行的重放次数", 100, 1, 500))
    
    # 5. 丢包率
    print("\n【步骤 5/7】网络丢包率 Packet Loss Rate")
    print("-" * 80)
    print("  常用值: 0.0 (理想), 0.05 (轻微), 0.1 (中等), 0.2 (严重)")
    p_loss = get_numeric_input("丢包率 (0.0-1.0)", 0.0, 0.0, 1.0)
    
    # 6. 乱序率
    print("\n【步骤 6/7】网络乱序率 Packet Reorder Rate")
    print("-" * 80)
    print("  常用值: 0.0 (无), 0.1 (轻微), 0.3 (中等)")
    p_reorder = get_numeric_input("乱序率 (0.0-1.0)", 0.0, 0.0, 1.0)
    
    # 7. 高级选项
    print("\n【步骤 7/7】高级选项 Advanced Options")
    print("-" * 80)
    advanced_choice = get_choice("是否需要高级设置?", [
        "否，使用默认值 No (推荐)",
        "是，自定义高级参数 Yes"
    ])
    
    window_size = 5
    target_commands = ""
    
    if advanced_choice == "2":
        window_size = int(get_numeric_input("\n滑动窗口大小 Window Size", 5, 1, 20))
        
        target_choice = get_choice("\n是否指定攻击目标命令?", [
            "否 No",
            "是，指定特定命令 Yes"
        ])
        
        if target_choice == "2":
            print("\n可用命令: UNLOCK, LOCK, START, STOP, OPEN, CLOSE")
            target_cmd = input("输入目标命令 (多个用空格分隔): ").strip()
            if target_cmd:
                target_commands = f"--target-commands {target_cmd}"
    
    # 构建命令
    cmd = f"--modes {modes} --runs {runs} --num-legit {num_legit} --num-replay {num_replay} "
    cmd += f"--p-loss {p_loss} --p-reorder {p_reorder} --window-size {window_size}"
    
    if target_commands:
        cmd += f" {target_commands}"
    
    # 确认并运行
    print("\n" + "="*80)
    print("📋 实验配置总结 Experiment Summary")
    print("="*80)
    print(f"  防御机制: {modes}")
    print(f"  运行次数: {runs}")
    print(f"  正规传输: {num_legit} per run")
    print(f"  重放攻击: {num_replay} per run")
    print(f"  丢包率: {p_loss:.2%}")
    print(f"  乱序率: {p_reorder:.2%}")
    print(f"  窗口大小: {window_size}")
    if target_commands:
        print(f"  目标命令: {target_commands.split()[-1]}")
    print("="*80 + "\n")
    
    confirm = input("确认运行? (y/n): ").strip().lower()
    if confirm in ['y', 'yes', '是', '']:
        print("\n🚀 启动实验...\n")
        run_command(cmd)
    else:
        print("❌ 已取消")


def batch_experiment_menu():
    """批量实验菜单"""
    print("\n" + "="*80)
    print("📊 批量实验 Batch Experiments")
    print("="*80 + "\n")
    
    batch_types = [
        ("丢包率扫描 P-Loss Sweep", "测试不同丢包率 (0%, 5%, 10%, 15%, 20%)", "p_loss"),
        ("乱序率扫描 P-Reorder Sweep", "测试不同乱序率 (0%, 10%, 20%, 30%)", "p_reorder"),
        ("窗口大小扫描 Window Sweep", "测试不同窗口大小 (1, 3, 5, 7, 9)", "window"),
        ("运行次数扫描 Runs Sweep", "测试不同运行次数的收敛性", "runs"),
    ]
    
    for i, (name, desc, _) in enumerate(batch_types, 1):
        print(f"  {i}. {name}")
        print(f"     {desc}")
        print()
    
    print(f"  0. 返回主菜单 Back to Main Menu\n")
    
    choice = input("请选择批量实验类型 (0-4): ").strip()
    
    if choice == "0":
        return
    
    try:
        idx = int(choice) - 1
        if idx == 0:  # p_loss sweep
            print("\n🔄 运行丢包率扫描...")
            print("这将运行5个实验，预计耗时 5-10 分钟\n")
            confirm = input("确认运行? (y/n): ").strip().lower()
            if confirm in ['y', 'yes', '是', '']:
                subprocess.run(["python", "scripts/run_sweeps.py", "--sweep", "p_loss"])
        
        elif idx == 1:  # p_reorder sweep
            print("\n🔄 运行乱序率扫描...")
            print("这将运行4个实验，预计耗时 4-8 分钟\n")
            confirm = input("确认运行? (y/n): ").strip().lower()
            if confirm in ['y', 'yes', '是', '']:
                subprocess.run(["python", "scripts/run_sweeps.py", "--sweep", "p_reorder"])
        
        elif idx == 2:  # window sweep
            print("\n🔄 运行窗口大小扫描...")
            print("这将运行5个实验，预计耗时 5-10 分钟\n")
            confirm = input("确认运行? (y/n): ").strip().lower()
            if confirm in ['y', 'yes', '是', '']:
                subprocess.run(["python", "scripts/run_sweeps.py", "--sweep", "window"])
        
        elif idx == 3:  # runs sweep
            print("\n🔄 运行次数扫描...")
            for runs in [20, 50, 100, 200]:
                print(f"\n运行 {runs} 次实验...")
                run_command(f"--modes window --runs {runs} --num-legit 20 --num-replay 100")
        
        else:
            print("❌ 无效的选择")
    except ValueError:
        print("❌ 请输入数字")


def visualization_menu():
    """可视化菜单"""
    print("\n" + "="*80)
    print("📈 数据可视化 Data Visualization")
    print("="*80 + "\n")
    
    viz_options = [
        "生成所有图表 Generate All Plots",
        "只生成丢包图 P-Loss Plots",
        "只生成乱序图 P-Reorder Plots",
        "只生成窗口对比图 Window Tradeoff Plot",
        "导出表格数据 Export Tables"
    ]
    
    for i, option in enumerate(viz_options, 1):
        print(f"  {i}. {option}")
    
    print(f"\n  0. 返回主菜单 Back to Main Menu\n")
    
    choice = input("请选择 (0-5): ").strip()
    
    if choice == "0":
        return
    
    try:
        idx = int(choice)
        if idx == 1:
            print("\n📊 生成所有图表...")
            subprocess.run(["python", "scripts/plot_results.py"])
        elif idx == 2:
            print("\n📊 生成丢包相关图表...")
            subprocess.run(["python", "scripts/plot_results.py", "--only", "p_loss"])
        elif idx == 3:
            print("\n📊 生成乱序相关图表...")
            subprocess.run(["python", "scripts/plot_results.py", "--only", "p_reorder"])
        elif idx == 4:
            print("\n📊 生成窗口对比图...")
            subprocess.run(["python", "scripts/plot_results.py", "--only", "window"])
        elif idx == 5:
            print("\n📋 导出表格数据...")
            subprocess.run(["python", "scripts/export_tables.py"])
        else:
            print("❌ 无效的选择")
    except ValueError:
        print("❌ 请输入数字")


def run_command(args: str):
    """运行main.py命令"""
    cmd = f"python main.py {args}"
    print(f"命令: {cmd}\n")
    print("="*80 + "\n")
    subprocess.run(cmd, shell=True)


def main_menu():
    """主菜单"""
    while True:
        print_header()
        
        print("主菜单 Main Menu")
        print("="*80 + "\n")
        
        menu_items = [
            "🎯 快速演示 Quick Demo Scenarios",
            "🔧 自定义实验 Custom Experiment",
            "📊 批量实验 Batch Experiments",
            "📈 数据可视化 Visualization",
            "📚 查看帮助 View Help",
            "🚪 退出程序 Exit"
        ]
        
        for i, item in enumerate(menu_items, 1):
            print(f"  {i}. {item}")
        
        print("\n" + "="*80)
        
        choice = input("\n请选择 (1-6): ").strip()
        
        if choice == "1":
            quick_demo_menu()
        elif choice == "2":
            custom_experiment_menu()
        elif choice == "3":
            batch_experiment_menu()
        elif choice == "4":
            visualization_menu()
        elif choice == "5":
            print("\n" + "="*80)
            print("📚 帮助信息 Help Information")
            print("="*80)
            print("""
详细文档:
  - DEMO_GUIDE.md     : 演示指南
  - README.md         : 项目说明
  - PRESENTATION.md   : 技术演示文档

命令行使用:
  python main.py --modes window --runs 50
  python main.py --quiet --modes window --runs 200
  ./demo_quick.sh

更多信息请查看 GitHub:
  https://github.com/tammakiiroha/Replay-simulation
            """)
            input("\n按 Enter 返回主菜单...")
        elif choice == "6":
            print("\n👋 感谢使用！Goodbye!")
            print("="*80 + "\n")
            sys.exit(0)
        else:
            print("\n❌ 无效的选择，请输入 1-6")
            input("按 Enter 继续...")


if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        print("\n\n👋 程序已终止。Goodbye!")
        sys.exit(0)

