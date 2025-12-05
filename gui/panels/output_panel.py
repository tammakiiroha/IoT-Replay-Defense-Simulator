"""
输出面板
Output panel with terminal display
"""

import tkinter as tk
from tkinter import scrolledtext

from ..theme import COLORS, FONTS
from ..widgets import AcademicButton, SectionCard


def create_output_panel(parent, app):
    """
    创建输出面板
    
    Args:
        parent: 父容器
        app: SimulationGUI 实例
    """
    card = SectionCard(parent, title=app.t("live_output"))
    card.pack(fill=tk.BOTH, expand=True)
    
    # 指标说明面板（紧凑设计）
    metrics_info = tk.Frame(card.content, bg=COLORS["bg_section"], bd=1, relief=tk.SOLID)
    metrics_info.pack(fill=tk.X, padx=10, pady=(0, 8))
    
    # 说明标题和内容在一行（更紧凑）
    info_row = tk.Frame(metrics_info, bg=COLORS["bg_section"], padx=12, pady=8)
    info_row.pack(fill=tk.X)
    
    # 左侧：标题
    left_frame = tk.Frame(info_row, bg=COLORS["bg_section"])
    left_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
    
    tk.Label(
        left_frame,
        text=app.t("metrics_help") + ":",
        font=FONTS["body"],
        fg=COLORS["text_primary"],
        bg=COLORS["bg_section"]
    ).pack(side=tk.LEFT)
    
    # 说明内容
    metrics_text = app.t("metrics_explanation")
    tk.Label(
        left_frame,
        text=metrics_text,
        font=FONTS["small"],
        fg=COLORS["text_secondary"],
        bg=COLORS["bg_section"],
        justify=tk.LEFT,
        wraplength=600
    ).pack(side=tk.LEFT, padx=(8, 0))
    
    # 右侧：帮助按钮
    help_btn = tk.Button(
        info_row,
        text="ⓘ",
        font=("Arial", 18, "bold"),
        fg="#00d4ff",
        bg=COLORS["primary"],
        activebackground="#4a5f8c",
        activeforeground="#00ffff",
        bd=0,
        relief=tk.FLAT,
        cursor="hand2",
        command=lambda: _show_metrics_help(app),
        padx=10,
        pady=5,
        width=3,
        height=1
    )
    help_btn.pack(side=tk.RIGHT, padx=(10, 5))
    
    # 鼠标悬停效果
    def on_enter(e):
        help_btn.config(bg="#5a7fb8", fg="#00ffff", relief=tk.RAISED)
    def on_leave(e):
        help_btn.config(bg=COLORS["primary"], fg="#00d4ff", relief=tk.FLAT)
    
    help_btn.bind("<Enter>", on_enter)
    help_btn.bind("<Leave>", on_leave)
    
    # 终端输出
    terminal_frame = tk.Frame(card.content, bg=COLORS["terminal_bg"], bd=0)
    terminal_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 0))
    
    app.output_text = scrolledtext.ScrolledText(
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
    app.output_text.pack(fill=tk.BOTH, expand=True)
    
    # 底部工具栏
    toolbar = tk.Frame(card.content, bg=COLORS["bg_card"], pady=12)
    toolbar.pack(fill=tk.X)
    
    app.status_label = tk.Label(
        toolbar,
        text=f"● {app.t('status_ready')}",
        font=FONTS["body"],
        fg=COLORS["success"],
        bg=COLORS["bg_card"]
    )
    app.status_label.pack(side=tk.LEFT)
    
    # 停止按钮（初始隐藏）
    app.stop_button = AcademicButton(
        toolbar,
        text=app.t("stop_sim"),
        command=app.stop_experiment,
        style="secondary",
        height=32,
        width=80
    )
    
    # 保存输出按钮
    AcademicButton(
        toolbar,
        text=app.t("save_output"),
        command=app.save_output,
        style="secondary",
        height=32,
        width=120
    ).pack(side=tk.RIGHT, padx=(0, 5))
    
    AcademicButton(
        toolbar,
        text=app.t("clear_output"),
        command=app.clear_output,
        style="secondary",
        height=32,
        width=100
    ).pack(side=tk.RIGHT, padx=(0, 5))


def _show_metrics_help(app):
    """显示详细的指标说明对话框"""
    help_text = app.t("metrics_tooltip")
    
    # 创建自定义对话框
    dialog = tk.Toplevel(app.root)
    dialog.title(app.t("metrics_help"))
    dialog.geometry("600x500")
    dialog.configure(bg=COLORS["bg_main"])
    
    # 设置为模态对话框
    dialog.transient(app.root)
    dialog.grab_set()
    
    # 标题
    title_frame = tk.Frame(dialog, bg=COLORS["primary"], padx=20, pady=15)
    title_frame.pack(fill=tk.X)
    
    tk.Label(
        title_frame,
        text="📊 " + app.t("metrics_help"),
        font=("Segoe UI", 16, "bold"),
        fg="white",
        bg=COLORS["primary"]
    ).pack()
    
    # 内容区域
    content_frame = tk.Frame(dialog, bg=COLORS["bg_main"], padx=20, pady=20)
    content_frame.pack(fill=tk.BOTH, expand=True)
    
    # 滚动文本框显示详细说明
    text_widget = scrolledtext.ScrolledText(
        content_frame,
        wrap=tk.WORD,
        font=("Segoe UI", 11),
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
    
    btn_text = "Got it" if app.current_lang.get() == "en" else "了解" if app.current_lang.get() == "zh" else "理解しました"
    AcademicButton(
        btn_frame,
        text="✓ " + btn_text,
        command=dialog.destroy,
        style="accent",
        height=40,
        width=120
    ).pack()
    
    # 居中显示
    dialog.update_idletasks()
    x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
    y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
    dialog.geometry(f"+{x}+{y}")
