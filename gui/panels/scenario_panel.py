"""
实验场景面板
Scenario selection panel
"""

import tkinter as tk

from ..theme import COLORS, FONTS
from ..widgets import AcademicButton, SectionCard


def create_scenario_panel(parent, app):
    """
    创建实验场景面板
    
    Args:
        parent: 父容器
        app: SimulationGUI 实例 (用于访问翻译和回调)
    """
    card = SectionCard(parent, title=app.t("scenarios"))
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
            text=app.t(title_key),
            font=FONTS["h3"],
            fg=COLORS["text_primary"],
            bg=COLORS["bg_section"],
            anchor="w"
        ).pack(fill=tk.X)
        
        tk.Label(
            content,
            text=app.t(desc_key),
            font=FONTS["small"],
            fg=COLORS["text_muted"],
            bg=COLORS["bg_section"],
            anchor="w"
        ).pack(fill=tk.X, pady=(4, 0))
        
        # 绑定点击
        for widget in [scenario_frame, content]:
            widget.bind("<Button-1>", lambda e, s=cmd: app.run_scenario(s))
    
    # 底部工具按钮
    tool_frame = tk.Frame(card.content, bg=COLORS["bg_card"], pady=10)
    tool_frame.pack(fill=tk.X)
    
    AcademicButton(
        tool_frame,
        text=app.t("generate_plots"),
        command=app.generate_plots,
        style="secondary",
        height=40
    ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
    
    AcademicButton(
        tool_frame,
        text=app.t("export_tables"),
        command=app.export_tables,
        style="secondary",
        height=40
    ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
