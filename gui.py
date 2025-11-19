#!/usr/bin/env python3
"""
Graphical User Interface for Replay Attack Simulation
图形界面 - 完全鼠标操作，无需输入
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import subprocess
import threading
import queue
import sys


class SimulationGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Replay Attack Simulation - 重放攻击仿真")
        self.root.geometry("1200x800")
        
        # 输出队列
        self.output_queue = queue.Queue()
        self.running = False
        
        # 创建界面
        self.create_widgets()
        
        # 定期检查输出
        self.check_output()
    
    def create_widgets(self):
        """创建所有界面元素"""
        
        # 标题
        title_frame = tk.Frame(self.root, bg="#2c3e50", height=80)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)
        
        title = tk.Label(
            title_frame,
            text="🛡️ Replay Attack Simulation Toolkit\nリプレイ攻撃シミュレーションツールキット",
            font=("Arial", 18, "bold"),
            bg="#2c3e50",
            fg="white"
        )
        title.pack(pady=15)
        
        # 主容器
        main_container = tk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 左侧：控制面板
        left_frame = tk.Frame(main_container, width=500)
        main_container.add(left_frame)
        
        # 右侧：输出窗口
        right_frame = tk.Frame(main_container)
        main_container.add(right_frame)
        
        self.create_control_panel(left_frame)
        self.create_output_panel(right_frame)
    
    def create_control_panel(self, parent):
        """创建左侧控制面板"""
        
        # 使用滚动框架
        canvas = tk.Canvas(parent)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # 快速场景按钮
        scenario_frame = tk.LabelFrame(
            scrollable_frame,
            text="🎯 快速场景 Quick Scenarios",
            font=("Arial", 12, "bold"),
            padx=10,
            pady=10
        )
        scenario_frame.pack(fill=tk.X, padx=10, pady=10)
        
        scenarios = [
            ("🎬 快速测试 (30秒)", "quick", "#27ae60"),
            ("📊 基线对比 (2分钟)", "baseline", "#3498db"),
            ("📉 丢包测试", "packet_loss", "#e67e22"),
            ("🔀 乱序测试", "reorder", "#9b59b6"),
            ("⚡ 恶劣网络", "harsh", "#e74c3c"),
            ("🎯 选择性攻击", "selective", "#16a085"),
        ]
        
        for text, scenario, color in scenarios:
            btn = tk.Button(
                scenario_frame,
                text=text,
                font=("Arial", 11),
                bg=color,
                fg="white",
                activebackground=color,
                activeforeground="white",
                cursor="hand2",
                command=lambda s=scenario: self.run_scenario(s),
                height=2,
                relief=tk.RAISED,
                bd=3
            )
            btn.pack(fill=tk.X, pady=5)
        
        # 自定义实验
        custom_frame = tk.LabelFrame(
            scrollable_frame,
            text="🔧 自定义实验 Custom Experiment",
            font=("Arial", 12, "bold"),
            padx=10,
            pady=10
        )
        custom_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # 防御机制
        tk.Label(custom_frame, text="防御机制 Defense:", font=("Arial", 10, "bold")).pack(anchor=tk.W)
        self.defense_var = tk.StringVar(value="all")
        defenses = [
            ("全部对比 All", "all"),
            ("无防御 No Defense", "no_def"),
            ("滚动计数器 Rolling", "rolling"),
            ("滑动窗口 Window", "window"),
            ("挑战响应 Challenge", "challenge")
        ]
        for text, value in defenses:
            tk.Radiobutton(
                custom_frame,
                text=text,
                variable=self.defense_var,
                value=value,
                font=("Arial", 10)
            ).pack(anchor=tk.W, padx=20)
        
        # 运行次数
        tk.Label(custom_frame, text="\n运行次数 Runs:", font=("Arial", 10, "bold")).pack(anchor=tk.W)
        self.runs_var = tk.IntVar(value=50)
        runs_frame = tk.Frame(custom_frame)
        runs_frame.pack(fill=tk.X, pady=5)
        
        tk.Scale(
            runs_frame,
            from_=10,
            to=200,
            orient=tk.HORIZONTAL,
            variable=self.runs_var,
            length=300,
            label="次数"
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        tk.Label(runs_frame, textvariable=self.runs_var, font=("Arial", 12, "bold")).pack(side=tk.LEFT, padx=10)
        
        # 丢包率
        tk.Label(custom_frame, text="\n丢包率 Packet Loss:", font=("Arial", 10, "bold")).pack(anchor=tk.W)
        self.ploss_var = tk.DoubleVar(value=0.0)
        ploss_frame = tk.Frame(custom_frame)
        ploss_frame.pack(fill=tk.X, pady=5)
        
        tk.Scale(
            ploss_frame,
            from_=0.0,
            to=0.5,
            resolution=0.01,
            orient=tk.HORIZONTAL,
            variable=self.ploss_var,
            length=300,
            label="概率"
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        tk.Label(ploss_frame, textvariable=self.ploss_var, font=("Arial", 12, "bold")).pack(side=tk.LEFT, padx=10)
        
        # 乱序率
        tk.Label(custom_frame, text="\n乱序率 Reorder Rate:", font=("Arial", 10, "bold")).pack(anchor=tk.W)
        self.preorder_var = tk.DoubleVar(value=0.0)
        preorder_frame = tk.Frame(custom_frame)
        preorder_frame.pack(fill=tk.X, pady=5)
        
        tk.Scale(
            preorder_frame,
            from_=0.0,
            to=0.5,
            resolution=0.01,
            orient=tk.HORIZONTAL,
            variable=self.preorder_var,
            length=300,
            label="概率"
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        tk.Label(preorder_frame, textvariable=self.preorder_var, font=("Arial", 12, "bold")).pack(side=tk.LEFT, padx=10)
        
        # 运行按钮
        tk.Button(
            custom_frame,
            text="▶️ 运行自定义实验 Run Custom Experiment",
            font=("Arial", 12, "bold"),
            bg="#2ecc71",
            fg="white",
            activebackground="#27ae60",
            activeforeground="white",
            cursor="hand2",
            command=self.run_custom,
            height=2,
            relief=tk.RAISED,
            bd=3
        ).pack(fill=tk.X, pady=15)
        
        # 其他功能
        other_frame = tk.LabelFrame(
            scrollable_frame,
            text="📈 其他功能 Other Functions",
            font=("Arial", 12, "bold"),
            padx=10,
            pady=10
        )
        other_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Button(
            other_frame,
            text="📊 生成图表 Generate Plots",
            font=("Arial", 11),
            bg="#3498db",
            fg="white",
            cursor="hand2",
            command=self.generate_plots,
            height=2
        ).pack(fill=tk.X, pady=5)
        
        tk.Button(
            other_frame,
            text="📋 导出表格 Export Tables",
            font=("Arial", 11),
            bg="#9b59b6",
            fg="white",
            cursor="hand2",
            command=self.export_tables,
            height=2
        ).pack(fill=tk.X, pady=5)
        
        tk.Button(
            other_frame,
            text="🗑️ 清空输出 Clear Output",
            font=("Arial", 11),
            bg="#95a5a6",
            fg="white",
            cursor="hand2",
            command=self.clear_output,
            height=2
        ).pack(fill=tk.X, pady=5)
    
    def create_output_panel(self, parent):
        """创建右侧输出面板"""
        
        output_label = tk.Label(
            parent,
            text="📟 实时输出 Live Output",
            font=("Arial", 12, "bold"),
            bg="#ecf0f1",
            fg="#2c3e50"
        )
        output_label.pack(fill=tk.X, pady=(0, 5))
        
        self.output_text = scrolledtext.ScrolledText(
            parent,
            wrap=tk.WORD,
            font=("Courier", 10),
            bg="#2c3e50",
            fg="#ecf0f1",
            insertbackground="white"
        )
        self.output_text.pack(fill=tk.BOTH, expand=True)
        
        # 状态栏
        self.status_var = tk.StringVar(value="就绪 Ready")
        status_bar = tk.Label(
            parent,
            textvariable=self.status_var,
            font=("Arial", 10),
            bg="#34495e",
            fg="white",
            anchor=tk.W,
            padx=10
        )
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)
    
    def run_scenario(self, scenario):
        """运行预设场景"""
        scenarios = {
            "quick": ("快速测试", "--modes window --runs 30 --num-legit 10 --num-replay 50 --p-loss 0.05"),
            "baseline": ("基线对比", "--modes no_def rolling window challenge --runs 100 --num-legit 20 --num-replay 100 --p-loss 0.0 --p-reorder 0.0"),
            "packet_loss": ("丢包测试", "--modes rolling window challenge --runs 100 --num-legit 20 --num-replay 100 --p-loss 0.1 --p-reorder 0.0"),
            "reorder": ("乱序测试", "--modes rolling window --runs 100 --num-legit 20 --num-replay 100 --p-loss 0.0 --p-reorder 0.3"),
            "harsh": ("恶劣网络", "--modes window challenge --runs 100 --num-legit 20 --num-replay 100 --p-loss 0.15 --p-reorder 0.3"),
            "selective": ("选择性攻击", "--modes rolling window challenge --runs 100 --num-legit 20 --num-replay 100 --target-commands UNLOCK --p-loss 0.0 --p-reorder 0.0"),
        }
        
        name, cmd = scenarios[scenario]
        self.run_command(cmd, f"场景: {name}")
    
    def run_custom(self):
        """运行自定义实验"""
        defense_map = {
            "all": "no_def rolling window challenge",
            "no_def": "no_def",
            "rolling": "rolling",
            "window": "window",
            "challenge": "challenge"
        }
        
        modes = defense_map[self.defense_var.get()]
        runs = self.runs_var.get()
        p_loss = self.ploss_var.get()
        p_reorder = self.preorder_var.get()
        
        cmd = f"--modes {modes} --runs {runs} --num-legit 20 --num-replay 100 --p-loss {p_loss} --p-reorder {p_reorder}"
        self.run_command(cmd, "自定义实验")
    
    def run_command(self, args, description):
        """在后台运行命令"""
        if self.running:
            messagebox.showwarning("警告", "已有实验正在运行！\nExperiment is already running!")
            return
        
        self.running = True
        self.status_var.set(f"运行中: {description} Running...")
        self.output_text.insert(tk.END, f"\n{'='*80}\n")
        self.output_text.insert(tk.END, f"▶️ 开始运行: {description}\n")
        self.output_text.insert(tk.END, f"{'='*80}\n\n")
        self.output_text.see(tk.END)
        
        def run_in_thread():
            try:
                # 激活虚拟环境并运行
                cmd = f"source .venv/bin/activate && python main.py {args}"
                process = subprocess.Popen(
                    cmd,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    executable='/bin/bash'
                )
                
                for line in process.stdout:
                    self.output_queue.put(line)
                
                process.wait()
                
                if process.returncode == 0:
                    self.output_queue.put("\n✅ 实验完成！Experiment completed!\n")
                else:
                    self.output_queue.put(f"\n❌ 错误: 退出码 {process.returncode}\n")
            
            except Exception as e:
                self.output_queue.put(f"\n❌ 错误: {str(e)}\n")
            
            finally:
                self.running = False
                self.status_var.set("就绪 Ready")
        
        thread = threading.Thread(target=run_in_thread, daemon=True)
        thread.start()
    
    def generate_plots(self):
        """生成图表"""
        self.status_var.set("生成图表中... Generating plots...")
        self.output_text.insert(tk.END, "\n📊 开始生成图表...\n")
        self.output_text.see(tk.END)
        
        def run():
            try:
                result = subprocess.run(
                    "source .venv/bin/activate && python scripts/plot_results.py",
                    shell=True,
                    capture_output=True,
                    text=True,
                    executable='/bin/bash'
                )
                
                self.output_queue.put(result.stdout)
                self.output_queue.put("\n✅ 图表生成完成！Plots generated!\n")
            except Exception as e:
                self.output_queue.put(f"\n❌ 错误: {str(e)}\n")
            
            self.status_var.set("就绪 Ready")
        
        threading.Thread(target=run, daemon=True).start()
    
    def export_tables(self):
        """导出表格"""
        self.status_var.set("导出表格中... Exporting tables...")
        self.output_text.insert(tk.END, "\n📋 开始导出表格...\n")
        self.output_text.see(tk.END)
        
        def run():
            try:
                result = subprocess.run(
                    "source .venv/bin/activate && python scripts/export_tables.py",
                    shell=True,
                    capture_output=True,
                    text=True,
                    executable='/bin/bash'
                )
                
                self.output_queue.put(result.stdout)
                self.output_queue.put("\n✅ 表格导出完成！Tables exported!\n")
            except Exception as e:
                self.output_queue.put(f"\n❌ 错误: {str(e)}\n")
            
            self.status_var.set("就绪 Ready")
        
        threading.Thread(target=run, daemon=True).start()
    
    def clear_output(self):
        """清空输出"""
        self.output_text.delete(1.0, tk.END)
        self.output_text.insert(tk.END, "输出已清空 Output cleared\n")
    
    def check_output(self):
        """定期检查并显示输出"""
        try:
            while True:
                line = self.output_queue.get_nowait()
                self.output_text.insert(tk.END, line)
                self.output_text.see(tk.END)
        except queue.Empty:
            pass
        
        self.root.after(100, self.check_output)


def main():
    root = tk.Tk()
    app = SimulationGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()

