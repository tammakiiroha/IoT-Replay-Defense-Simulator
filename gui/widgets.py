"""
可复用的 GUI 组件
Reusable GUI widgets
"""

import tkinter as tk

from .theme import COLORS, FONTS


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
        super().__init__(
            parent,
            bg=COLORS["bg_card"],
            bd=1,
            relief=tk.SOLID,
            highlightbackground=COLORS["border"],
            highlightthickness=1,
            **kwargs
        )
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
