"""
主题配置：颜色和字体
Theme configuration: colors and fonts
"""

import platform

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
