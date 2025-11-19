#!/usr/bin/env python3
"""
Graphical User Interface for Replay Attack Simulation
图形界面 - 美化版 (Modern UI)
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import subprocess
import threading
import queue
import sys
import platform

# --- 颜色配置 ---
COLORS = {
    "bg_dark": "#2c3e50",       # 深色背景（侧边栏）
    "bg_light": "#ecf0f1",      # 浅色背景（内容区）
    "accent": "#3498db",        # 强调色（蓝色）
    "accent_hover": "#2980b9",  # 强调色悬停
    "success": "#2ecc71",       # 成功色（绿色）
    "success_hover": "#27ae60", # 成功色悬停
    "warning": "#e67e22",       # 警告色（橙色）
    "danger": "#e74c3c",        # 危险色（红色）
    "text_light": "#ffffff",    # 浅色文本
    "text_dark": "#2c3e50",     # 深色文本
    "card_bg": "#ffffff",       # 卡片背景
    "border": "#bdc3c7"         # 边框颜色
}

# --- 字体配置 ---
if platform.system() == "Darwin":  # macOS
    FONTS = {
        "h1": ("Helvetica Neue", 24, "bold"),
        "h2": ("Helvetica Neue", 16, "bold"),
        "h3": ("Helvetica Neue", 14, "bold"),
        "body": ("Helvetica Neue", 13),
        "mono": ("Menlo", 12),
        "icon": ("Apple Color Emoji", 16)
    }
else:  # Windows/Linux
    FONTS = {
        "h1": ("Segoe UI", 20, "bold"),
        "h2": ("Segoe UI", 14, "bold"),
        "h3": ("Segoe UI", 12, "bold"),
        "body": ("Segoe UI", 11),
        "mono": ("Consolas", 10),
        "icon": ("Segoe UI Emoji", 14)
    }

class ModernButton(tk.Frame):
    """自定义现代风格按钮"""
    def __init__(self, parent, text, command, color=COLORS["accent"], hover_color=COLORS["accent_hover"], icon="", **kwargs):
        super().__init__(parent, bg=color, cursor="hand2", **kwargs)
        self.command = command
        self.color = color
        self.hover_color = hover_color
        
        # 布局容器
        self.pack_propagate(False)
        
        # 内容标签（图标+文字） - 移除Emoji图标支持，直接用文字
        self.label = tk.Label(
            self, 
            text=text, 
            bg=color, 
            fg="white", 
            font=FONTS["h3"],
            cursor="hand2"
        )
        self.label.place(relx=0.5, rely=0.5, anchor="center")
        
        # 绑定事件
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)
        self.bind("<Button-1>", self.on_click)
        self.label.bind("<Enter>", self.on_enter)
        self.label.bind("<Leave>", self.on_leave)
        self.label.bind("<Button-1>", self.on_click)

    def on_enter(self, event):
        self.configure(bg=self.hover_color)
        self.label.configure(bg=self.hover_color)

    def on_leave(self, event):
        self.configure(bg=self.color)
        self.label.configure(bg=self.color)

    def on_click(self, event):
        if self.command:
            self.command()

class CardFrame(tk.Frame):
    """卡片样式容器"""
    def __init__(self, parent, title, icon="", **kwargs):
        super().__init__(parent, bg=COLORS["card_bg"], padx=15, pady=15, **kwargs)
        
        # 标题栏
        header = tk.Frame(self, bg=COLORS["card_bg"])
        header.pack(fill=tk.X, pady=(0, 10))
        
        if icon:
            tk.Label(header, text=icon, font=FONTS["icon"], bg=COLORS["card_bg"]).pack(side=tk.LEFT, padx=(0, 10))
            
        tk.Label(
            header, 
            text=title, 
            font=FONTS["h2"], 
            fg=COLORS["text_dark"], 
            bg=COLORS["card_bg"]
        ).pack(side=tk.LEFT)
        
        # 分割线
        ttk.Separator(self, orient="horizontal").pack(fill=tk.X, pady=(0, 15))

class SimulationGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Replay Attack Simulation Toolkit")
        self.root.geometry("1280x850")
        self.root.configure(bg=COLORS["bg_light"])
        
        # 设置样式
        self.setup_style()
        
        # 输出队列
        self.output_queue = queue.Queue()
        self.running = False
        
        # 创建界面
        self.create_widgets()
        
        # 定期检查输出
        self.check_output()
    
    def setup_style(self):
        """配置ttk样式"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # 配置通用背景
        style.configure(".", background=COLORS["bg_light"])
        
        # 配置滚动条
        style.configure("Vertical.TScrollbar", 
                       gripcount=0,
                       background=COLORS["bg_dark"], 
                       darkcolor=COLORS["bg_dark"], 
                       lightcolor=COLORS["bg_dark"],
                       troughcolor=COLORS["bg_light"], 
                       bordercolor=COLORS["bg_light"], 
                       arrowcolor="white")
                       
        # 配置单选按钮
        style.configure("TRadiobutton", 
                       background=COLORS["card_bg"], 
                       font=FONTS["body"],
                       foreground=COLORS["text_dark"])
                       
        # 配置水平分割线
        style.configure("TSeparator", background=COLORS["border"])

    def create_widgets(self):
        """创建主界面结构"""
        
        # === 侧边栏 (Sidebar) ===
        sidebar = tk.Frame(self.root, bg=COLORS["bg_dark"], width=280)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)
        
        # Logo区
        logo_frame = tk.Frame(sidebar, bg=COLORS["bg_dark"], height=100)
        logo_frame.pack(fill=tk.X, pady=20)
        tk.Label(logo_frame, text="[ Replay ]", font=("Arial", 24, "bold"), bg=COLORS["bg_dark"], fg="white").pack()
        tk.Label(logo_frame, text="Simulation Toolkit", font=("Arial", 12), bg=COLORS["bg_dark"], fg="white").pack(pady=5)
        tk.Label(logo_frame, text="v1.0", font=("Arial", 10), bg=COLORS["bg_dark"], fg="#95a5a6").pack()

        # 侧边栏菜单
        self.create_sidebar_menu(sidebar)
        
        # === 主内容区 (Main Content) ===
        main_area = tk.Frame(self.root, bg=COLORS["bg_light"])
        main_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 标题栏
        header_frame = tk.Frame(main_area, bg=COLORS["bg_light"], height=50)
        header_frame.pack(fill=tk.X, pady=(0, 20))
        tk.Label(
            header_frame, 
            text="Dashboard / 控制面板", 
            font=FONTS["h1"], 
            bg=COLORS["bg_light"], 
            fg=COLORS["text_dark"]
        ).pack(side=tk.LEFT)
        
        # 内容网格
        content_grid = tk.Frame(main_area, bg=COLORS["bg_light"])
        content_grid.pack(fill=tk.BOTH, expand=True)
        
        # 左列：配置
        left_col = tk.Frame(content_grid, bg=COLORS["bg_light"])
        left_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        # 右列：输出
        right_col = tk.Frame(content_grid, bg=COLORS["bg_light"])
        right_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0))
        
        self.create_config_panel(left_col)
        self.create_output_panel(right_col)

    def create_sidebar_menu(self, parent):
        """侧边栏快捷菜单"""
        
        menu_items = [
            ("Quick Test", "30s run", "quick", COLORS["success"]),
            ("Baseline", "Compare all modes", "baseline", COLORS["accent"]),
            ("Packet Loss", "10% loss test", "packet_loss", COLORS["warning"]),
            ("Reordering", "30% reorder test", "reorder", "#9b59b6"),
            ("Harsh Network", "Loss + Reorder", "harsh", COLORS["danger"]),
        ]
        
        tk.Label(parent, text="SCENARIOS", font=("Arial", 10, "bold"), bg=COLORS["bg_dark"], fg="#7f8c8d", anchor="w").pack(fill=tk.X, padx=20, pady=(30, 10))
        
        for title, sub, cmd, color in menu_items:
            btn_frame = tk.Frame(parent, bg=COLORS["bg_dark"], cursor="hand2")
            btn_frame.pack(fill=tk.X, padx=10, pady=2)
            
            # 左侧色条
            tk.Frame(btn_frame, bg=color, width=4).pack(side=tk.LEFT, fill=tk.Y)
            
            # 文字容器
            text_frame = tk.Frame(btn_frame, bg=COLORS["bg_dark"], padx=10, pady=8)
            text_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            
            tk.Label(text_frame, text=title, font=FONTS["h3"], bg=COLORS["bg_dark"], fg="white", anchor="w").pack(fill=tk.X)
            tk.Label(text_frame, text=sub, font=("Arial", 10), bg=COLORS["bg_dark"], fg="#95a5a6", anchor="w").pack(fill=tk.X)
            
            # 绑定点击事件
            for w in [btn_frame, text_frame] + text_frame.winfo_children():
                w.bind("<Button-1>", lambda e, s=cmd: self.run_scenario(s))
                w.bind("<Enter>", lambda e, f=btn_frame: f.configure(bg="#34495e"))
                w.bind("<Leave>", lambda e, f=btn_frame: f.configure(bg=COLORS["bg_dark"]))

        # 底部按钮
        bottom_frame = tk.Frame(parent, bg=COLORS["bg_dark"], pady=20)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        ModernButton(
            bottom_frame, 
            text="Generate Plots", 
            command=self.generate_plots,
            color="#34495e",
            hover_color="#2c3e50",
            icon="📈",
            height=40
        ).pack(fill=tk.X, padx=20, pady=5)
        
        ModernButton(
            bottom_frame, 
            text="Export Tables", 
            command=self.export_tables,
            color="#34495e",
            hover_color="#2c3e50",
            icon="📋",
            height=40
        ).pack(fill=tk.X, padx=20, pady=5)

    def create_config_panel(self, parent):
        """自定义实验配置面板"""
        card = CardFrame(parent, "Custom Experiment", "")
        card.pack(fill=tk.BOTH, expand=True)
        
        # 1. 防御机制
        tk.Label(card, text="Defense Mechanisms", font=FONTS["h3"], bg=COLORS["card_bg"]).pack(anchor="w", pady=(0, 10))
        
        self.defense_var = tk.StringVar(value="all")
        defense_frame = tk.Frame(card, bg=COLORS["card_bg"])
        defense_frame.pack(fill=tk.X, pady=(0, 20))
        
        defenses = [
            ("All / 全部对比", "all"),
            ("No Def / 无防御", "no_def"),
            ("Rolling / 滚动计数", "rolling"),
            ("Window / 滑动窗口", "window"),
            ("Challenge / 挑战响应", "challenge")
        ]
        
        for text, val in defenses:
            ttk.Radiobutton(defense_frame, text=text, variable=self.defense_var, value=val).pack(anchor="w", pady=2)

        # 2. 运行参数
        params_frame = tk.Frame(card, bg=COLORS["card_bg"])
        params_frame.pack(fill=tk.X)
        
        # 运行次数
        self.create_slider(params_frame, "Runs / 运行次数", self.runs_var_init(50), 10, 200, 10)
        # 丢包率
        self.create_slider(params_frame, "Packet Loss / 丢包率", self.ploss_var_init(0.0), 0.0, 0.5, 0.01, True)
        # 乱序率
        self.create_slider(params_frame, "Reorder Rate / 乱序率", self.preorder_var_init(0.0), 0.0, 0.5, 0.01, True)

        # 3. 运行按钮
        tk.Frame(card, bg=COLORS["card_bg"], height=20).pack() # Spacer
        ModernButton(
            card, 
            text="START SIMULATION / 开始仿真", 
            command=self.run_custom,
            color=COLORS["success"],
            hover_color=COLORS["success_hover"],
            icon="▶️",
            height=50
        ).pack(fill=tk.X, pady=10)

    def create_slider(self, parent, title, variable, min_val, max_val, res, is_float=False):
        """创建美化的滑动条"""
        frame = tk.Frame(parent, bg=COLORS["card_bg"], pady=10)
        frame.pack(fill=tk.X)
        
        header = tk.Frame(frame, bg=COLORS["card_bg"])
        header.pack(fill=tk.X, pady=(0, 5))
        
        tk.Label(header, text=title, font=FONTS["body"], bg=COLORS["card_bg"], fg="#7f8c8d").pack(side=tk.LEFT)
        
        value_label = tk.Label(header, font=FONTS["h3"], bg=COLORS["card_bg"], fg=COLORS["accent"])
        value_label.pack(side=tk.RIGHT)
        
        def update_label(*args):
            val = variable.get()
            if is_float:
                value_label.config(text=f"{val:.2f}")
            else:
                value_label.config(text=f"{int(val)}")
        
        variable.trace_add("write", update_label)
        update_label() # init
        
        scale = ttk.Scale(frame, from_=min_val, to=max_val, variable=variable, orient="horizontal")
        scale.pack(fill=tk.X)

    def runs_var_init(self, val):
        self.runs_var = tk.IntVar(value=val)
        return self.runs_var
        
    def ploss_var_init(self, val):
        self.ploss_var = tk.DoubleVar(value=val)
        return self.ploss_var
        
    def preorder_var_init(self, val):
        self.preorder_var = tk.DoubleVar(value=val)
        return self.preorder_var

    def create_output_panel(self, parent):
        """右侧输出面板"""
        card = CardFrame(parent, "Live Output", "")
        card.pack(fill=tk.BOTH, expand=True)
        
        # 文本框容器（带边框）
        text_container = tk.Frame(card, bg="#2c3e50", bd=1, relief="flat")
        text_container.pack(fill=tk.BOTH, expand=True)
        
        self.output_text = scrolledtext.ScrolledText(
            text_container,
            wrap=tk.WORD,
            font=FONTS["mono"],
            bg="#2c3e50",
            fg="#ecf0f1",
            insertbackground="white",
            padx=10,
            pady=10,
            borderwidth=0,
            highlightthickness=0
        )
        self.output_text.pack(fill=tk.BOTH, expand=True)
        
        # 底部工具栏
        toolbar = tk.Frame(card, bg=COLORS["card_bg"], height=40, pady=10)
        toolbar.pack(fill=tk.X)
        
        # 状态指示
        self.status_label = tk.Label(toolbar, text="● Ready", font=FONTS["body"], fg=COLORS["success"], bg=COLORS["card_bg"])
        self.status_label.pack(side=tk.LEFT)
        
        # 清空按钮
        ModernButton(
            toolbar,
            text="Clear Output",
            command=self.clear_output,
            color="#95a5a6",
            hover_color="#7f8c8d",
            icon="🗑️",
            height=30,
            width=120
        ).pack(side=tk.RIGHT)

    # --- 逻辑功能部分 (保持原有逻辑，适配新UI) ---
    
    def run_scenario(self, scenario):
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
        defense_map = {
            "all": "no_def rolling window challenge",
            "no_def": "no_def",
            "rolling": "rolling",
            "window": "window",
            "challenge": "challenge"
        }
        modes = defense_map[self.defense_var.get()]
        cmd = f"--modes {modes} --runs {self.runs_var.get()} --num-legit 20 --num-replay 100 --p-loss {self.ploss_var.get()} --p-reorder {self.preorder_var.get()}"
        self.run_command(cmd, "自定义实验")

    def run_command(self, args, description):
        if self.running:
            messagebox.showwarning("Busy", "Experiment is running! / 实验正在进行中")
            return
        
        self.running = True
        self.set_status(True, f"Running: {description}...")
        
        self.output_text.insert(tk.END, f"\n{'='*60}\n")
        self.output_text.insert(tk.END, f"▶️ START: {description}\n")
        self.output_text.insert(tk.END, f"{'='*60}\n\n")
        self.output_text.see(tk.END)
        
        def run_in_thread():
            try:
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
                self.output_queue.put("\n✅ DONE / 完成\n")
            except Exception as e:
                self.output_queue.put(f"\n❌ ERROR: {str(e)}\n")
            finally:
                self.running = False
                self.set_status(False)
        
        threading.Thread(target=run_in_thread, daemon=True).start()

    def generate_plots(self):
        self.set_status(True, "Generating plots...")
        self.output_text.insert(tk.END, "\n📊 Generating plots...\n")
        def run():
            subprocess.run("source .venv/bin/activate && python scripts/plot_results.py", shell=True, executable='/bin/bash')
            self.output_queue.put("✅ Plots generated in figures/\n")
            self.running = False
            self.set_status(False)
        self.running = True
        threading.Thread(target=run, daemon=True).start()

    def export_tables(self):
        self.set_status(True, "Exporting tables...")
        self.output_text.insert(tk.END, "\n📋 Exporting tables...\n")
        def run():
            subprocess.run("source .venv/bin/activate && python scripts/export_tables.py", shell=True, executable='/bin/bash')
            self.output_queue.put("✅ Tables exported to docs/\n")
            self.running = False
            self.set_status(False)
        self.running = True
        threading.Thread(target=run, daemon=True).start()

    def clear_output(self):
        self.output_text.delete(1.0, tk.END)

    def set_status(self, is_running, text=None):
        if text:
            self.status_label.config(text=f"● {text}")
        else:
            self.status_label.config(text="● Ready")
            
        if is_running:
            self.status_label.config(fg=COLORS["warning"])
        else:
            self.status_label.config(fg=COLORS["success"])

    def check_output(self):
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