"""
可复用的 GUI 组件
Reusable GUI widgets - Web-style modern design
"""

import tkinter as tk

from .theme import COLORS, FONTS


class ModernButton(tk.Canvas):
    """现代风格圆角按钮（模拟 Web 版本的按钮样式）"""
    
    def __init__(self, parent, text, command, style="primary", width=None, height=44, **kwargs):
        """
        Args:
            parent: 父容器
            text: 按钮文字
            command: 点击回调
            style: 按钮样式 ("primary", "accent", "secondary", "dark")
            width: 宽度（None 表示自适应）
            height: 高度
        """
        self.styles = {
            "primary": {
                "bg": COLORS["primary"],
                "hover": COLORS["primary_dark"],
                "fg": COLORS["text_light"],
            },
            "accent": {
                "bg": COLORS["primary"],
                "hover": COLORS["primary_dark"],
                "fg": COLORS["text_light"],
            },
            "secondary": {
                "bg": COLORS["bg_section"],
                "hover": COLORS["border"],
                "fg": COLORS["text_secondary"],
            },
            "dark": {
                "bg": "#0f172a",  # slate-900
                "hover": "#000000",
                "fg": COLORS["text_light"],
            },
        }
        
        self.style_config = self.styles.get(style, self.styles["primary"])
        self.command = command
        self.text = text
        self.btn_height = height
        
        # 计算宽度
        if width:
            self.btn_width = width
        else:
            # 自动计算宽度（估算）
            self.btn_width = len(text) * 10 + 40
        
        super().__init__(
            parent, 
            width=self.btn_width, 
            height=height,
            bg=parent.cget("bg"),
            highlightthickness=0,
            cursor="hand2",
            **kwargs
        )
        
        self._draw_button(self.style_config["bg"])
        
        # 绑定事件
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)
    
    def _draw_button(self, bg_color):
        """绘制圆角按钮"""
        self.delete("all")
        radius = 12
        
        # 绘制圆角矩形
        self.create_rounded_rect(
            2, 2, self.btn_width - 2, self.btn_height - 2,
            radius=radius,
            fill=bg_color,
            outline=""
        )
        
        # 绘制文字
        self.create_text(
            self.btn_width // 2,
            self.btn_height // 2,
            text=self.text,
            font=FONTS["button"],
            fill=self.style_config["fg"]
        )
    
    def create_rounded_rect(self, x1, y1, x2, y2, radius, **kwargs):
        """绘制圆角矩形"""
        points = [
            x1 + radius, y1,
            x2 - radius, y1,
            x2, y1,
            x2, y1 + radius,
            x2, y2 - radius,
            x2, y2,
            x2 - radius, y2,
            x1 + radius, y2,
            x1, y2,
            x1, y2 - radius,
            x1, y1 + radius,
            x1, y1,
        ]
        return self.create_polygon(points, smooth=True, **kwargs)
    
    def _on_enter(self, event):
        self._draw_button(self.style_config["hover"])
    
    def _on_leave(self, event):
        self._draw_button(self.style_config["bg"])
    
    def _on_click(self, event):
        if self.command:
            self.command()


class ModernCard(tk.Frame):
    """现代卡片组件（模拟 Web 版本的卡片样式）"""
    
    def __init__(self, parent, **kwargs):
        super().__init__(
            parent,
            bg=COLORS["bg_card"],
            highlightbackground=COLORS["border"],
            highlightthickness=1,
            **kwargs
        )
        
        # 内容区域
        self.content = tk.Frame(self, bg=COLORS["bg_card"], padx=24, pady=20)
        self.content.pack(fill=tk.BOTH, expand=True)


class SectionHeader(tk.Frame):
    """章节标题（Web 风格）"""
    
    def __init__(self, parent, text, icon=None, **kwargs):
        super().__init__(parent, bg=parent.cget("bg"), **kwargs)
        
        # 图标（可选）
        if icon:
            tk.Label(
                self,
                text=icon,
                font=FONTS["small"],
                fg=COLORS["text_muted"],
                bg=self.cget("bg")
            ).pack(side=tk.LEFT, padx=(0, 6))
        
        # 标题文字
        tk.Label(
            self,
            text=text.upper(),
            font=(FONTS["small"][0], FONTS["small"][1], "bold"),
            fg=COLORS["text_muted"],
            bg=self.cget("bg"),
            anchor="w"
        ).pack(side=tk.LEFT)


class ModernSlider(tk.Frame):
    """现代滑块组件（Web 风格）"""
    
    def __init__(self, parent, label, variable, min_val, max_val, 
                 is_float=False, show_badge=None, app=None, **kwargs):
        """
        Args:
            parent: 父容器
            label: 标签文字
            variable: Tkinter 变量
            min_val: 最小值
            max_val: 最大值
            is_float: 是否为浮点数
            show_badge: 显示标签的函数 (value) -> str 或 None
            app: 应用实例（用于翻译）
        """
        super().__init__(parent, bg=COLORS["bg_card"], **kwargs)
        
        self.variable = variable
        self.is_float = is_float
        self.show_badge = show_badge
        
        # 标题行
        header = tk.Frame(self, bg=COLORS["bg_card"])
        header.pack(fill=tk.X, pady=(0, 8))
        
        # 标签
        tk.Label(
            header,
            text=label,
            font=FONTS["body"],
            fg=COLORS["text_primary"],
            bg=COLORS["bg_card"]
        ).pack(side=tk.LEFT)
        
        # 数值显示（圆角背景）
        self.value_frame = tk.Frame(header, bg=COLORS["bg_section"], padx=8, pady=2)
        self.value_frame.pack(side=tk.RIGHT)
        
        self.value_label = tk.Label(
            self.value_frame,
            font=(FONTS["mono"][0], FONTS["mono"][1], "bold"),
            fg=COLORS["text_secondary"],
            bg=COLORS["bg_section"]
        )
        self.value_label.pack()
        
        # 滑块
        from tkinter import ttk
        style = ttk.Style()
        style.configure(
            "Modern.Horizontal.TScale",
            background=COLORS["bg_card"],
            troughcolor=COLORS["bg_section"],
        )
        
        self.scale = ttk.Scale(
            self,
            from_=min_val,
            to=max_val,
            variable=variable,
            orient="horizontal",
            style="Modern.Horizontal.TScale"
        )
        self.scale.pack(fill=tk.X)
        
        # 监听变化
        variable.trace_add("write", self._update_value)
        self._update_value()
    
    def _update_value(self, *args):
        val = self.variable.get()
        if self.is_float:
            text = f"{val:.0%}" if val <= 1 else f"{val:.2f}"
        else:
            text = str(int(val))
        self.value_label.config(text=text)


class ScenarioButton(tk.Frame):
    """场景选择按钮（Web 风格）"""
    
    def __init__(self, parent, text, command, is_selected=False, **kwargs):
        bg_color = COLORS["primary"] if is_selected else COLORS["bg_card"]
        fg_color = COLORS["text_light"] if is_selected else COLORS["text_secondary"]
        border_color = COLORS["primary"] if is_selected else COLORS["border"]
        
        super().__init__(
            parent,
            bg=bg_color,
            highlightbackground=border_color,
            highlightthickness=1,
            cursor="hand2",
            **kwargs
        )
        
        self.command = command
        self.is_selected = is_selected
        self.bg_color = bg_color
        self.fg_color = fg_color
        
        self.label = tk.Label(
            self,
            text=text,
            font=FONTS["body"],
            fg=fg_color,
            bg=bg_color,
            padx=16,
            pady=12,
            anchor="w",
            cursor="hand2"
        )
        self.label.pack(fill=tk.X)
        
        # 绑定点击事件
        for widget in [self, self.label]:
            widget.bind("<Button-1>", self._on_click)
            if not is_selected:
                widget.bind("<Enter>", self._on_enter)
                widget.bind("<Leave>", self._on_leave)
    
    def _on_click(self, event):
        if self.command:
            self.command()
    
    def _on_enter(self, event):
        self.configure(bg=COLORS["bg_section"])
        self.label.configure(bg=COLORS["bg_section"])
    
    def _on_leave(self, event):
        self.configure(bg=self.bg_color)
        self.label.configure(bg=self.bg_color)


class ModeCheckbox(tk.Frame):
    """防御模式复选框（Web 风格）"""
    
    def __init__(self, parent, mode_id, title, description, variable, color, **kwargs):
        super().__init__(
            parent,
            bg=COLORS["bg_card"],
            highlightbackground=COLORS["border_light"],
            highlightthickness=1,
            cursor="hand2",
            **kwargs
        )
        
        self.variable = variable
        self.mode_id = mode_id
        self.color = color
        
        # 内容容器
        content = tk.Frame(self, bg=COLORS["bg_card"], padx=12, pady=10)
        content.pack(fill=tk.X)
        
        # 复选框
        self.checkbox = tk.Checkbutton(
            content,
            variable=variable,
            bg=COLORS["bg_card"],
            activebackground=COLORS["bg_card"],
            highlightthickness=0,
            cursor="hand2"
        )
        self.checkbox.pack(side=tk.LEFT)
        
        # 文字区域
        text_frame = tk.Frame(content, bg=COLORS["bg_card"])
        text_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 0))
        
        # 标题（带颜色指示器）
        title_frame = tk.Frame(text_frame, bg=COLORS["bg_card"])
        title_frame.pack(fill=tk.X)
        
        # 颜色点
        tk.Frame(title_frame, bg=color, width=8, height=8).pack(side=tk.LEFT, padx=(0, 8))
        
        tk.Label(
            title_frame,
            text=title,
            font=FONTS["body"],
            fg=COLORS["text_primary"],
            bg=COLORS["bg_card"],
            anchor="w"
        ).pack(side=tk.LEFT)
        
        # 描述
        tk.Label(
            text_frame,
            text=description,
            font=FONTS["small"],
            fg=COLORS["text_muted"],
            bg=COLORS["bg_card"],
            anchor="w"
        ).pack(fill=tk.X, pady=(2, 0))
        
        # 绑定点击整个区域切换复选框
        for widget in [self, content, text_frame, title_frame]:
            widget.bind("<Button-1>", lambda e: self.checkbox.invoke())


# === 兼容性别名（保持旧代码兼容）===

class AcademicButton(ModernButton):
    """兼容旧代码的按钮别名"""
    pass


class SectionCard(ModernCard):
    """兼容旧代码的卡片别名"""
    
    def __init__(self, parent, title=None, subtitle=None, **kwargs):
        super().__init__(parent, **kwargs)
        
        if title:
            header = tk.Frame(self.content, bg=COLORS["bg_card"])
            header.pack(fill=tk.X, pady=(0, 16))
            
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


class ResultBarChart(tk.Frame):
    """结果柱状图组件（带动态动画效果）"""
    
    def __init__(self, parent, title, unit="%", **kwargs):
        super().__init__(parent, bg=COLORS["bg_card"], **kwargs)
        
        self.unit = unit
        
        # 标题栏
        header = tk.Frame(self, bg=COLORS["bg_card"])
        header.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(
            header,
            text=title,
            font=FONTS["h3"],
            fg=COLORS["text_secondary"],
            bg=COLORS["bg_card"]
        ).pack(side=tk.LEFT)
        
        # 画布
        self.canvas = tk.Canvas(
            self,
            bg=COLORS["bg_card"],
            highlightthickness=0,
            height=20
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.animation_items = []
    
    def update_data(self, data):
        """更新图表数据并播放动画"""
        self.canvas.delete("all")
        self.animation_items = []
        
        if not data:
            return
            
        bar_height = 16  # 更纤细的胶囊风格
        gap = 24         # 更大的间距，呼吸感
        total_height = len(data) * (bar_height + gap)
        self.canvas.config(height=total_height)
        
        # 获取宽度
        width = self.canvas.winfo_width() 
        if width < 100: width = 350 # Fallback 增加默认宽度
        
        y = 0
        
        # 布局参数
        label_w = 160         # 左侧标签区宽度
        value_w = 70          # 右侧数值区宽度
        right_pad = 20        # 右边距
        
        # 进度条区域宽度
        track_w = width - label_w - value_w - right_pad
        if track_w < 50: track_w = 100 # 最小保护
        
        track_x = label_w
        
        for item in data:
            label = item["label"]
            val = item["value"]
            color = item["color"]
            
            # 1. 左侧标签 (垂直居中)
            self.canvas.create_text(
                0, y + bar_height/2,
                text=label,
                anchor="w",
                font=FONTS["small"],
                fill=COLORS["text_secondary"]
            )
            
            # 2. 背景槽 (全圆角胶囊)
            self._create_rounded_bar(
                track_x, y,
                track_x + track_w, y + bar_height,
                radius=bar_height/2,
                fill=COLORS["bg_section"]
            )
            
            # 3. 进度条 (初始宽度 0)
            target_pixel_w = track_w * val
            if target_pixel_w < bar_height: target_pixel_w = bar_height # 保持圆形
            
            # 创建初始 bar (保持为圆形)
            points = self._get_rounded_rect_points(
                track_x, y, 
                track_x + bar_height, y + bar_height, 
                radius=bar_height/2
            )
            bar_id = self.canvas.create_polygon(points, smooth=True, fill=color)
            
            # 4. 数值 (右对齐，固定位置)
            val_text_id = self.canvas.create_text(
                width - right_pad, y + bar_height/2,
                text=f"0.0{self.unit}",
                anchor="e", # 右对齐
                font=(FONTS["mono"][0], 11, "bold"),
                fill=COLORS["text_primary"]
            )
            
            self.animation_items.append({
                "bar_id": bar_id,
                "text_id": val_text_id,
                "start_x": track_x,
                "y": y,
                "height": bar_height,
                "target_w": target_pixel_w,
                "final_val": val,
                "radius": bar_height/2
            })
            
            y += bar_height + gap
            
        # 启动动画
        self.after(10, self._animate, 0)

    def _create_rounded_bar(self, x1, y1, x2, y2, radius, **kwargs):
        """绘制圆角条(封装)"""
        points = self._get_rounded_rect_points(x1, y1, x2, y2, radius)
        return self.canvas.create_polygon(points, smooth=True, **kwargs)

    def _animate(self, frame):
        """执行动画帧"""
        total_frames = 50 
        if frame > total_frames:
            return
            
        progress = frame / total_frames
        ease = 1 - pow(1 - progress, 3) # Cubic ease out
        
        for item in self.animation_items:
            # 更新条形宽度
            current_w = item["target_w"] * ease
            # 最小宽度限制为高度(保持圆形)或更小
            min_w = item["height"]
            if current_w < min_w: current_w = min_w
            
            points = self._get_rounded_rect_points(
                item["start_x"], item["y"], 
                item["start_x"] + current_w, item["y"] + item["height"], 
                radius=item["radius"]
            )
            self.canvas.coords(item["bar_id"], *points)
            
            # 更新数值
            current_val = item["final_val"] * ease
            self.canvas.itemconfigure(item["text_id"], text=f"{current_val*100:.1f}{self.unit}")
            
        self.after(16, self._animate, frame + 1)

    def _get_rounded_rect_points(self, x1, y1, x2, y2, radius):
        """生成圆角矩形路径点"""
        # 防止半径过大
        h = y2 - y1
        w = x2 - x1
        r = min(radius, h/2, w/2) if w > 0 else 0
        if r < 0: r = 0
        
        return [
            x1 + r, y1,
            x2 - r, y1,
            x2, y1,
            x2, y1 + r,
            x2, y2 - r,
            x2, y2,
            x2 - r, y2,
            x1 + r, y2,
            x1, y2,
            x1, y2 - r,
            x1, y1 + r,
            x1, y1,
        ]

