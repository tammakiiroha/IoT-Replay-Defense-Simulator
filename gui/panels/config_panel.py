"""
配置面板
Configuration panel with sliders and options
"""

import tkinter as tk
from tkinter import ttk

from ..theme import COLORS, FONTS
from ..widgets import AcademicButton, SectionCard


def create_config_panel(parent, app):
    """
    创建配置面板
    
    Args:
        parent: 父容器
        app: SimulationGUI 实例
    """
    card = SectionCard(parent, title=app.t("custom_exp"))
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
        text=app.t("defense_mech"),
        font=FONTS["h3"],
        fg=COLORS["text_primary"],
        bg=COLORS["bg_card"]
    ).pack(anchor="w", pady=(0, 10))
    
    app.defense_var = tk.StringVar(value="all")
    
    for key in ["all", "no_def", "rolling", "window", "challenge"]:
        ttk.Radiobutton(
            scrollable_frame,
            text=app.t(key),
            variable=app.defense_var,
            value=key,
            style="Academic.TRadiobutton"
        ).pack(anchor="w", pady=4)
    
    # 分割线
    tk.Frame(scrollable_frame, bg=COLORS["divider"], height=1).pack(fill=tk.X, pady=18)
    
    # 攻击模式
    tk.Label(
        scrollable_frame,
        text=app.t("attack_mode"),
        font=FONTS["h3"],
        fg=COLORS["text_primary"],
        bg=COLORS["bg_card"]
    ).pack(anchor="w", pady=(0, 10))
    
    app.attack_mode_var = tk.StringVar(value="post")
    
    for key, value in [("post_run", "post"), ("inline", "inline")]:
        ttk.Radiobutton(
            scrollable_frame,
            text=app.t(key),
            variable=app.attack_mode_var,
            value=value,
            style="Academic.TRadiobutton"
        ).pack(anchor="w", pady=4)
    
    # 分割线
    tk.Frame(scrollable_frame, bg=COLORS["divider"], height=1).pack(fill=tk.X, pady=18)
    
    # 参数配置
    tk.Label(
        scrollable_frame,
        text=app.t("params"),
        font=FONTS["h3"],
        fg=COLORS["text_primary"],
        bg=COLORS["bg_card"]
    ).pack(anchor="w", pady=(0, 10))
    
    # 初始化变量
    app.runs_var = tk.IntVar(value=100)
    app.num_legit_var = tk.IntVar(value=20)
    app.num_replay_var = tk.IntVar(value=100)
    app.ploss_var = tk.DoubleVar(value=0.0)
    app.preorder_var = tk.DoubleVar(value=0.0)
    app.window_size_var = tk.IntVar(value=5)
    app.seed_var = tk.IntVar(value=0)
    app.attacker_loss_var = tk.DoubleVar(value=0.0)
    
    _create_slider(scrollable_frame, "runs", app.runs_var, 10, 500, False, app)
    _create_slider(scrollable_frame, "num_legit", app.num_legit_var, 5, 100, False, app)
    _create_slider(scrollable_frame, "num_replay", app.num_replay_var, 10, 500, False, app)
    _create_slider(scrollable_frame, "p_loss", app.ploss_var, 0.0, 0.5, True, app)
    _create_slider(scrollable_frame, "p_reorder", app.preorder_var, 0.0, 0.5, True, app)
    _create_slider(scrollable_frame, "window_size", app.window_size_var, 1, 20, False, app)
    
    # 高级参数分割线
    tk.Frame(scrollable_frame, bg=COLORS["divider"], height=1).pack(fill=tk.X, pady=18)
    tk.Label(
        scrollable_frame,
        text=app.t("advanced"),
        font=FONTS["h3"],
        fg=COLORS["text_secondary"],
        bg=COLORS["bg_card"]
    ).pack(anchor="w", pady=(0, 10))
    
    _create_slider(scrollable_frame, "seed", app.seed_var, 0, 9999, False, app)
    _create_slider(scrollable_frame, "attacker_loss", app.attacker_loss_var, 0.0, 0.5, True, app)
    
    # 运行按钮
    tk.Frame(scrollable_frame, bg=COLORS["bg_card"], height=15).pack()
    
    AcademicButton(
        scrollable_frame,
        text=app.t("start_sim"),
        command=app.run_custom,
        style="accent",
        height=50
    ).pack(fill=tk.X, padx=5)


def _create_slider(parent, label_key, variable, min_val, max_val, is_float, app):
    """创建滑动条"""
    frame = tk.Frame(parent, bg=COLORS["bg_card"], pady=10)
    frame.pack(fill=tk.X)
    
    header = tk.Frame(frame, bg=COLORS["bg_card"])
    header.pack(fill=tk.X, pady=(0, 6))
    
    tk.Label(
        header,
        text=app.t(label_key),
        font=FONTS["body"],
        fg=COLORS["text_secondary"],
        bg=COLORS["bg_card"],
        width=30,
        anchor="w"
    ).pack(side=tk.LEFT)
    
    value_label = tk.Label(
        header,
        font=FONTS["h2"],
        fg=COLORS["accent"],
        bg=COLORS["bg_card"]
    )
    value_label.pack(side=tk.RIGHT, padx=10)
    
    def update(*args):
        val = variable.get()
        text = f"{val:.2f}" if is_float else f"{int(val)}"
        
        # 为窗口大小添加建议提示
        if label_key == "window_size":
            ival = int(val)
            if ival < 3:
                text += " ⚠"
            elif 3 <= ival <= 7:
                text += " ✓"
            elif ival > 10:
                text += " ⚠"
        
        # 为随机种子添加提示
        elif label_key == "seed":
            ival = int(val)
            if ival == 0:
                text += " 🎲"
            else:
                text += " 🔒"
        
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
            text=hint_text[app.current_lang.get()],
            font=FONTS["small"],
            fg=COLORS["text_muted"],
            bg=COLORS["bg_card"]
        ).pack(anchor="w", pady=(2, 0))
    
    # 为随机种子添加说明文本
    elif label_key == "seed":
        hint_text = {
            "en": "0=Random | Fixed number=Reproducible",
            "zh": "0=随机 | 非0=可重现（如42每次结果相同）",
            "ja": "0=ランダム | 非0=再現可能（例:42は毎回同じ結果）"
        }
        tk.Label(
            frame,
            text=hint_text[app.current_lang.get()],
            font=FONTS["small"],
            fg=COLORS["text_muted"],
            bg=COLORS["bg_card"]
        ).pack(anchor="w", pady=(2, 0))
