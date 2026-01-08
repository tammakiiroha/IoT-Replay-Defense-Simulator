"""
主应用程序类
Main simulation GUI application - Web-style modern design with ALL original features
"""

import os
import platform
import queue
import signal
import subprocess
import threading
import tkinter as tk
from datetime import datetime
from tkinter import ttk, messagebox, filedialog, scrolledtext

from ..theme import COLORS, FONTS, MODE_META
from ..translations import TRANSLATIONS
from ..widgets import ModernButton, ModernCard, SectionHeader, ResultBarChart
import json


class SimulationGUI:
    """重放攻击仿真 GUI 主类 - Web 风格 + 完整功能"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("IoT Replay Attack Defense Simulator")
        # 动态调整窗口大小和位置 (适配截图尺寸)
        width = 1750
        height = 1000
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        
        # 居中显示
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.minsize(1100, 800)  # 防止窗口过小导致侧边栏显示不全
        self.root.configure(bg=COLORS["bg_main"])
        
        self.current_lang = tk.StringVar(value="en")
        self.output_queue = queue.Queue()
        self.running = False
        self.current_process = None
        
        # === 配置变量（与原版完全一致）===
        self.defense_var = tk.StringVar(value="all")  # 单选：all/no_def/rolling/window/challenge
        self.attack_mode_var = tk.StringVar(value="post")  # post/inline
        self.runs_var = tk.IntVar(value=100)
        self.num_legit_var = tk.IntVar(value=20)
        self.num_replay_var = tk.IntVar(value=100)
        self.ploss_var = tk.DoubleVar(value=0.0)
        self.preorder_var = tk.DoubleVar(value=0.0)
        self.window_size_var = tk.IntVar(value=5)
        self.seed_var = tk.IntVar(value=0)
        self.attacker_loss_var = tk.DoubleVar(value=0.0)
        
        # UI 组件引用
        self.output_text = None
        self.status_label = None
        self.stop_button = None
        
        self.setup_style()
        self.create_widgets()
        self.check_output()
    
    def t(self, key):
        """获取翻译"""
        return TRANSLATIONS[self.current_lang.get()].get(key, key)
    
    def setup_style(self):
        """配置 ttk 样式"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # 单选按钮样式
        style.configure(
            "Modern.TRadiobutton",
            background=COLORS["bg_card"],
            foreground=COLORS["text_primary"],
            font=FONTS["body"],
        )
        style.map("Modern.TRadiobutton",
            background=[('active', COLORS["bg_card"])],
            foreground=[('active', COLORS["primary"])])
        
        # 滑动条样式
        style.configure(
            "Modern.Horizontal.TScale",
            background=COLORS["bg_card"],
            troughcolor=COLORS["bg_section"],
            sliderlength=16,
        )
    
    def create_widgets(self):
        """创建主界面 - Web 风格侧边栏+主内容区布局"""
        
        # === 主容器 ===
        main_container = tk.Frame(self.root, bg=COLORS["bg_main"])
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # === 左侧边栏 ===
        sidebar = tk.Frame(
            main_container, 
            bg=COLORS["bg_card"], 
            width=420,
            highlightbackground=COLORS["border"],
            highlightthickness=1
        )
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)
        
        # 侧边栏滚动支持
        sidebar_canvas = tk.Canvas(sidebar, bg=COLORS["bg_card"], highlightthickness=0)
        sidebar_scrollbar = tk.Scrollbar(sidebar, orient="vertical", command=sidebar_canvas.yview)
        sidebar_content = tk.Frame(sidebar_canvas, bg=COLORS["bg_card"])
        
        sidebar_content.bind(
            "<Configure>",
            lambda e: sidebar_canvas.configure(scrollregion=sidebar_canvas.bbox("all"))
        )
        
        sidebar_canvas.create_window((0, 0), window=sidebar_content, anchor="nw", width=418)
        sidebar_canvas.configure(yscrollcommand=sidebar_scrollbar.set)
        
        # 鼠标滚轮支持
        def _on_mousewheel(event):
            sidebar_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        sidebar_canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        sidebar_canvas.pack(side="left", fill="both", expand=True)
        sidebar_scrollbar.pack(side="right", fill="y")
        
        # --- 侧边栏内容 ---
        self._create_sidebar_header(sidebar_content)
        self._create_scenario_section(sidebar_content)
        self._create_config_section(sidebar_content)
        self._create_run_button(sidebar_content)
        
        # === 右侧主内容区 ===
        main_content = tk.Frame(main_container, bg=COLORS["bg_main"])
        main_content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=24, pady=24)
        
        self._create_dashboard(main_content)
    
    def _create_sidebar_header(self, parent):
        """创建侧边栏标题区"""
        header = tk.Frame(parent, bg=COLORS["bg_card"], pady=20, padx=24)
        header.pack(fill=tk.X)
        
        # 1. 语言切换器行 (放在最上方，避免与标题重叠)
        lang_row = tk.Frame(header, bg=COLORS["bg_card"])
        lang_row.pack(fill=tk.X, pady=(0, 10))
        
        lang_frame = tk.Frame(lang_row, bg=COLORS["bg_card"])
        lang_frame.pack(side=tk.RIGHT)
        
        for code, name in [("zh", "中文"), ("ja", "日本語"), ("en", "English")]:
            is_active = self.current_lang.get() == code
            
            btn = tk.Label(
                lang_frame,
                text=name,
                font=(FONTS["small"][0], 11, "bold"),
                fg=COLORS["text_light"] if is_active else COLORS["text_secondary"],
                bg=COLORS["primary"] if is_active else COLORS["bg_section"],
                padx=10,
                pady=5,
                cursor="hand2"
            )
            btn.pack(side=tk.LEFT, padx=2)
            
            # 悬停效果
            def on_enter(e, b=btn, active=is_active):
                if not active:
                    b.config(bg=COLORS["border"], fg=COLORS["text_primary"])
            
            def on_leave(e, b=btn, active=is_active):
                if not active:
                    b.config(bg=COLORS["bg_section"], fg=COLORS["text_secondary"])
            
            btn.bind("<Enter>", on_enter)
            btn.bind("<Leave>", on_leave)
            
            # 绑定点击
            def on_click(e, c=code):
                self.switch_language(c)
            btn.bind("<Button-1>", on_click)
            
        # 2. 标题行 (Logo + Title)
        title_row = tk.Frame(header, bg=COLORS["bg_card"])
        title_row.pack(fill=tk.X)
        
        # 图标
        icon_bg = tk.Frame(title_row, bg=COLORS["primary"], padx=8, pady=8)
        icon_bg.pack(side=tk.LEFT, padx=(0, 12))
        
        tk.Label(icon_bg, text="🛡️", font=("Arial", 16), bg=COLORS["primary"]).pack()
        
        # 标题文字
        title_text_frame = tk.Frame(title_row, bg=COLORS["bg_card"])
        title_text_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        tk.Label(
            title_text_frame,
            text=self.t("title"),
            font=FONTS["title"],
            fg=COLORS["text_primary"],
            bg=COLORS["bg_card"],
            wraplength=300, # 允许标题换行
            justify=tk.LEFT
        ).pack(anchor="w")
        
        # 副标题
        tk.Label(
            header,
            text=self.t("subtitle"),
            font=FONTS["small"],
            fg=COLORS["text_secondary"],
            bg=COLORS["bg_card"],
            wraplength=360,
            justify=tk.LEFT
        ).pack(anchor="w", pady=(12, 0))
    
    def _create_scenario_section(self, parent):
        """创建场景选择区（可直接运行）"""
        section = tk.Frame(parent, bg=COLORS["bg_card"], padx=24, pady=16)
        section.pack(fill=tk.X)
        
        # 标题
        SectionHeader(section, self.t("scenarios"), icon="⚡").pack(anchor="w", pady=(0, 12))
        
        # 场景定义（与 Web 版一致）
        scenarios = [
            ("ideal_scenario", "ideal_desc", "ideal", COLORS["success"]),
            ("office_scenario", "office_desc", "office", COLORS["info"]),
            ("industrial_scenario", "industrial_desc", "industrial", COLORS["warning"]),
            ("multihop_scenario", "multihop_desc", "multihop", COLORS["mode_rolling"]),
            ("attack_heavy_scenario", "attack_heavy_desc", "attack_heavy", COLORS["danger"]),
        ]
        
        for title_key, desc_key, cmd, color in scenarios:
            scenario_frame = tk.Frame(
                section,
                bg=COLORS["bg_section"],
                cursor="hand2",
                highlightbackground=COLORS["border"],
                highlightthickness=1
            )
            scenario_frame.pack(fill=tk.X, pady=4)
            
            # 左侧色条
            tk.Frame(scenario_frame, bg=color, width=4).pack(side=tk.LEFT, fill=tk.Y)
            
            # 内容区
            content = tk.Frame(scenario_frame, bg=COLORS["bg_section"], padx=14, pady=10)
            content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            
            tk.Label(
                content,
                text=self.t(title_key),
                font=FONTS["h3"],
                fg=COLORS["text_primary"],
                bg=COLORS["bg_section"],
                anchor="w",
                cursor="hand2"
            ).pack(fill=tk.X)
            
            tk.Label(
                content,
                text=self.t(desc_key),
                font=FONTS["small"],
                fg=COLORS["text_muted"],
                bg=COLORS["bg_section"],
                anchor="w",
                cursor="hand2"
            ).pack(fill=tk.X, pady=(2, 0))
            
            # 绑定点击（直接运行，与原版一致）
            for widget in [scenario_frame, content] + list(content.winfo_children()):
                widget.bind("<Button-1>", lambda e, s=cmd: self.run_scenario(s))
        
        # 分割线
        tk.Frame(section, bg=COLORS["divider"], height=1).pack(fill=tk.X, pady=(16, 8))
        
        # 工具按钮
        tool_frame = tk.Frame(section, bg=COLORS["bg_card"])
        tool_frame.pack(fill=tk.X)
        
        ModernButton(
            tool_frame,
            text=self.t("generate_plots"),
            command=self.generate_plots,
            style="secondary",
            width=175,
            height=36
        ).pack(side=tk.LEFT, padx=(0, 8))
        
        ModernButton(
            tool_frame,
            text=self.t("export_tables"),
            command=self.export_tables,
            style="secondary",
            width=175,
            height=36
        ).pack(side=tk.LEFT)
    
    def _create_config_section(self, parent):
        """创建完整配置区（恢复所有原有功能）"""
        section = tk.Frame(parent, bg=COLORS["bg_card"], padx=24, pady=16)
        section.pack(fill=tk.X)
        
        # 标题
        SectionHeader(section, self.t("custom_exp"), icon="⚙️").pack(anchor="w", pady=(0, 12))
        
        # === 防御机制（单选，与原版一致）===
        tk.Label(
            section,
            text=self.t("defense_mech"),
            font=FONTS["h3"],
            fg=COLORS["text_primary"],
            bg=COLORS["bg_card"]
        ).pack(anchor="w", pady=(0, 8))
        
        for key in ["all", "no_def", "rolling", "window", "challenge"]:
            ttk.Radiobutton(
                section,
                text=self.t(key),
                variable=self.defense_var,
                value=key,
                style="Modern.TRadiobutton"
            ).pack(anchor="w", pady=2)
        
        # 分割线
        tk.Frame(section, bg=COLORS["divider"], height=1).pack(fill=tk.X, pady=16)
        
        # === 攻击模式（与原版一致）===
        tk.Label(
            section,
            text=self.t("attack_mode"),
            font=FONTS["h3"],
            fg=COLORS["text_primary"],
            bg=COLORS["bg_card"]
        ).pack(anchor="w", pady=(0, 8))
        
        for key, value in [("post_run", "post"), ("inline", "inline")]:
            ttk.Radiobutton(
                section,
                text=self.t(key),
                variable=self.attack_mode_var,
                value=value,
                style="Modern.TRadiobutton"
            ).pack(anchor="w", pady=2)
        
        # 分割线
        tk.Frame(section, bg=COLORS["divider"], height=1).pack(fill=tk.X, pady=16)
        
        # === 参数滑块（与原版一致）===
        tk.Label(
            section,
            text=self.t("params"),
            font=FONTS["h3"],
            fg=COLORS["text_primary"],
            bg=COLORS["bg_card"]
        ).pack(anchor="w", pady=(0, 8))
        
        self._create_slider(section, "runs", self.runs_var, 10, 500, False)
        self._create_slider(section, "num_legit", self.num_legit_var, 5, 100, False)
        self._create_slider(section, "num_replay", self.num_replay_var, 10, 500, False)
        self._create_slider(section, "p_loss", self.ploss_var, 0.0, 0.5, True)
        self._create_slider(section, "p_reorder", self.preorder_var, 0.0, 0.5, True)
        self._create_slider(section, "window_size", self.window_size_var, 1, 20, False)
        
        # 高级参数
        tk.Frame(section, bg=COLORS["divider"], height=1).pack(fill=tk.X, pady=16)
        tk.Label(
            section,
            text=self.t("advanced"),
            font=FONTS["h3"],
            fg=COLORS["text_secondary"],
            bg=COLORS["bg_card"]
        ).pack(anchor="w", pady=(0, 8))
        
        self._create_slider(section, "seed", self.seed_var, 0, 9999, False)
        self._create_slider(section, "attacker_loss", self.attacker_loss_var, 0.0, 0.5, True)
    
    def _create_slider(self, parent, label_key, variable, min_val, max_val, is_float):
        """创建滑块（与原版功能一致）"""
        frame = tk.Frame(parent, bg=COLORS["bg_card"], pady=6)
        frame.pack(fill=tk.X)
        
        # 标题行
        header = tk.Frame(frame, bg=COLORS["bg_card"])
        header.pack(fill=tk.X, pady=(0, 4))
        
        tk.Label(
            header,
            text=self.t(label_key),
            font=FONTS["body"],
            fg=COLORS["text_secondary"],
            bg=COLORS["bg_card"],
            anchor="w"
        ).pack(side=tk.LEFT)
        
        # 数值显示
        value_label = tk.Label(
            header,
            font=(FONTS["h2"][0], FONTS["h2"][1], "bold"),
            fg=COLORS["primary"],
            bg=COLORS["bg_card"]
        )
        value_label.pack(side=tk.RIGHT, padx=8)
        
        def update_value(*args):
            val = variable.get()
            text = f"{val:.2f}" if is_float else f"{int(val)}"
            
            # 窗口大小提示
            if label_key == "window_size":
                ival = int(val)
                if ival < 3:
                    text += " ⚠"
                elif 3 <= ival <= 7:
                    text += " ✓"
                elif ival > 10:
                    text += " ⚠"
            
            # 随机种子提示
            elif label_key == "seed":
                ival = int(val)
                text += " 🎲" if ival == 0 else " 🔒"
            
            value_label.config(text=text)
        
        variable.trace_add("write", update_value)
        update_value()
        
        # 滑块
        ttk.Scale(
            frame,
            from_=min_val,
            to=max_val,
            variable=variable,
            orient="horizontal",
            style="Modern.Horizontal.TScale"
        ).pack(fill=tk.X)
        
        # 提示文本
        if label_key == "window_size":
            hint = {"en": "Recommended: 3-7", "zh": "推荐值：3-7", "ja": "推奨値：3-7"}
            tk.Label(frame, text=hint[self.current_lang.get()], font=FONTS["small"],
                    fg=COLORS["text_muted"], bg=COLORS["bg_card"]).pack(anchor="w")
        elif label_key == "seed":
            hint = {"en": "0=Random | Fixed=Reproducible", "zh": "0=随机 | 非0=可重现", "ja": "0=ランダム | 非0=再現可能"}
            tk.Label(frame, text=hint[self.current_lang.get()], font=FONTS["small"],
                    fg=COLORS["text_muted"], bg=COLORS["bg_card"]).pack(anchor="w")
    
    def _create_run_button(self, parent):
        """创建运行按钮"""
        btn_frame = tk.Frame(parent, bg=COLORS["bg_card"], padx=24, pady=20)
        btn_frame.pack(fill=tk.X)
        
        ModernButton(
            btn_frame,
            text=self.t("start_sim"),
            command=self.run_custom,
            style="dark",
            width=370,
            height=52
        ).pack()
    
    def _create_dashboard(self, parent):
        """创建主内容区的仪表盘"""
        # 标题
        header = tk.Frame(parent, bg=COLORS["bg_main"])
        header.pack(fill=tk.X, pady=(0, 16))
        
        tk.Label(
            header,
            text=self.t("dashboard"),
            font=(FONTS["title"][0], 24, "bold"),
            fg=COLORS["text_primary"],
            bg=COLORS["bg_main"]
        ).pack(side=tk.LEFT)
        
        tk.Label(
            header,
            text=self.t("dash_desc"),
            font=FONTS["body"],
            fg=COLORS["text_secondary"],
            bg=COLORS["bg_main"]
        ).pack(side=tk.LEFT, padx=(16, 0))
        
        # 指标帮助按钮
        help_btn = tk.Button(
            header,
            text="ⓘ " + self.t("metrics_help"),
            font=FONTS["small"],
            fg=COLORS["primary"],
            bg=COLORS["bg_main"],
            activebackground=COLORS["bg_section"],
            bd=0,
            cursor="hand2",
            command=self._show_metrics_help
        )
        help_btn.pack(side=tk.RIGHT)
        
        # 主内容卡片
        content_card = ModernCard(parent)
        content_card.pack(fill=tk.BOTH, expand=True)

        # 结果图表区 (新功能)
        charts_row = tk.Frame(content_card.content, bg=COLORS["bg_card"])
        charts_row.pack(fill=tk.X, pady=(0, 20))
        
        self.usability_chart = ResultBarChart(charts_row, "System Usability (Legit Acceptance)", unit="%")
        self.usability_chart.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 12))
        
        self.security_chart = ResultBarChart(charts_row, "Security Risk (Attack Success)", unit="%")
        self.security_chart.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 指标说明面板
        metrics_info = tk.Frame(content_card.content, bg=COLORS["bg_section"], padx=12, pady=8)
        metrics_info.pack(fill=tk.X, pady=(0, 12))
        
        tk.Label(
            metrics_info,
            text=self.t("metrics_explanation"),
            font=FONTS["small"],
            fg=COLORS["text_secondary"],
            bg=COLORS["bg_section"]
        ).pack(side=tk.LEFT)
        
        # 终端输出
        self.output_text = scrolledtext.ScrolledText(
            content_card.content,
            wrap=tk.WORD,
            font=FONTS["mono"],
            bg=COLORS["terminal_bg"],
            fg=COLORS["terminal_text"],
            insertbackground=COLORS["primary"],
            padx=20,
            pady=20,
            borderwidth=0,
            highlightthickness=0
        )
        self.output_text.pack(fill=tk.BOTH, expand=True)
        
        # 初始欢迎消息
        self.output_text.insert(tk.END, f"🛡️ {self.t('ready_title')}\n\n")
        self.output_text.insert(tk.END, f"{self.t('ready_desc')}\n")
        
        # 底部工具栏
        toolbar = tk.Frame(content_card.content, bg=COLORS["bg_card"], pady=12)
        toolbar.pack(fill=tk.X)
        
        # 状态标签
        self.status_label = tk.Label(
            toolbar,
            text=f"● {self.t('status_ready')}",
            font=FONTS["body"],
            fg=COLORS["success"],
            bg=COLORS["bg_card"]
        )
        self.status_label.pack(side=tk.LEFT)
        
        # 停止按钮
        self.stop_button = ModernButton(
            toolbar,
            text=self.t("stop_sim"),
            command=self.stop_experiment,
            style="secondary",
            width=80,
            height=32
        )
        
        # 保存和清空按钮
        ModernButton(
            toolbar,
            text=self.t("save_output"),
            command=self.save_output,
            style="secondary",
            width=120,
            height=32
        ).pack(side=tk.RIGHT, padx=(8, 0))
        
        ModernButton(
            toolbar,
            text=self.t("clear_output"),
            command=self.clear_output,
            style="secondary",
            width=80,
            height=32
        ).pack(side=tk.RIGHT)
    
    def _show_metrics_help(self):
        """显示指标帮助对话框"""
        help_text = self.t("metrics_tooltip")
        
        dialog = tk.Toplevel(self.root)
        dialog.title(self.t("metrics_help"))
        dialog.geometry("600x500")
        dialog.configure(bg=COLORS["bg_main"])
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 标题
        title_frame = tk.Frame(dialog, bg=COLORS["primary"], padx=20, pady=15)
        title_frame.pack(fill=tk.X)
        
        tk.Label(
            title_frame,
            text="📊 " + self.t("metrics_help"),
            font=FONTS["h1"],
            fg="white",
            bg=COLORS["primary"]
        ).pack()
        
        # 内容
        content_frame = tk.Frame(dialog, bg=COLORS["bg_main"], padx=20, pady=20)
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        text_widget = scrolledtext.ScrolledText(
            content_frame,
            wrap=tk.WORD,
            font=FONTS["body"],
            bg=COLORS["bg_card"],
            fg=COLORS["text_primary"],
            padx=15,
            pady=15,
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=COLORS["divider"]
        )
        text_widget.pack(fill=tk.BOTH, expand=True)
        text_widget.insert(1.0, help_text)
        text_widget.config(state=tk.DISABLED)
        
        # 关闭按钮
        btn_frame = tk.Frame(dialog, bg=COLORS["bg_main"], pady=15)
        btn_frame.pack(fill=tk.X)
        
        ModernButton(
            btn_frame,
            text="✓ OK",
            command=dialog.destroy,
            style="primary",
            width=100,
            height=40
        ).pack()
        
        # 居中
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
    
    def switch_language(self, lang_code):
        """切换语言并重建界面"""
        self.current_lang.set(lang_code)
        for widget in self.root.winfo_children():
            widget.destroy()
        self.create_widgets()
    
    # === 业务逻辑（与原版完全一致）===
    
    def run_scenario(self, scenario):
        """运行预设场景"""
        scenarios = {
            "ideal": ("Ideal Channel", "--modes no_def rolling window challenge --runs 200 --num-legit 20 --num-replay 100 --p-loss 0.0 --p-reorder 0.0 --attack-mode post"),
            "office": ("Office Environment", "--modes no_def rolling window challenge --runs 200 --num-legit 20 --num-replay 100 --p-loss 0.1 --p-reorder 0.05 --attack-mode post"),
            "industrial": ("Industrial Environment", "--modes no_def rolling window challenge --runs 200 --num-legit 20 --num-replay 100 --p-loss 0.25 --p-reorder 0.1 --attack-mode post"),
            "multihop": ("Multi-hop Mesh", "--modes no_def rolling window challenge --runs 200 --num-legit 20 --num-replay 100 --p-loss 0.1 --p-reorder 0.25 --attack-mode post"),
            "attack_heavy": ("Active Inline Attack", "--modes no_def rolling window challenge --runs 200 --num-legit 20 --num-replay 100 --p-loss 0.1 --p-reorder 0.1 --attack-mode inline --inline-attack-prob 0.3"),
        }
        name, cmd = scenarios[scenario]
        self.run_command(cmd, name)
    
    def run_custom(self):
        """运行自定义配置"""
        defense_map = {
            "all": "no_def rolling window challenge",
            "no_def": "no_def",
            "rolling": "rolling",
            "window": "window",
            "challenge": "challenge"
        }
        modes = defense_map[self.defense_var.get()]
        
        cmd_parts = [
            f"--modes {modes}",
            f"--runs {self.runs_var.get()}",
            f"--num-legit {self.num_legit_var.get()}",
            f"--num-replay {self.num_replay_var.get()}",
            f"--p-loss {self.ploss_var.get()}",
            f"--p-reorder {self.preorder_var.get()}",
            f"--window-size {self.window_size_var.get()}",
            f"--attack-mode {self.attack_mode_var.get()}",
            f"--attacker-loss {self.attacker_loss_var.get()}",
        ]
        
        if self.seed_var.get() != 0:
            cmd_parts.append(f"--seed {self.seed_var.get()}")
        
        cmd = " ".join(cmd_parts)
        self.run_command(cmd, self.t("custom_exp"))
    
    def run_command(self, args, description):
        """执行仿真命令"""
        if self.running:
            messagebox.showwarning("Busy", self.t("busy_msg"))
            return
        
        self.running = True
        self.set_status(True, f"{self.t('status_running')}: {description}")
        self.stop_button.pack(side=tk.RIGHT, padx=(8, 0))
        
        self.output_text.insert(tk.END, f"\n{'='*70}\n▶ EXPERIMENT: {description}\n{'='*70}\n\n")
        self.output_text.see(tk.END)
        
        def run_thread():
            try:
                cmd = f"source .venv/bin/activate && python main.py {args}"

                # Prepare environment to avoid CoreFoundation fork issues on macOS
                env = os.environ.copy()
                env["OBJC_DISABLE_INITIALIZE_FORK_SAFETY"] = "YES"

                self.current_process = subprocess.Popen(
                    cmd,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    executable='/bin/bash',
                    start_new_session=platform.system() != "Windows",
                    env=env
                )
                for line in self.current_process.stdout:
                    if not self.running:
                        break
                    self.output_queue.put(line)
                
                returncode = self.current_process.wait()
                if returncode == 0:
                    self.output_queue.put(f"\n✓ {self.t('done')}\n")
                elif returncode == -15 or returncode == -9:
                    self.output_queue.put(f"\n⚠ Experiment stopped by user\n")
                else:
                    self.output_queue.put(f"\n✗ Process exited with code {returncode}\n")
            except Exception as e:
                self.output_queue.put(f"\n✗ {self.t('error')}: {e}\n")
            finally:
                self.current_process = None
                self.running = False
                self.set_status(False)
                try:
                    self.stop_button.pack_forget()
                except:
                    pass
        
        threading.Thread(target=run_thread, daemon=True).start()
    
    def generate_plots(self):
        """生成图表"""
        if self.running:
            messagebox.showwarning("Busy", self.t("busy_msg"))
            return
        
        if not os.path.exists("results") or not os.listdir("results"):
            messagebox.showwarning("Warning", self.t("no_results"))
            return
        
        self.running = True
        self.set_status(True, self.t("generate_plots"))
        
        def run():
            try:
                # Prepare environment
                env = os.environ.copy()
                env["OBJC_DISABLE_INITIALIZE_FORK_SAFETY"] = "YES"

                result = subprocess.run(
                    "source .venv/bin/activate && python scripts/plot_results.py",
                    shell=True,
                    executable='/bin/bash',
                    capture_output=True,
                    text=True,
                    env=env
                )
                if result.returncode == 0:
                    self.output_queue.put(f"✓ {self.t('generate_plots')} {self.t('done')}\n")
                else:
                    self.output_queue.put(f"✗ Error: {result.stderr}\n")
            except Exception as e:
                self.output_queue.put(f"✗ {self.t('error')}: {e}\n")
            finally:
                self.running = False
                self.set_status(False)
        
        threading.Thread(target=run, daemon=True).start()
    
    def export_tables(self):
        """导出表格"""
        if self.running:
            messagebox.showwarning("Busy", self.t("busy_msg"))
            return
        
        if not os.path.exists("results") or not os.listdir("results"):
            messagebox.showwarning("Warning", self.t("no_results"))
            return
        
        self.running = True
        self.set_status(True, self.t("export_tables"))
        
        def run():
            try:
                result = subprocess.run(
                    "source .venv/bin/activate && python scripts/export_tables.py",
                    shell=True,
                    executable='/bin/bash',
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    self.output_queue.put(f"✓ {self.t('export_tables')} {self.t('done')}\n")
                else:
                    self.output_queue.put(f"✗ Error: {result.stderr}\n")
            except Exception as e:
                self.output_queue.put(f"✗ {self.t('error')}: {e}\n")
            finally:
                self.running = False
                self.set_status(False)
        
        threading.Thread(target=run, daemon=True).start()
    
    def stop_experiment(self):
        """停止当前运行的实验"""
        if not self.running or not self.current_process:
            return
        
        if messagebox.askyesno("Confirm", self.t("confirm_stop")):
            try:
                if platform.system() != "Windows":
                    os.killpg(os.getpgid(self.current_process.pid), signal.SIGTERM)
                else:
                    self.current_process.terminate()
                
                self.running = False
                self.output_queue.put("\n⚠ Stopping experiment...\n")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to stop: {e}")
    
    def save_output(self):
        """保存输出到文件"""
        content = self.output_text.get(1.0, tk.END).strip()
        if not content:
            messagebox.showinfo("Info", "No output to save")
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"simulation_output_{timestamp}.txt"
        
        filepath = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=default_name
        )
        
        if filepath:
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
                messagebox.showinfo("Success", f"{self.t('saved')}\n{filepath}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save: {e}")
    
    def clear_output(self):
        """清空输出"""
        self.output_text.delete(1.0, tk.END)
    
    def set_status(self, is_running, text=None):
        """设置状态"""
        if text:
            self.status_label.config(text=f"● {text}")
        else:
            self.status_label.config(text=f"● {self.t('status_ready')}")
        
        if is_running:
            self.status_label.config(fg=COLORS["warning"])
        else:
            self.status_label.config(fg=COLORS["success"])
    
    def check_output(self):
        """检查输出队列"""
        try:
            while True:
                line = self.output_queue.get_nowait()
                if line.startswith("__JSON_RESULT__:"):
                    # 解析 JSON 数据并更新图表
                    try:
                        json_str = line[len("__JSON_RESULT__:"):]
                        data = json.loads(json_str)
                        self._update_charts(data)
                    except Exception as e:
                        print(f"Chart update failed: {e}")
                else:
                    self.output_text.insert(tk.END, line)
                    self.output_text.see(tk.END)
        except queue.Empty:
            pass
        self.root.after(100, self.check_output)
    
    def _update_charts(self, data):
        """解析结果更新图表"""
        usability_data = []
        security_data = []
        
        for item in data:
            mode_key = item["mode"]
            # 获取模式元数据
            meta = MODE_META.get(mode_key, {})
            # 优先使用翻译
            label = self.t(f"mode_{mode_key}") if f"mode_{mode_key}" in TRANSLATIONS["en"] else mode_key
            color = meta.get("color", COLORS["primary"])
            
            usability_data.append({
                "label": label,
                "value": item["avg_legit_rate"],
                "color": color
            })
            
            security_data.append({
                "label": label,
                "value": item["avg_attack_rate"],
                "color": color
            })
            
        self.usability_chart.update_data(usability_data)
        self.security_chart.update_data(security_data)


def main():
    """入口函数"""
    root = tk.Tk()
    app = SimulationGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
