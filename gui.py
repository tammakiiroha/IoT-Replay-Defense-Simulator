#!/usr/bin/env python3
"""
Graphical User Interface for Replay Attack Simulation
图形界面 - 美化版 + 多语言支持 (Modern UI + Multi-language)
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import subprocess
import threading
import queue
import sys
import platform

# --- 多语言文本配置 ---
TRANSLATIONS = {
    "en": {
        "title": "Replay Attack Simulation Toolkit",
        "subtitle": "Defense Evaluation System",
        "version": "Version",
        "scenarios": "QUICK SCENARIOS",
        "dashboard": "Dashboard / Control Panel",
        "custom_exp": "Custom Experiment",
        "defense_mech": "Defense Mechanisms",
        "all": "All (Compare all)",
        "no_def": "No Defense (Baseline)",
        "rolling": "Rolling Counter + MAC",
        "window": "Sliding Window",
        "challenge": "Challenge-Response",
        "runs": "Monte Carlo Runs",
        "p_loss": "Packet Loss Rate",
        "p_reorder": "Reorder Rate",
        "start_sim": "START SIMULATION",
        "live_output": "Live Output",
        "status_ready": "Ready",
        "status_running": "Running",
        "clear_output": "Clear Output",
        "generate_plots": "Generate Plots",
        "export_tables": "Export Tables",
        "quick_test": "Quick Test",
        "quick_desc": "30s test run",
        "baseline": "Baseline",
        "baseline_desc": "Compare all modes",
        "packet_loss": "Packet Loss",
        "loss_desc": "10% loss test",
        "reorder": "Reordering",
        "reorder_desc": "30% reorder test",
        "harsh": "Harsh Network",
        "harsh_desc": "Loss + Reorder",
        "busy_msg": "An experiment is already running!",
        "done": "DONE",
        "error": "ERROR",
        "language": "Language",
    },
    "zh": {
        "title": "重放攻击仿真工具包",
        "subtitle": "防御机制评估系统",
        "version": "版本",
        "scenarios": "快速场景",
        "dashboard": "仪表盘 / 控制面板",
        "custom_exp": "自定义实验",
        "defense_mech": "防御机制",
        "all": "全部对比",
        "no_def": "无防御（基线）",
        "rolling": "滚动计数器 + MAC",
        "window": "滑动窗口",
        "challenge": "挑战-响应",
        "runs": "运行次数（蒙特卡洛）",
        "p_loss": "丢包率",
        "p_reorder": "乱序率",
        "start_sim": "开始仿真",
        "live_output": "实时输出",
        "status_ready": "就绪",
        "status_running": "运行中",
        "clear_output": "清空输出",
        "generate_plots": "生成图表",
        "export_tables": "导出表格",
        "quick_test": "快速测试",
        "quick_desc": "30秒测试运行",
        "baseline": "基线对比",
        "baseline_desc": "对比所有模式",
        "packet_loss": "丢包测试",
        "loss_desc": "10%丢包测试",
        "reorder": "乱序测试",
        "reorder_desc": "30%乱序测试",
        "harsh": "恶劣网络",
        "harsh_desc": "丢包+乱序",
        "busy_msg": "实验正在运行中！",
        "done": "完成",
        "error": "错误",
        "language": "语言",
    },
    "ja": {
        "title": "リプレイ攻撃シミュレーションツールキット",
        "subtitle": "防御メカニズム評価システム",
        "version": "バージョン",
        "scenarios": "クイックシナリオ",
        "dashboard": "ダッシュボード / コントロールパネル",
        "custom_exp": "カスタム実験",
        "defense_mech": "防御メカニズム",
        "all": "すべて（比較）",
        "no_def": "防御なし（ベースライン）",
        "rolling": "ローリングカウンタ + MAC",
        "window": "スライディングウィンドウ",
        "challenge": "チャレンジレスポンス",
        "runs": "実行回数（モンテカルロ）",
        "p_loss": "パケット損失率",
        "p_reorder": "並び替え率",
        "start_sim": "シミュレーション開始",
        "live_output": "リアルタイム出力",
        "status_ready": "準備完了",
        "status_running": "実行中",
        "clear_output": "出力をクリア",
        "generate_plots": "グラフ生成",
        "export_tables": "テーブル出力",
        "quick_test": "クイックテスト",
        "quick_desc": "30秒テスト実行",
        "baseline": "ベースライン",
        "baseline_desc": "全モード比較",
        "packet_loss": "パケット損失",
        "loss_desc": "10%損失テスト",
        "reorder": "並び替えテスト",
        "reorder_desc": "30%並び替え",
        "harsh": "厳しいネットワーク",
        "harsh_desc": "損失+並び替え",
        "busy_msg": "実験はすでに実行中です！",
        "done": "完了",
        "error": "エラー",
        "language": "言語",
    }
}

# --- 增强的颜色配置 ---
COLORS = {
    "bg_dark": "#1a252f",       # 更深的背景
    "bg_medium": "#2c3e50",     # 中等背景
    "bg_light": "#f5f6fa",      # 浅色背景
    "accent": "#3498db",        # 蓝色
    "accent_hover": "#2980b9",
    "success": "#2ecc71",       # 绿色
    "success_hover": "#27ae60",
    "warning": "#f39c12",       # 橙色
    "danger": "#e74c3c",        # 红色
    "purple": "#9b59b6",        # 紫色
    "text_light": "#ffffff",
    "text_dark": "#2c3e50",
    "text_muted": "#7f8c8d",
    "card_bg": "#ffffff",
    "border": "#dcdde1",
    "shadow": "#00000020"
}

# --- 字体配置 ---
if platform.system() == "Darwin":  # macOS
    FONTS = {
        "h1": ("SF Pro Display", 26, "bold"),
        "h2": ("SF Pro Display", 18, "bold"),
        "h3": ("SF Pro Display", 14, "bold"),
        "body": ("SF Pro Text", 13),
        "small": ("SF Pro Text", 11),
        "mono": ("SF Mono", 11),
    }
else:
    FONTS = {
        "h1": ("Segoe UI", 22, "bold"),
        "h2": ("Segoe UI", 16, "bold"),
        "h3": ("Segoe UI", 12, "bold"),
        "body": ("Segoe UI", 11),
        "small": ("Segoe UI", 9),
        "mono": ("Consolas", 10),
    }

class ModernButton(tk.Frame):
    """现代风格按钮 - 带圆角效果（通过Canvas模拟）"""
    def __init__(self, parent, text, command, color=COLORS["accent"], hover_color=COLORS["accent_hover"], **kwargs):
        super().__init__(parent, bg=color, cursor="hand2", **kwargs)
        self.command = command
        self.color = color
        self.hover_color = hover_color
        
        self.pack_propagate(False)
        
        self.label = tk.Label(
            self, 
            text=text, 
            bg=color, 
            fg="white", 
            font=FONTS["h3"],
            cursor="hand2"
        )
        self.label.place(relx=0.5, rely=0.5, anchor="center")
        
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
    """卡片容器 - 带阴影效果"""
    def __init__(self, parent, title, **kwargs):
        # 外层容器（阴影）
        shadow_frame = tk.Frame(parent, bg=COLORS["shadow"])
        shadow_frame.pack(fill=tk.BOTH, expand=True, padx=(2, 0), pady=(2, 0))
        
        # 内层卡片
        super().__init__(shadow_frame, bg=COLORS["card_bg"], padx=20, pady=20, **kwargs)
        self.pack(fill=tk.BOTH, expand=True)
        
        # 标题
        if title:
            title_label = tk.Label(
                self, 
                text=title, 
                font=FONTS["h2"], 
                fg=COLORS["text_dark"], 
                bg=COLORS["card_bg"]
            )
            title_label.pack(anchor="w", pady=(0, 15))
            
            # 标题下划线
            tk.Frame(self, bg=COLORS["accent"], height=3, width=60).pack(anchor="w", pady=(0, 15))

class SimulationGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Replay Attack Simulation Toolkit")
        self.root.geometry("1320x880")
        self.root.configure(bg=COLORS["bg_light"])
        
        # 当前语言
        self.current_lang = tk.StringVar(value="en")
        
        # 设置样式
        self.setup_style()
        
        # 输出队列
        self.output_queue = queue.Queue()
        self.running = False
        
        # 创建界面
        self.create_widgets()
        
        # 定期检查输出
        self.check_output()
    
    def t(self, key):
        """获取翻译文本"""
        return TRANSLATIONS[self.current_lang.get()].get(key, key)
    
    def setup_style(self):
        """配置ttk样式"""
        style = ttk.Style()
        style.theme_use('clam')
        
        style.configure(".", background=COLORS["bg_light"])
        style.configure("TRadiobutton", 
                       background=COLORS["card_bg"], 
                       font=FONTS["body"],
                       foreground=COLORS["text_dark"])
        style.configure("TSeparator", background=COLORS["border"])

    def create_widgets(self):
        """创建主界面"""
        
        # === 顶部导航栏 ===
        topbar = tk.Frame(self.root, bg=COLORS["bg_dark"], height=70)
        topbar.pack(fill=tk.X)
        topbar.pack_propagate(False)
        
        # Logo区
        logo_frame = tk.Frame(topbar, bg=COLORS["bg_dark"])
        logo_frame.pack(side=tk.LEFT, padx=30)
        
        tk.Label(
            logo_frame, 
            text="[ REPLAY SIM ]", 
            font=("Arial", 18, "bold"), 
            bg=COLORS["bg_dark"], 
            fg="white"
        ).pack(side=tk.LEFT)
        
        # 语言切换器
        lang_frame = tk.Frame(topbar, bg=COLORS["bg_dark"])
        lang_frame.pack(side=tk.RIGHT, padx=30)
        
        tk.Label(lang_frame, text=self.t("language") + ":", font=FONTS["small"], bg=COLORS["bg_dark"], fg=COLORS["text_muted"]).pack(side=tk.LEFT, padx=(0, 10))
        
        for lang_code, lang_name in [("en", "English"), ("zh", "中文"), ("ja", "日本語")]:
            btn = tk.Button(
                lang_frame,
                text=lang_name,
                font=FONTS["small"],
                bg=COLORS["bg_medium"] if self.current_lang.get() == lang_code else COLORS["bg_dark"],
                fg="white",
                activebackground=COLORS["bg_medium"],
                activeforeground="white",
                relief=tk.FLAT,
                cursor="hand2",
                padx=15,
                pady=5,
                command=lambda lc=lang_code: self.switch_language(lc)
            )
            btn.pack(side=tk.LEFT, padx=2)
        
        # === 主内容区 ===
        main_container = tk.Frame(self.root, bg=COLORS["bg_light"])
        main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 左侧：快速场景
        left_panel = tk.Frame(main_container, bg=COLORS["bg_light"], width=320)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        left_panel.pack_propagate(False)
        
        # 中间：配置
        middle_panel = tk.Frame(main_container, bg=COLORS["bg_light"])
        middle_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)
        
        # 右侧：输出
        right_panel = tk.Frame(main_container, bg=COLORS["bg_light"])
        right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0))
        
        self.create_scenario_panel(left_panel)
        self.create_config_panel(middle_panel)
        self.create_output_panel(right_panel)
    
    def create_scenario_panel(self, parent):
        """快速场景面板"""
        card = CardFrame(parent, self.t("scenarios"))
        
        scenarios = [
            ("quick_test", "quick_desc", "quick", COLORS["success"]),
            ("baseline", "baseline_desc", "baseline", COLORS["accent"]),
            ("packet_loss", "loss_desc", "packet_loss", COLORS["warning"]),
            ("reorder", "reorder_desc", "reorder", COLORS["purple"]),
            ("harsh", "harsh_desc", "harsh", COLORS["danger"]),
        ]
        
        for title_key, desc_key, cmd, color in scenarios:
            # 场景按钮容器
            scenario_frame = tk.Frame(card, bg=color, cursor="hand2", height=70)
            scenario_frame.pack(fill=tk.X, pady=8)
            scenario_frame.pack_propagate(False)
            
            # 左侧色条
            tk.Frame(scenario_frame, bg=color, width=5).pack(side=tk.LEFT, fill=tk.Y)
            
            # 文字区
            text_area = tk.Frame(scenario_frame, bg=color, padx=15, pady=10)
            text_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            
            title_label = tk.Label(
                text_area, 
                text=self.t(title_key), 
                font=FONTS["h3"], 
                bg=color, 
                fg="white", 
                anchor="w"
            )
            title_label.pack(fill=tk.X)
            
            desc_label = tk.Label(
                text_area, 
                text=self.t(desc_key), 
                font=FONTS["small"], 
                bg=color, 
                fg="white", 
                anchor="w"
            )
            desc_label.pack(fill=tk.X)
            
            # 绑定点击
            for widget in [scenario_frame, text_area, title_label, desc_label]:
                widget.bind("<Button-1>", lambda e, s=cmd: self.run_scenario(s))
        
        # 底部工具按钮
        tk.Frame(card, bg=COLORS["card_bg"], height=20).pack()
        
        ModernButton(
            card, 
            text=self.t("generate_plots"), 
            command=self.generate_plots,
            color=COLORS["bg_medium"],
            hover_color=COLORS["bg_dark"],
            height=45
        ).pack(fill=tk.X, pady=5)
        
        ModernButton(
            card, 
            text=self.t("export_tables"), 
            command=self.export_tables,
            color=COLORS["bg_medium"],
            hover_color=COLORS["bg_dark"],
            height=45
        ).pack(fill=tk.X, pady=5)
    
    def create_config_panel(self, parent):
        """自定义配置面板"""
        card = CardFrame(parent, self.t("custom_exp"))
        
        # 防御机制
        tk.Label(card, text=self.t("defense_mech"), font=FONTS["h3"], bg=COLORS["card_bg"], fg=COLORS["text_dark"]).pack(anchor="w", pady=(0, 10))
        
        self.defense_var = tk.StringVar(value="all")
        defense_frame = tk.Frame(card, bg=COLORS["card_bg"])
        defense_frame.pack(fill=tk.X, pady=(0, 20))
        
        for key in ["all", "no_def", "rolling", "window", "challenge"]:
            ttk.Radiobutton(
                defense_frame, 
                text=self.t(key), 
                variable=self.defense_var, 
                value=key
            ).pack(anchor="w", pady=3)
        
        # 参数滑动条
        self.runs_var = tk.IntVar(value=50)
        self.ploss_var = tk.DoubleVar(value=0.0)
        self.preorder_var = tk.DoubleVar(value=0.0)
        
        self.create_slider(card, "runs", self.runs_var, 10, 200, False)
        self.create_slider(card, "p_loss", self.ploss_var, 0.0, 0.5, True)
        self.create_slider(card, "p_reorder", self.preorder_var, 0.0, 0.5, True)
        
        # 运行按钮
        tk.Frame(card, bg=COLORS["card_bg"], height=20).pack()
        ModernButton(
            card, 
            text=self.t("start_sim"), 
            command=self.run_custom,
            color=COLORS["success"],
            hover_color=COLORS["success_hover"],
            height=55
        ).pack(fill=tk.X)
    
    def create_slider(self, parent, label_key, variable, min_val, max_val, is_float):
        """创建滑动条"""
        frame = tk.Frame(parent, bg=COLORS["card_bg"], pady=12)
        frame.pack(fill=tk.X)
        
        header = tk.Frame(frame, bg=COLORS["card_bg"])
        header.pack(fill=tk.X, pady=(0, 8))
        
        tk.Label(
            header, 
            text=self.t(label_key), 
            font=FONTS["body"], 
            bg=COLORS["card_bg"], 
            fg=COLORS["text_muted"]
        ).pack(side=tk.LEFT)
        
        value_label = tk.Label(
            header, 
            font=FONTS["h3"], 
            bg=COLORS["card_bg"], 
            fg=COLORS["accent"]
        )
        value_label.pack(side=tk.RIGHT)
        
        def update(*args):
            val = variable.get()
            value_label.config(text=f"{val:.2f}" if is_float else f"{int(val)}")
        
        variable.trace_add("write", update)
        update()
        
        ttk.Scale(frame, from_=min_val, to=max_val, variable=variable, orient="horizontal").pack(fill=tk.X)
    
    def create_output_panel(self, parent):
        """输出面板"""
        card = CardFrame(parent, self.t("live_output"))
        
        # 输出文本框
        text_container = tk.Frame(card, bg=COLORS["bg_dark"], relief=tk.FLAT)
        text_container.pack(fill=tk.BOTH, expand=True)
        
        self.output_text = scrolledtext.ScrolledText(
            text_container,
            wrap=tk.WORD,
            font=FONTS["mono"],
            bg=COLORS["bg_dark"],
            fg=COLORS["text_light"],
            insertbackground="white",
            padx=15,
            pady=15,
            borderwidth=0,
            highlightthickness=0
        )
        self.output_text.pack(fill=tk.BOTH, expand=True)
        
        # 底部工具栏
        toolbar = tk.Frame(card, bg=COLORS["card_bg"], height=50, pady=12)
        toolbar.pack(fill=tk.X)
        
        self.status_label = tk.Label(
            toolbar, 
            text=f"● {self.t('status_ready')}", 
            font=FONTS["body"], 
            fg=COLORS["success"], 
            bg=COLORS["card_bg"]
        )
        self.status_label.pack(side=tk.LEFT)
        
        ModernButton(
            toolbar,
            text=self.t("clear_output"),
            command=self.clear_output,
            color=COLORS["text_muted"],
            hover_color="#95a5a6",
            height=35,
            width=140
        ).pack(side=tk.RIGHT)
    
    def switch_language(self, lang_code):
        """切换语言并刷新界面"""
        self.current_lang.set(lang_code)
        # 销毁当前界面
        for widget in self.root.winfo_children():
            widget.destroy()
        # 重新创建界面
        self.create_widgets()
    
    # === 业务逻辑 ===
    
    def run_scenario(self, scenario):
        scenarios = {
            "quick": ("Quick Test", "--modes window --runs 30 --num-legit 10 --num-replay 50 --p-loss 0.05"),
            "baseline": ("Baseline", "--modes no_def rolling window challenge --runs 100 --num-legit 20 --num-replay 100 --p-loss 0.0 --p-reorder 0.0"),
            "packet_loss": ("Packet Loss", "--modes rolling window challenge --runs 100 --num-legit 20 --num-replay 100 --p-loss 0.1 --p-reorder 0.0"),
            "reorder": ("Reordering", "--modes rolling window --runs 100 --num-legit 20 --num-replay 100 --p-loss 0.0 --p-reorder 0.3"),
            "harsh": ("Harsh Network", "--modes window challenge --runs 100 --num-legit 20 --num-replay 100 --p-loss 0.15 --p-reorder 0.3"),
        }
        name, cmd = scenarios[scenario]
        self.run_command(cmd, name)
    
    def run_custom(self):
        defense_map = {"all": "no_def rolling window challenge", "no_def": "no_def", "rolling": "rolling", "window": "window", "challenge": "challenge"}
        modes = defense_map[self.defense_var.get()]
        cmd = f"--modes {modes} --runs {self.runs_var.get()} --num-legit 20 --num-replay 100 --p-loss {self.ploss_var.get()} --p-reorder {self.preorder_var.get()}"
        self.run_command(cmd, self.t("custom_exp"))
    
    def run_command(self, args, description):
        if self.running:
            messagebox.showwarning("Busy", self.t("busy_msg"))
            return
        
        self.running = True
        self.set_status(True, f"{self.t('status_running')}: {description}")
        
        self.output_text.insert(tk.END, f"\n{'='*60}\n▶ START: {description}\n{'='*60}\n\n")
        self.output_text.see(tk.END)
        
        def run_thread():
            try:
                cmd = f"source .venv/bin/activate && python main.py {args}"
                proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, executable='/bin/bash')
                for line in proc.stdout:
                    self.output_queue.put(line)
                proc.wait()
                self.output_queue.put(f"\n✅ {self.t('done')}\n")
            except Exception as e:
                self.output_queue.put(f"\n❌ {self.t('error')}: {e}\n")
            finally:
                self.running = False
                self.set_status(False)
        
        threading.Thread(target=run_thread, daemon=True).start()
    
    def generate_plots(self):
        self.set_status(True, f"{self.t('status_running')}...")
        def run():
            subprocess.run("source .venv/bin/activate && python scripts/plot_results.py", shell=True, executable='/bin/bash')
            self.output_queue.put(f"✅ {self.t('generate_plots')} {self.t('done')}\n")
            self.running = False
            self.set_status(False)
        self.running = True
        threading.Thread(target=run, daemon=True).start()
    
    def export_tables(self):
        self.set_status(True, f"{self.t('status_running')}...")
        def run():
            subprocess.run("source .venv/bin/activate && python scripts/export_tables.py", shell=True, executable='/bin/bash')
            self.output_queue.put(f"✅ {self.t('export_tables')} {self.t('done')}\n")
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
            self.status_label.config(text=f"● {self.t('status_ready')}")
        
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
