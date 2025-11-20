#!/usr/bin/env python3
"""
Graphical User Interface for Replay Attack Simulation
学术风格界面 - Academic & Professional Design
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
        "title": "Replay Attack Defense Evaluation",
        "subtitle": "Monte Carlo Simulation Framework",
        "version": "v1.0",
        "tagline": "Statistical analysis of defense mechanisms against replay attacks",
        "scenarios": "Experimental Scenarios",
        "dashboard": "Control Panel",
        "custom_exp": "Custom Configuration",
        "defense_mech": "Defense Mechanisms",
        "all": "All Modes (Comparative Study)",
        "no_def": "No Defense (Baseline)",
        "rolling": "Rolling Counter + MAC",
        "window": "Sliding Window",
        "challenge": "Challenge-Response",
        "runs": "Monte Carlo Runs",
        "num_legit": "Legitimate Transmissions (per run)",
        "num_replay": "Replay Attempts (per run)",
        "p_loss": "Packet Loss Rate (p_loss)",
        "p_reorder": "Reordering Rate (p_reorder)",
        "window_size": "Window Size (for Sliding Window)",
        "attack_mode": "Attack Mode",
        "post_run": "Post-run (replay after legitimate traffic)",
        "inline": "Inline (replay during legitimate traffic)",
        "seed": "Random Seed",
        "attacker_loss": "Attacker Recording Loss Rate",
        "advanced": "Advanced Parameters",
        "start_sim": "▶  Run Simulation",
        "live_output": "Console Output",
        "status_ready": "Ready",
        "status_running": "Running",
        "clear_output": "Clear",
        "generate_plots": "Generate Figures",
        "export_tables": "Export Tables",
        "quick_test": "Quick Test",
        "quick_desc": "Fast validation run (30 iterations)",
        "baseline": "Baseline Comparison",
        "baseline_desc": "Ideal conditions (no loss/reorder)",
        "packet_loss": "Packet Loss Impact",
        "loss_desc": "10% packet loss scenario",
        "reorder": "Reordering Impact",
        "reorder_desc": "30% packet reordering",
        "harsh": "Harsh Network",
        "harsh_desc": "Combined loss + reordering",
        "busy_msg": "A simulation is already running.",
        "done": "COMPLETED",
        "error": "ERROR",
        "language": "Language",
        "params": "Parameters",
        "desc": "Description",
        "stop_sim": "Stop",
        "save_output": "Save Output",
        "confirm_stop": "Are you sure you want to stop the running experiment?",
        "no_results": "No results directory found. Please run experiments first.",
        "saved": "Output saved to",
    },
    "zh": {
        "title": "重放攻击防御评估",
        "subtitle": "蒙特卡洛仿真框架",
        "version": "v1.0 版本",
        "tagline": "基于统计方法的防御机制评估研究",
        "scenarios": "实验场景",
        "dashboard": "控制面板",
        "custom_exp": "自定义配置",
        "defense_mech": "防御机制",
        "all": "全部模式（对比研究）",
        "no_def": "无防御（基线）",
        "rolling": "滚动计数器 + MAC",
        "window": "滑动窗口",
        "challenge": "挑战-响应",
        "runs": "蒙特卡洛运行次数",
        "num_legit": "正规传输次数（每次运行）",
        "num_replay": "重放攻击次数（每次运行）",
        "p_loss": "丢包率 (p_loss)",
        "p_reorder": "乱序率 (p_reorder)",
        "window_size": "窗口大小（滑动窗口）",
        "attack_mode": "攻击模式",
        "post_run": "事后攻击（正规流量后重放）",
        "inline": "内联攻击（正规流量中重放）",
        "seed": "随机种子",
        "attacker_loss": "攻击者记录丢失率",
        "advanced": "高级参数",
        "start_sim": "▶  运行仿真",
        "live_output": "控制台输出",
        "status_ready": "就绪",
        "status_running": "运行中",
        "clear_output": "清空",
        "generate_plots": "生成图表",
        "export_tables": "导出表格",
        "quick_test": "快速测试",
        "quick_desc": "快速验证运行（30次迭代）",
        "baseline": "基线对比",
        "baseline_desc": "理想条件（无丢包/乱序）",
        "packet_loss": "丢包影响",
        "loss_desc": "10% 丢包场景",
        "reorder": "乱序影响",
        "reorder_desc": "30% 数据包乱序",
        "harsh": "恶劣网络",
        "harsh_desc": "丢包 + 乱序组合",
        "busy_msg": "仿真正在运行中。",
        "done": "已完成",
        "error": "错误",
        "language": "语言",
        "params": "参数",
        "desc": "描述",
        "stop_sim": "停止",
        "save_output": "保存输出",
        "confirm_stop": "确定要停止正在运行的实验吗？",
        "no_results": "未找到结果目录。请先运行实验。",
        "saved": "输出已保存到",
    },
    "ja": {
        "title": "リプレイ攻撃防御評価",
        "subtitle": "モンテカルロシミュレーションフレームワーク",
        "version": "v1.0 バージョン",
        "tagline": "統計的手法による防御メカニズムの評価研究",
        "scenarios": "実験シナリオ",
        "dashboard": "コントロールパネル",
        "custom_exp": "カスタム設定",
        "defense_mech": "防御メカニズム",
        "all": "全モード（比較研究）",
        "no_def": "防御なし（ベースライン）",
        "rolling": "ローリングカウンタ + MAC",
        "window": "スライディングウィンドウ",
        "challenge": "チャレンジレスポンス",
        "runs": "モンテカルロ実行回数",
        "num_legit": "正規送信回数（実行ごと）",
        "num_replay": "リプレイ攻撃回数（実行ごと）",
        "p_loss": "パケット損失率 (p_loss)",
        "p_reorder": "並び替え率 (p_reorder)",
        "window_size": "ウィンドウサイズ（スライディング）",
        "attack_mode": "攻撃モード",
        "post_run": "事後攻撃（正規トラフィック後）",
        "inline": "インライン攻撃（正規トラフィック中）",
        "seed": "ランダムシード",
        "attacker_loss": "攻撃者記録損失率",
        "advanced": "詳細設定",
        "start_sim": "▶  シミュレーション実行",
        "live_output": "コンソール出力",
        "status_ready": "準備完了",
        "status_running": "実行中",
        "clear_output": "クリア",
        "generate_plots": "図表生成",
        "export_tables": "テーブル出力",
        "quick_test": "クイックテスト",
        "quick_desc": "高速検証実行（30回反復）",
        "baseline": "ベースライン比較",
        "baseline_desc": "理想条件（損失/並び替えなし）",
        "packet_loss": "パケット損失影響",
        "loss_desc": "10% 損失シナリオ",
        "reorder": "並び替え影響",
        "reorder_desc": "30% パケット並び替え",
        "harsh": "厳しいネットワーク",
        "harsh_desc": "損失 + 並び替え組み合わせ",
        "busy_msg": "シミュレーションは既に実行中です。",
        "done": "完了",
        "error": "エラー",
        "language": "言語",
        "params": "パラメータ",
        "desc": "説明",
        "stop_sim": "停止",
        "save_output": "出力を保存",
        "confirm_stop": "実行中の実験を停止してもよろしいですか？",
        "no_results": "結果ディレクトリが見つかりません。まず実験を実行してください。",
        "saved": "出力を保存しました：",
    }
}

# --- 学术风格配色方案 ---
COLORS = {
    # 主色调：深蓝色学术风格
    "primary": "#1a3a52",           # 深海军蓝
    "primary_light": "#2d5575",     # 浅海军蓝
    "primary_dark": "#0f2537",      # 极深蓝
    
    # 背景色：纸质感
    "bg_main": "#f8f9fa",           # 浅灰白（纸质）
    "bg_card": "#ffffff",           # 纯白（卡片）
    "bg_section": "#f0f2f5",        # 分区背景
    
    # 强调色：学术期刊风格
    "accent": "#d4a574",            # 金褐色（强调）
    "accent_hover": "#c4956a",      # 深金褐
    
    # 状态色：专业配色
    "success": "#3a7d44",           # 深绿
    "warning": "#b8860b",           # 深金黄
    "danger": "#8b3a3a",            # 深红
    "info": "#4a6fa5",              # 信息蓝
    
    # 文字颜色
    "text_primary": "#1a1a1a",      # 主文字（近黑）
    "text_secondary": "#4a5568",    # 次要文字（深灰）
    "text_muted": "#718096",        # 弱化文字（中灰）
    "text_light": "#ffffff",        # 白色文字
    
    # 边框与分割线
    "border": "#d1d5db",            # 边框灰
    "divider": "#e5e7eb",           # 分割线
    "shadow": "#e8eaed",            # 阴影色
    
    # 终端配色
    "terminal_bg": "#1e1e1e",       # 终端背景
    "terminal_text": "#d4d4d4",     # 终端文字
}

# --- 学术风格字体配置 ---
if platform.system() == "Darwin":  # macOS
    FONTS = {
        "title": ("Georgia", 28, "bold"),           # 衬线字体 - 标题
        "subtitle": ("Georgia", 14),                # 衬线字体 - 副标题
        "h1": ("Helvetica Neue", 20, "bold"),       # 无衬线 - 一级标题
        "h2": ("Helvetica Neue", 16, "bold"),       # 二级标题
        "h3": ("Helvetica Neue", 13, "bold"),       # 三级标题
        "body": ("Helvetica Neue", 12),             # 正文
        "small": ("Helvetica Neue", 11),            # 小字
        "mono": ("Menlo", 11),                      # 等宽字体
        "button": ("Helvetica Neue", 13, "bold"),   # 按钮
    }
else:
    FONTS = {
        "title": ("Georgia", 24, "bold"),
        "subtitle": ("Georgia", 12),
        "h1": ("Segoe UI", 18, "bold"),
        "h2": ("Segoe UI", 14, "bold"),
        "h3": ("Segoe UI", 11, "bold"),
        "body": ("Segoe UI", 10),
        "small": ("Segoe UI", 9),
        "mono": ("Consolas", 10),
        "button": ("Segoe UI", 11, "bold"),
    }

class AcademicButton(tk.Frame):
    """学术风格按钮"""
    def __init__(self, parent, text, command, style="primary", **kwargs):
        colors = {
            "primary": (COLORS["primary"], COLORS["primary_light"]),
            "accent": (COLORS["accent"], COLORS["accent_hover"]),
            "secondary": (COLORS["text_secondary"], COLORS["text_primary"]),
        }
        self.color, self.hover_color = colors.get(style, colors["primary"])
        
        super().__init__(parent, bg=self.color, cursor="hand2", bd=1, relief=tk.FLAT, **kwargs)
        self.command = command
        self.pack_propagate(False)
        
        self.label = tk.Label(
            self,
            text=text,
            bg=self.color,
            fg=COLORS["text_light"],
            font=FONTS["button"],
            cursor="hand2"
        )
        self.label.place(relx=0.5, rely=0.5, anchor="center")
        
        for widget in [self, self.label]:
            widget.bind("<Enter>", lambda e: self._on_enter())
            widget.bind("<Leave>", lambda e: self._on_leave())
            widget.bind("<Button-1>", lambda e: self._on_click())
    
    def _on_enter(self):
        self.configure(bg=self.hover_color)
        self.label.configure(bg=self.hover_color)
    
    def _on_leave(self):
        self.configure(bg=self.color)
        self.label.configure(bg=self.color)
    
    def _on_click(self):
        if self.command:
            self.command()

class SectionCard(tk.Frame):
    """学术论文风格的章节卡片"""
    def __init__(self, parent, title=None, subtitle=None, **kwargs):
        super().__init__(parent, bg=COLORS["bg_card"], bd=1, relief=tk.SOLID, highlightbackground=COLORS["border"], highlightthickness=1, **kwargs)
        self.pack_propagate(False)
        
        if title:
            header = tk.Frame(self, bg=COLORS["bg_card"], pady=18, padx=20)
            header.pack(fill=tk.X)
            
            tk.Label(
                header,
                text=title,
                font=FONTS["h2"],
                fg=COLORS["text_primary"],
                bg=COLORS["bg_card"]
            ).pack(anchor="w")
            
            if subtitle:
                tk.Label(
                    header,
                    text=subtitle,
                    font=FONTS["small"],
                    fg=COLORS["text_muted"],
                    bg=COLORS["bg_card"]
                ).pack(anchor="w", pady=(4, 0))
            
            # 分割线
            tk.Frame(self, bg=COLORS["divider"], height=1).pack(fill=tk.X)
        
        # 内容区域
        self.content = tk.Frame(self, bg=COLORS["bg_card"], padx=20, pady=18)
        self.content.pack(fill=tk.BOTH, expand=True)

class SimulationGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Replay Attack Defense Evaluation System")
        self.root.geometry("1400x900")
        self.root.configure(bg=COLORS["bg_main"])
        
        self.current_lang = tk.StringVar(value="en")
        self.output_queue = queue.Queue()
        self.running = False
        self.current_process = None  # 跟踪当前运行的进程
        
        self.setup_style()
        self.create_widgets()
        self.check_output()
    
    def t(self, key):
        """获取翻译"""
        return TRANSLATIONS[self.current_lang.get()].get(key, key)
    
    def setup_style(self):
        """配置样式"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # 单选按钮样式
        style.configure("Academic.TRadiobutton",
                       background=COLORS["bg_card"],
                       foreground=COLORS["text_primary"],
                       font=FONTS["body"],
                       borderwidth=0)
        style.map("Academic.TRadiobutton",
                 background=[('active', COLORS["bg_card"])],
                 foreground=[('active', COLORS["primary"])])
        
        # 滑动条样式
        style.configure("Academic.Horizontal.TScale",
                       background=COLORS["bg_card"],
                       troughcolor=COLORS["bg_section"],
                       borderwidth=0,
                       lightcolor=COLORS["accent"],
                       darkcolor=COLORS["accent"])
    
    def create_widgets(self):
        """创建主界面"""
        
        # === 顶部标题区（学术论文风格）===
        header = tk.Frame(self.root, bg=COLORS["primary"], height=160)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        header_content = tk.Frame(header, bg=COLORS["primary"])
        header_content.place(relx=0.5, rely=0.5, anchor="center")
        
        tk.Label(
            header_content,
            text=self.t("title"),
            font=FONTS["title"],
            fg=COLORS["text_light"],
            bg=COLORS["primary"]
        ).pack()
        
        tk.Label(
            header_content,
            text=self.t("subtitle"),
            font=FONTS["subtitle"],
            fg=COLORS["accent"],
            bg=COLORS["primary"]
        ).pack(pady=(8, 4))
        
        tk.Label(
            header_content,
            text=self.t("tagline"),
            font=FONTS["small"],
            fg=COLORS["text_light"],
            bg=COLORS["primary"]
        ).pack()
        
        # 语言切换器（右上角）
        lang_frame = tk.Frame(header, bg=COLORS["primary"])
        lang_frame.place(relx=0.95, rely=0.5, anchor="e")
        
        tk.Label(
            lang_frame,
            text=self.t("language"),
            font=FONTS["small"],
            fg=COLORS["text_light"],
            bg=COLORS["primary"]
        ).pack(side=tk.LEFT, padx=(0, 8))
        
        for code, name in [("en", "EN"), ("zh", "中"), ("ja", "日")]:
            is_active = self.current_lang.get() == code
            btn = tk.Label(
                lang_frame,
                text=name,
                font=FONTS["small"],
                fg=COLORS["accent"] if is_active else COLORS["text_light"],
                bg=COLORS["primary"],
                cursor="hand2",
                padx=8,
                pady=4
            )
            btn.pack(side=tk.LEFT, padx=2)
            if not is_active:
                btn.bind("<Button-1>", lambda e, lc=code: self.switch_language(lc))
        
        # === 主内容区 ===
        main = tk.Frame(self.root, bg=COLORS["bg_main"])
        main.pack(fill=tk.BOTH, expand=True, padx=30, pady=25)
        
        # 左侧：实验场景 + 配置
        left = tk.Frame(main, bg=COLORS["bg_main"], width=480)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 15))
        left.pack_propagate(False)
        
        # 右侧：输出
        right = tk.Frame(main, bg=COLORS["bg_main"])
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.create_scenario_panel(left)
        self.create_config_panel(left)
        self.create_output_panel(right)
    
    def create_scenario_panel(self, parent):
        """实验场景面板"""
        card = SectionCard(parent, title=self.t("scenarios"))
        card.pack(fill=tk.X, pady=(0, 15))
        
        scenarios = [
            ("quick_test", "quick_desc", "quick", COLORS["info"]),
            ("baseline", "baseline_desc", "baseline", COLORS["primary"]),
            ("packet_loss", "loss_desc", "packet_loss", COLORS["warning"]),
            ("reorder", "reorder_desc", "reorder", COLORS["info"]),
            ("harsh", "harsh_desc", "harsh", COLORS["danger"]),
        ]
        
        for title_key, desc_key, cmd, color in scenarios:
            scenario_frame = tk.Frame(
                card.content,
                bg=COLORS["bg_section"],
                cursor="hand2",
                bd=1,
                relief=tk.SOLID,
                highlightbackground=COLORS["border"],
                highlightthickness=0
            )
            scenario_frame.pack(fill=tk.X, pady=6)
            
            # 左侧色条
            tk.Frame(scenario_frame, bg=color, width=4).pack(side=tk.LEFT, fill=tk.Y)
            
            # 内容区
            content = tk.Frame(scenario_frame, bg=COLORS["bg_section"], padx=14, pady=12)
            content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            
            tk.Label(
                content,
                text=self.t(title_key),
                font=FONTS["h3"],
                fg=COLORS["text_primary"],
                bg=COLORS["bg_section"],
                anchor="w"
            ).pack(fill=tk.X)
            
            tk.Label(
                content,
                text=self.t(desc_key),
                font=FONTS["small"],
                fg=COLORS["text_muted"],
                bg=COLORS["bg_section"],
                anchor="w"
            ).pack(fill=tk.X, pady=(4, 0))
            
            # 绑定点击
            for widget in [scenario_frame, content]:
                widget.bind("<Button-1>", lambda e, s=cmd: self.run_scenario(s))
        
        # 底部工具按钮
        tool_frame = tk.Frame(card.content, bg=COLORS["bg_card"], pady=10)
        tool_frame.pack(fill=tk.X)
        
        AcademicButton(
            tool_frame,
            text=self.t("generate_plots"),
            command=self.generate_plots,
            style="secondary",
            height=40
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        AcademicButton(
            tool_frame,
            text=self.t("export_tables"),
            command=self.export_tables,
            style="secondary",
            height=40
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
    
    def create_config_panel(self, parent):
        """配置面板"""
        card = SectionCard(parent, title=self.t("custom_exp"))
        card.pack(fill=tk.BOTH, expand=True)
        
        # 创建Canvas和Scrollbar用于滚动
        canvas = tk.Canvas(card.content, bg=COLORS["bg_card"], highlightthickness=0)
        scrollbar = tk.Scrollbar(card.content, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=COLORS["bg_card"])
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # 鼠标滚轮支持
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)  # Windows/macOS
        canvas.bind_all("<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))  # Linux
        canvas.bind_all("<Button-5>", lambda e: canvas.yview_scroll(1, "units"))   # Linux
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # 防御机制
        tk.Label(
            scrollable_frame,
            text=self.t("defense_mech"),
            font=FONTS["h3"],
            fg=COLORS["text_primary"],
            bg=COLORS["bg_card"]
        ).pack(anchor="w", pady=(0, 10))
        
        self.defense_var = tk.StringVar(value="all")
        
        for key in ["all", "no_def", "rolling", "window", "challenge"]:
            ttk.Radiobutton(
                scrollable_frame,
                text=self.t(key),
                variable=self.defense_var,
                value=key,
                style="Academic.TRadiobutton"
            ).pack(anchor="w", pady=4)
        
        # 分割线
        tk.Frame(scrollable_frame, bg=COLORS["divider"], height=1).pack(fill=tk.X, pady=18)
        
        # 攻击模式
        tk.Label(
            scrollable_frame,
            text=self.t("attack_mode"),
            font=FONTS["h3"],
            fg=COLORS["text_primary"],
            bg=COLORS["bg_card"]
        ).pack(anchor="w", pady=(0, 10))
        
        self.attack_mode_var = tk.StringVar(value="post")
        
        for key, value in [("post_run", "post"), ("inline", "inline")]:
            ttk.Radiobutton(
                scrollable_frame,
                text=self.t(key),
                variable=self.attack_mode_var,
                value=value,
                style="Academic.TRadiobutton"
            ).pack(anchor="w", pady=4)
        
        # 分割线
        tk.Frame(scrollable_frame, bg=COLORS["divider"], height=1).pack(fill=tk.X, pady=18)
        
        # 参数配置
        tk.Label(
            scrollable_frame,
            text=self.t("params"),
            font=FONTS["h3"],
            fg=COLORS["text_primary"],
            bg=COLORS["bg_card"]
        ).pack(anchor="w", pady=(0, 10))
        
        self.runs_var = tk.IntVar(value=100)
        self.num_legit_var = tk.IntVar(value=20)
        self.num_replay_var = tk.IntVar(value=100)
        self.ploss_var = tk.DoubleVar(value=0.0)
        self.preorder_var = tk.DoubleVar(value=0.0)
        self.window_size_var = tk.IntVar(value=5)
        self.seed_var = tk.IntVar(value=0)
        self.attacker_loss_var = tk.DoubleVar(value=0.0)
        
        self.create_slider(scrollable_frame, "runs", self.runs_var, 10, 500, False)
        self.create_slider(scrollable_frame, "num_legit", self.num_legit_var, 5, 100, False)
        self.create_slider(scrollable_frame, "num_replay", self.num_replay_var, 10, 500, False)
        self.create_slider(scrollable_frame, "p_loss", self.ploss_var, 0.0, 0.5, True)
        self.create_slider(scrollable_frame, "p_reorder", self.preorder_var, 0.0, 0.5, True)
        self.create_slider(scrollable_frame, "window_size", self.window_size_var, 1, 20, False)
        
        # 高级参数分割线
        tk.Frame(scrollable_frame, bg=COLORS["divider"], height=1).pack(fill=tk.X, pady=18)
        tk.Label(
            scrollable_frame,
            text=self.t("advanced"),
            font=FONTS["h3"],
            fg=COLORS["text_secondary"],
            bg=COLORS["bg_card"]
        ).pack(anchor="w", pady=(0, 10))
        
        self.create_slider(scrollable_frame, "seed", self.seed_var, 0, 9999, False)
        self.create_slider(scrollable_frame, "attacker_loss", self.attacker_loss_var, 0.0, 0.5, True)
        
        # 运行按钮
        tk.Frame(scrollable_frame, bg=COLORS["bg_card"], height=15).pack()
        
        AcademicButton(
            scrollable_frame,
            text=self.t("start_sim"),
            command=self.run_custom,
            style="accent",
            height=50
        ).pack(fill=tk.X, padx=5)
    
    def create_slider(self, parent, label_key, variable, min_val, max_val, is_float):
        """创建滑动条"""
        frame = tk.Frame(parent, bg=COLORS["bg_card"], pady=10)
        frame.pack(fill=tk.X)
        
        header = tk.Frame(frame, bg=COLORS["bg_card"])
        header.pack(fill=tk.X, pady=(0, 6))
        
        tk.Label(
            header,
            text=self.t(label_key),
            font=FONTS["body"],
            fg=COLORS["text_secondary"],
            bg=COLORS["bg_card"]
        ).pack(side=tk.LEFT)
        
        value_label = tk.Label(
            header,
            font=FONTS["h2"],  # 增大字体从h3到h2
            fg=COLORS["primary"],  # 改为深蓝色，更清晰
            bg=COLORS["bg_card"]
        )
        value_label.pack(side=tk.RIGHT, padx=10)  # 增加左边距
        
        def update(*args):
            val = variable.get()
            text = f"{val:.2f}" if is_float else f"{int(val)}"
            
            # 为窗口大小添加建议提示
            if label_key == "window_size":
                ival = int(val)
                if ival < 3:
                    text += " ⚠"  # 太小
                elif 3 <= ival <= 7:
                    text += " ✓"  # 推荐范围
                elif ival > 10:
                    text += " ⚠"  # 太大
            
            # 为随机种子添加提示
            elif label_key == "seed":
                ival = int(val)
                if ival == 0:
                    text += " 🎲"  # 随机
                else:
                    text += " 🔒"  # 固定
            
            value_label.config(text=text)
        
        variable.trace_add("write", update)
        update()
        
        ttk.Scale(
            frame,
            from_=min_val,
            to=max_val,
            variable=variable,
            orient="horizontal",
            style="Academic.Horizontal.TScale"
        ).pack(fill=tk.X)
        
        # 为窗口大小添加说明文本
        if label_key == "window_size":
            hint_text = {
                "en": "Recommended: 3-7 (balance security & usability)",
                "zh": "推荐值：3-7（平衡安全性与可用性）",
                "ja": "推奨値：3-7（セキュリティと使いやすさのバランス）"
            }
            tk.Label(
                frame,
                text=hint_text[self.current_lang.get()],
                font=FONTS["small"],
                fg=COLORS["text_muted"],
                bg=COLORS["bg_card"]
            ).pack(anchor="w", pady=(2, 0))
        
        # 为随机种子添加说明文本
        elif label_key == "seed":
            hint_text = {
                "en": "0=Random | Non-zero=Reproducible (e.g., 42 always gives same result)",
                "zh": "0=随机 | 非0=可重现（如42每次结果相同）",
                "ja": "0=ランダム | 非0=再現可能（例:42は毎回同じ結果）"
            }
            tk.Label(
                frame,
                text=hint_text[self.current_lang.get()],
                font=FONTS["small"],
                fg=COLORS["text_muted"],
                bg=COLORS["bg_card"]
            ).pack(anchor="w", pady=(2, 0))
    
    def create_output_panel(self, parent):
        """输出面板"""
        card = SectionCard(parent, title=self.t("live_output"))
        card.pack(fill=tk.BOTH, expand=True)
        
        # 终端输出
        terminal_frame = tk.Frame(card.content, bg=COLORS["terminal_bg"], bd=0)
        terminal_frame.pack(fill=tk.BOTH, expand=True)
        
        self.output_text = scrolledtext.ScrolledText(
            terminal_frame,
            wrap=tk.WORD,
            font=FONTS["mono"],
            bg=COLORS["terminal_bg"],
            fg=COLORS["terminal_text"],
            insertbackground=COLORS["accent"],
            padx=15,
            pady=15,
            borderwidth=0,
            highlightthickness=0
        )
        self.output_text.pack(fill=tk.BOTH, expand=True)
        
        # 底部工具栏
        toolbar = tk.Frame(card.content, bg=COLORS["bg_card"], pady=12)
        toolbar.pack(fill=tk.X)
        
        self.status_label = tk.Label(
            toolbar,
            text=f"● {self.t('status_ready')}",
            font=FONTS["body"],
            fg=COLORS["success"],
            bg=COLORS["bg_card"]
        )
        self.status_label.pack(side=tk.LEFT)
        
        # 停止按钮（初始隐藏）
        self.stop_button = AcademicButton(
            toolbar,
            text=self.t("stop_sim"),
            command=self.stop_experiment,
            style="secondary",
            height=32,
            width=80
        )
        
        # 保存输出按钮
        AcademicButton(
            toolbar,
            text=self.t("save_output"),
            command=self.save_output,
            style="secondary",
            height=32,
            width=120
        ).pack(side=tk.RIGHT, padx=(0, 5))
        
        AcademicButton(
            toolbar,
            text=self.t("clear_output"),
            command=self.clear_output,
            style="secondary",
            height=32,
            width=100
        ).pack(side=tk.RIGHT, padx=(0, 5))
    
    def switch_language(self, lang_code):
        """切换语言"""
        self.current_lang.set(lang_code)
        for widget in self.root.winfo_children():
            widget.destroy()
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
        defense_map = {
            "all": "no_def rolling window challenge",
            "no_def": "no_def",
            "rolling": "rolling",
            "window": "window",
            "challenge": "challenge"
        }
        modes = defense_map[self.defense_var.get()]
        
        # 构建命令
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
        
        # 只在非0时添加seed参数
        if self.seed_var.get() != 0:
            cmd_parts.append(f"--seed {self.seed_var.get()}")
        
        cmd = " ".join(cmd_parts)
        self.run_command(cmd, self.t("custom_exp"))
    
    def run_command(self, args, description):
        if self.running:
            messagebox.showwarning("Busy", self.t("busy_msg"))
            return
        
        self.running = True
        self.set_status(True, f"{self.t('status_running')}: {description}")
        self.stop_button.pack(side=tk.RIGHT, padx=(0, 5))  # 显示停止按钮
        
        self.output_text.insert(tk.END, f"\n{'='*70}\n▶ EXPERIMENT: {description}\n{'='*70}\n\n")
        self.output_text.see(tk.END)
        
        def run_thread():
            try:
                cmd = f"source .venv/bin/activate && python main.py {args}"
                self.current_process = subprocess.Popen(
                    cmd,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    executable='/bin/bash',
                    preexec_fn=None if platform.system() == "Windows" else lambda: None
                )
                for line in self.current_process.stdout:
                    if not self.running:  # 检查是否被停止
                        break
                    self.output_queue.put(line)
                
                returncode = self.current_process.wait()
                if returncode == 0:
                    self.output_queue.put(f"\n✓ {self.t('done')}\n")
                elif returncode == -15 or returncode == -9:  # SIGTERM or SIGKILL
                    self.output_queue.put(f"\n⚠ Experiment stopped by user\n")
                else:
                    self.output_queue.put(f"\n✗ Process exited with code {returncode}\n")
            except Exception as e:
                self.output_queue.put(f"\n✗ {self.t('error')}: {e}\n")
            finally:
                self.current_process = None
                self.running = False
                self.set_status(False)
                self.stop_button.pack_forget()  # 隐藏停止按钮
        
        threading.Thread(target=run_thread, daemon=True).start()
    
    def generate_plots(self):
        if self.running:
            messagebox.showwarning("Busy", self.t("busy_msg"))
            return
        
        # 检查results目录是否存在
        import os
        if not os.path.exists("results") or not os.listdir("results"):
            messagebox.showwarning("Warning", self.t("no_results"))
            return
        
        self.running = True
        self.set_status(True, self.t("generate_plots"))
        
        def run():
            try:
                result = subprocess.run(
                    "source .venv/bin/activate && python scripts/plot_results.py",
                    shell=True,
                    executable='/bin/bash',
                    capture_output=True,
                    text=True
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
        if self.running:
            messagebox.showwarning("Busy", self.t("busy_msg"))
            return
        
        # 检查results目录是否存在
        import os
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
                import signal
                import os
                if platform.system() != "Windows":
                    # Unix系统：发送SIGTERM信号给整个进程组
                    os.killpg(os.getpgid(self.current_process.pid), signal.SIGTERM)
                else:
                    # Windows系统：终止进程
                    self.current_process.terminate()
                
                self.running = False
                self.output_queue.put("\n⚠ Stopping experiment...\n")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to stop: {e}")
    
    def save_output(self):
        """保存输出到文件"""
        from tkinter import filedialog
        from datetime import datetime
        
        content = self.output_text.get(1.0, tk.END).strip()
        if not content:
            messagebox.showinfo("Info", "No output to save")
            return
        
        # 生成默认文件名
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
