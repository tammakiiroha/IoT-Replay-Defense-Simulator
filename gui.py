#!/usr/bin/env python3
"""GUI for Replay Attack Simulation with academic aesthetics and tri-lingual UI."""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import subprocess
import threading
import queue
import platform

# --- 多语言文本配置 ---
TRANSLATIONS = {
    "en": {
        "title": "Replay Attack Simulation Toolkit",
        "subtitle": "Defense Evaluation System",
        "version": "Version",
        "hero_desc": "Academic-grade console for replay attack defense research.",
        "hero_badge_precision": "Statistical rigor",
        "hero_badge_plots": "Publication-ready figures",
        "hero_badge_demo": "Live demo friendly",
        "hero_stat_runs": "Default Monte Carlo runs",
        "hero_stat_loss": "Packet-loss sweep",
        "hero_stat_reorder": "Reorder sweep",
        "scenarios": "QUICK SCENARIOS",
        "dashboard": "Dashboard / Control Panel",
        "custom_exp": "Custom Experiment",
        "defense_mech": "Defense Mechanisms",
        "dashboard_hint": "Tune parameters to reproduce thesis-grade experiments with comparable rigor.",
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
        "hero_desc": "面向毕业论文的学术级重放攻击防御仿真平台。",
        "hero_badge_precision": "统计结果可信",
        "hero_badge_plots": "论文级图表",
        "hero_badge_demo": "现场演示友好",
        "hero_stat_runs": "默认蒙特卡洛次数",
        "hero_stat_loss": "丢包率扫描",
        "hero_stat_reorder": "乱序率扫描",
        "scenarios": "快速场景",
        "dashboard": "仪表盘 / 控制面板",
        "custom_exp": "自定义实验",
        "defense_mech": "防御机制",
        "dashboard_hint": "调节参数以复现毕业论文级别的实验与严谨度。",
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
        "hero_desc": "卒業研究向けの学術的なリプレイ攻撃防御コンソール。",
        "hero_badge_precision": "統計的な厳密性",
        "hero_badge_plots": "論文品質の図表",
        "hero_badge_demo": "デモに最適",
        "hero_stat_runs": "標準モンテカルロ回数",
        "hero_stat_loss": "損失率スイープ",
        "hero_stat_reorder": "並び替え率スイープ",
        "scenarios": "クイックシナリオ",
        "dashboard": "ダッシュボード / コントロールパネル",
        "custom_exp": "カスタム実験",
        "defense_mech": "防御メカニズム",
        "dashboard_hint": "卒業論文レベルの再現実験が行えるようにパラメータを調整してください。",
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

# --- 色彩与字体配置 ---
COLORS = {
    "bg_dark": "#131c2e",
    "bg_medium": "#1f2c45",
    "bg_light": "#f3f4f6",
    "hero_bg": "#e8ecf6",
    "card_bg": "#ffffff",
    "card_border": "#d5dae6",
    "accent": "#2b4c7e",
    "accent_hover": "#1f3658",
    "success": "#3c7a6b",
    "success_hover": "#2f5c50",
    "warning": "#b3752a",
    "danger": "#8e2f3f",
    "purple": "#5c4a72",
    "text_light": "#ffffff",
    "text_dark": "#1f2c45",
    "text_muted": "#6d768a",
    "badge_bg": "#fdfdfd",
    "shadow": "#d6dae5"
}

SCENARIO_ACCENTS = {
    "quick": "#2b4c7e",
    "baseline": "#445a86",
    "packet_loss": "#8c6a43",
    "reorder": "#5f4e73",
    "harsh": "#7c3642",
}

if platform.system() == "Darwin":  # macOS
    FONTS = {
        "hero": ("SF Pro Display", 30, "bold"),
        "h1": ("SF Pro Display", 24, "bold"),
        "h2": ("SF Pro Display", 18, "bold"),
        "h3": ("SF Pro Display", 14, "bold"),
        "body": ("SF Pro Text", 13),
        "small": ("SF Pro Text", 11),
        "mono": ("SF Mono", 11),
    }
else:
    FONTS = {
        "hero": ("Segoe UI", 24, "bold"),
        "h1": ("Segoe UI", 22, "bold"),
        "h2": ("Segoe UI", 16, "bold"),
        "h3": ("Segoe UI", 12, "bold"),
        "body": ("Segoe UI", 11),
        "small": ("Segoe UI", 9),
        "mono": ("Consolas", 10),
    }


class ModernButton(tk.Frame):
    def __init__(self, parent, text, command, color=COLORS["accent"], hover_color=COLORS["accent_hover"], **kwargs):
        super().__init__(parent, bg=color, cursor="hand2", highlightthickness=1, highlightbackground=COLORS["card_border"], bd=0, **kwargs)
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

        for widget in (self, self.label):
            widget.bind("<Enter>", self.on_enter)
            widget.bind("<Leave>", self.on_leave)
            widget.bind("<Button-1>", self.on_click)

    def on_enter(self, _):
        self.configure(bg=self.hover_color)
        self.label.configure(bg=self.hover_color)

    def on_leave(self, _):
        self.configure(bg=self.color)
        self.label.configure(bg=self.color)

    def on_click(self, _):
        if self.command:
            self.command()


class CardFrame(tk.Frame):
    def __init__(self, parent, title, **kwargs):
        container = tk.Frame(parent, bg=COLORS["bg_light"])
        container.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        super().__init__(
            container,
            bg=COLORS["card_bg"],
            padx=22,
            pady=22,
            highlightthickness=1,
            highlightbackground=COLORS["card_border"],
            **kwargs,
        )
        self.pack(fill=tk.BOTH, expand=True)

        if title:
            title_label = tk.Label(self, text=title, font=FONTS["h2"], fg=COLORS["text_dark"], bg=COLORS["card_bg"])
            title_label.pack(anchor="w")
            tk.Frame(self, bg=COLORS["accent"], height=2, width=70).pack(anchor="w", pady=(6, 16))


class SimulationGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Replay Attack Simulation Toolkit")
        self.root.geometry("1340x900")
        self.root.configure(bg=COLORS["bg_light"])

        self.current_lang = tk.StringVar(value="en")
        self.output_queue = queue.Queue()
        self.running = False

        self.setup_style()
        self.create_widgets()
        self.check_output()

    def t(self, key):
        return TRANSLATIONS[self.current_lang.get()].get(key, key)

    def setup_style(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".", background=COLORS["bg_light"])
        style.configure(
            "TRadiobutton",
            background=COLORS["card_bg"],
            font=FONTS["body"],
            foreground=COLORS["text_dark"],
        )
        style.configure("TSeparator", background=COLORS["card_border"])
        style.configure(
            "Horizontal.TScale",
            background=COLORS["card_bg"],
            troughcolor="#e1e5f0",
            thickness=6,
            troughrelief="flat",
        )

    def create_widgets(self):
        self.root.configure(bg=COLORS["bg_light"])
        self.create_topbar()
        self.create_hero_section()
        self.create_main_section()

    def create_topbar(self):
        topbar = tk.Frame(self.root, bg=COLORS["bg_dark"], height=70)
        topbar.pack(fill=tk.X)
        topbar.pack_propagate(False)

        logo = tk.Frame(topbar, bg=COLORS["bg_dark"])
        logo.pack(side=tk.LEFT, padx=30)
        tk.Label(
            logo,
            text="REPLAY SIMULATION",
            font=FONTS["h1"],
            fg="white",
            bg=COLORS["bg_dark"],
        ).pack(anchor="w")
        tk.Label(
            logo,
            text=self.t("subtitle"),
            font=FONTS["small"],
            fg="#a7b3d1",
            bg=COLORS["bg_dark"],
        ).pack(anchor="w")

        lang_frame = tk.Frame(topbar, bg=COLORS["bg_dark"])
        lang_frame.pack(side=tk.RIGHT, padx=30)
        tk.Label(
            lang_frame,
            text=self.t("language") + ":",
            font=FONTS["small"],
            bg=COLORS["bg_dark"],
            fg="#a7b3d1",
        ).pack(side=tk.LEFT, padx=(0, 10))

        for code, name in [("en", "English"), ("zh", "中文"), ("ja", "日本語")]:
            btn = tk.Button(
                lang_frame,
                text=name,
                font=FONTS["small"],
                bg=COLORS["bg_medium"] if self.current_lang.get() == code else COLORS["bg_dark"],
                fg="white",
                activebackground=COLORS["bg_medium"],
                activeforeground="white",
                relief=tk.FLAT,
                padx=16,
                pady=6,
                cursor="hand2",
                command=lambda lc=code: self.switch_language(lc),
            )
            btn.pack(side=tk.LEFT, padx=3)

    def create_hero_section(self):
        hero = tk.Frame(self.root, bg=COLORS["hero_bg"], padx=30, pady=26)
        hero.pack(fill=tk.X, padx=20, pady=(16, 12))

        left = tk.Frame(hero, bg=COLORS["hero_bg"])
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tk.Label(left, text=self.t("title"), font=FONTS["hero"], fg=COLORS["text_dark"], bg=COLORS["hero_bg"]).pack(anchor="w")
        tk.Label(left, text=self.t("hero_desc"), font=FONTS["body"], fg=COLORS["text_muted"], bg=COLORS["hero_bg"], wraplength=520, justify="left").pack(anchor="w", pady=(6, 12))

        stats_frame = tk.Frame(left, bg=COLORS["hero_bg"])
        stats_frame.pack(anchor="w")
        stats = [
            (self.t("hero_stat_runs"), "50"),
            (self.t("hero_stat_loss"), "0.0 - 0.5"),
            (self.t("hero_stat_reorder"), "0.0 - 0.5"),
        ]
        for label, value in stats:
            card = tk.Frame(stats_frame, bg=COLORS["card_bg"], padx=14, pady=10, highlightthickness=1, highlightbackground=COLORS["card_border"])
            card.pack(side=tk.LEFT, padx=6)
            tk.Label(card, text=label, font=FONTS["small"], fg=COLORS["text_muted"], bg=COLORS["card_bg"]).pack(anchor="w")
            tk.Label(card, text=value, font=FONTS["h3"], fg=COLORS["accent"], bg=COLORS["card_bg"]).pack(anchor="w")

        right = tk.Frame(hero, bg=COLORS["hero_bg"])
        right.pack(side=tk.RIGHT, padx=20)
        badges = [
            self.t("hero_badge_precision"),
            self.t("hero_badge_plots"),
            self.t("hero_badge_demo"),
        ]
        for text in badges:
            badge = tk.Frame(right, bg=COLORS["badge_bg"], padx=18, pady=10, highlightthickness=1, highlightbackground=COLORS["card_border"])
            badge.pack(fill=tk.X, pady=6)
            tk.Label(badge, text=text, font=FONTS["body"], fg=COLORS["text_dark"], bg=COLORS["badge_bg"]).pack(anchor="w")

    def create_main_section(self):
        main_container = tk.Frame(self.root, bg=COLORS["bg_light"])
        main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        left_panel = tk.Frame(main_container, bg=COLORS["bg_light"], width=320)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 12))
        left_panel.pack_propagate(False)

        middle_panel = tk.Frame(main_container, bg=COLORS["bg_light"])
        middle_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=12)

        right_panel = tk.Frame(main_container, bg=COLORS["bg_light"])
        right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.create_scenario_panel(left_panel)
        self.create_config_panel(middle_panel)
        self.create_output_panel(right_panel)

    def create_scenario_panel(self, parent):
        card = CardFrame(parent, self.t("scenarios"))
        for key, desc_key, slug in [
            ("quick_test", "quick_desc", "quick"),
            ("baseline", "baseline_desc", "baseline"),
            ("packet_loss", "loss_desc", "packet_loss"),
            ("reorder", "reorder_desc", "reorder"),
            ("harsh", "harsh_desc", "harsh"),
        ]:
            accent = SCENARIO_ACCENTS[slug]
            scenario = tk.Frame(card, bg=COLORS["card_bg"], highlightthickness=1, highlightbackground=accent, height=78, cursor="hand2")
            scenario.pack(fill=tk.X, pady=6)
            scenario.pack_propagate(False)

            bar = tk.Frame(scenario, bg=accent, width=5)
            bar.pack(side=tk.LEFT, fill=tk.Y)

            text_area = tk.Frame(scenario, bg=COLORS["card_bg"], padx=16, pady=12)
            text_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            tk.Label(text_area, text=self.t(key), font=FONTS["h3"], fg=COLORS["text_dark"], bg=COLORS["card_bg"], anchor="w").pack(fill=tk.X)
            tk.Label(text_area, text=self.t(desc_key), font=FONTS["small"], fg=COLORS["text_muted"], bg=COLORS["card_bg"], anchor="w").pack(fill=tk.X, pady=(4, 0))

            for widget in (scenario, text_area, bar):
                widget.bind("<Button-1>", lambda _, s=slug: self.run_scenario(s))

        tk.Frame(card, bg=COLORS["card_bg"], height=16).pack()
        ModernButton(card, text=self.t("generate_plots"), command=self.generate_plots, height=46).pack(fill=tk.X, pady=4)
        ModernButton(card, text=self.t("export_tables"), command=self.export_tables, height=46).pack(fill=tk.X, pady=4)

    def create_config_panel(self, parent):
        card = CardFrame(parent, self.t("custom_exp"))
        tk.Label(card, text=self.t("dashboard_hint"), font=FONTS["body"], fg=COLORS["text_muted"], bg=COLORS["card_bg"], wraplength=520, justify="left").pack(anchor="w", pady=(0, 18))

        tk.Label(card, text=self.t("defense_mech"), font=FONTS["h3"], bg=COLORS["card_bg"], fg=COLORS["text_dark"]).pack(anchor="w", pady=(0, 6))
        self.defense_var = tk.StringVar(value="all")
        defense_frame = tk.Frame(card, bg=COLORS["card_bg"])
        defense_frame.pack(fill=tk.X, pady=(0, 16))
        for key in ["all", "no_def", "rolling", "window", "challenge"]:
            ttk.Radiobutton(defense_frame, text=self.t(key), variable=self.defense_var, value=key).pack(anchor="w", pady=2)

        self.runs_var = tk.IntVar(value=50)
        self.ploss_var = tk.DoubleVar(value=0.0)
        self.preorder_var = tk.DoubleVar(value=0.0)
        self.create_slider(card, "runs", self.runs_var, 10, 200, False)
        self.create_slider(card, "p_loss", self.ploss_var, 0.0, 0.5, True)
        self.create_slider(card, "p_reorder", self.preorder_var, 0.0, 0.5, True)

        tk.Frame(card, bg=COLORS["card_bg"], height=12).pack()
        ModernButton(card, text=self.t("start_sim"), command=self.run_custom, color=COLORS["success"], hover_color=COLORS["success_hover"], height=56).pack(fill=tk.X)

    def create_slider(self, parent, label_key, variable, min_val, max_val, is_float):
        frame = tk.Frame(parent, bg=COLORS["card_bg"], pady=10)
        frame.pack(fill=tk.X)
        header = tk.Frame(frame, bg=COLORS["card_bg"])
        header.pack(fill=tk.X, pady=(0, 6))
        tk.Label(header, text=self.t(label_key), font=FONTS["body"], fg=COLORS["text_muted"], bg=COLORS["card_bg"]).pack(side=tk.LEFT)
        value_label = tk.Label(header, font=FONTS["h3"], fg=COLORS["accent"], bg=COLORS["card_bg"])
        value_label.pack(side=tk.RIGHT)

        def update(*_):
            val = variable.get()
            value_label.config(text=f"{val:.2f}" if is_float else f"{int(val)}")

        variable.trace_add("write", update)
        update()
        ttk.Scale(frame, from_=min_val, to=max_val, variable=variable, orient="horizontal").pack(fill=tk.X)

    def create_output_panel(self, parent):
        card = CardFrame(parent, self.t("live_output"))
        tk.Label(card, text=self.t("dashboard"), font=FONTS["small"], fg=COLORS["text_muted"], bg=COLORS["card_bg"], anchor="w").pack(fill=tk.X)
        text_container = tk.Frame(card, bg=COLORS["bg_dark"], relief=tk.FLAT)
        text_container.pack(fill=tk.BOTH, expand=True, pady=(10, 6))

        self.output_text = scrolledtext.ScrolledText(
            text_container,
            wrap=tk.WORD,
            font=FONTS["mono"],
            bg=COLORS["bg_dark"],
            fg=COLORS["text_light"],
            insertbackground="white",
            padx=16,
            pady=16,
            borderwidth=0,
            highlightthickness=0,
        )
        self.output_text.pack(fill=tk.BOTH, expand=True)

        toolbar = tk.Frame(card, bg=COLORS["card_bg"], height=48, pady=8)
        toolbar.pack(fill=tk.X)
        self.status_label = tk.Label(toolbar, text=f"● {self.t('status_ready')}", font=FONTS["body"], fg=COLORS["success"], bg=COLORS["card_bg"])
        self.status_label.pack(side=tk.LEFT)
        ModernButton(toolbar, text=self.t("clear_output"), command=self.clear_output, color=COLORS["bg_medium"], hover_color=COLORS["bg_dark"], height=38, width=150).pack(side=tk.RIGHT)

    def switch_language(self, lang_code):
        self.current_lang.set(lang_code)
        for widget in self.root.winfo_children():
            widget.destroy()
        self.create_widgets()

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
            "challenge": "challenge",
        }
        modes = defense_map[self.defense_var.get()]
        cmd = (
            f"--modes {modes} --runs {self.runs_var.get()} --num-legit 20 "
            f"--num-replay 100 --p-loss {self.ploss_var.get()} --p-reorder {self.preorder_var.get()}"
        )
        self.run_command(cmd, self.t("custom_exp"))

    def run_command(self, args, description):
        if self.running:
            messagebox.showwarning("Busy", self.t("busy_msg"))
            return
        self.running = True
        self.set_status(True, f"{self.t('status_running')}: {description}")
        self.output_text.insert(tk.END, f"\n{'=' * 60}\n▶ START: {description}\n{'=' * 60}\n\n")
        self.output_text.see(tk.END)

        def worker():
            try:
                cmd = f"source .venv/bin/activate && python main.py {args}"
                proc = subprocess.Popen(
                    cmd,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    executable="/bin/bash",
                )
                for line in proc.stdout:
                    self.output_queue.put(line)
                proc.wait()
                self.output_queue.put(f"\n✅ {self.t('done')}\n")
            except Exception as exc:  # pylint: disable=broad-except
                self.output_queue.put(f"\n❌ {self.t('error')}: {exc}\n")
            finally:
                self.running = False
                self.set_status(False)

        threading.Thread(target=worker, daemon=True).start()

    def generate_plots(self):
        if self.running:
            messagebox.showwarning("Busy", self.t("busy_msg"))
            return
        self.running = True
        self.set_status(True, self.t("generate_plots"))

        def worker():
            subprocess.run("source .venv/bin/activate && python scripts/plot_results.py", shell=True, executable="/bin/bash")
            self.output_queue.put(f"✅ {self.t('generate_plots')} {self.t('done')}\n")
            self.running = False
            self.set_status(False)

        threading.Thread(target=worker, daemon=True).start()

    def export_tables(self):
        if self.running:
            messagebox.showwarning("Busy", self.t("busy_msg"))
            return
        self.running = True
        self.set_status(True, self.t("export_tables"))

        def worker():
            subprocess.run("source .venv/bin/activate && python scripts/export_tables.py", shell=True, executable="/bin/bash")
            self.output_queue.put(f"✅ {self.t('export_tables')} {self.t('done')}\n")
            self.running = False
            self.set_status(False)

        threading.Thread(target=worker, daemon=True).start()

    def clear_output(self):
        self.output_text.delete(1.0, tk.END)

    def set_status(self, is_running, text=None):
        if text:
            self.status_label.config(text=f"● {text}")
        else:
            self.status_label.config(text=f"● {self.t('status_ready')}")
        self.status_label.config(fg=COLORS["warning"] if is_running else COLORS["success"])

    def check_output(self):
        try:
            while True:
                line = self.output_queue.get_nowait()
                self.output_text.insert(tk.END, line)
                self.output_text.see(tk.END)
        except queue.Empty:
            pass
        self.root.after(120, self.check_output)


def main():
    root = tk.Tk()
    SimulationGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
