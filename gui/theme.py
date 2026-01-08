"""
主题配置：颜色和字体
Theme configuration: colors and fonts

Web-style modern theme matching web/app/page.tsx
"""

import platform

# --- Web 风格配色方案 (Slate + Indigo) ---
COLORS = {
    # 背景色：Slate 灰色系
    "bg_main": "#f8fafc",           # slate-50 - 主背景
    "bg_card": "#ffffff",           # white - 卡片/侧边栏背景
    "bg_section": "#f1f5f9",        # slate-100 - 分区背景
    "bg_hover": "#f8fafc",          # slate-50 - 悬停背景
    
    # 主强调色：Indigo
    "primary": "#4f46e5",           # indigo-600
    "primary_light": "#6366f1",     # indigo-500
    "primary_dark": "#4338ca",      # indigo-700
    "primary_bg": "#eef2ff",        # indigo-50 - 浅色背景
    
    # 状态色
    "success": "#10b981",           # emerald-500
    "warning": "#f59e0b",           # amber-500
    "danger": "#ef4444",            # red-500
    "info": "#3b82f6",              # blue-500
    
    # 文字颜色
    "text_primary": "#0f172a",      # slate-900 - 主文字
    "text_secondary": "#64748b",    # slate-500 - 次要文字
    "text_muted": "#94a3b8",        # slate-400 - 弱化文字
    "text_light": "#ffffff",        # white - 白色文字
    
    # 边框与分割线
    "border": "#e2e8f0",            # slate-200
    "divider": "#e2e8f0",           # slate-200
    "border_light": "#f1f5f9",      # slate-100
    
    # 终端配色
    "terminal_bg": "#0f172a",       # slate-900 - 终端背景
    "terminal_text": "#e2e8f0",     # slate-200 - 终端文字
    
    # 防御模式颜色 (与 Web 版本一致)
    "mode_no_def": "#ef4444",       # red-500
    "mode_rolling": "#8b5cf6",      # violet-500
    "mode_window": "#3b82f6",       # blue-500
    "mode_challenge": "#10b981",    # emerald-500
    
    # 兼容性别名（保持旧代码兼容）
    "accent": "#4f46e5",            # indigo-600
    "accent_hover": "#4338ca",      # indigo-700
}

# --- 现代字体配置 ---
if platform.system() == "Darwin":  # macOS
    FONTS = {
        "title": ("SF Pro Display", 22, "bold"),      # 标题
        "subtitle": ("SF Pro Text", 12),              # 副标题
        "h1": ("SF Pro Display", 18, "bold"),         # 一级标题
        "h2": ("SF Pro Text", 14, "bold"),            # 二级标题
        "h3": ("SF Pro Text", 12, "bold"),            # 三级标题
        "body": ("SF Pro Text", 12),                  # 正文
        "small": ("SF Pro Text", 11),                 # 小字
        "tiny": ("SF Pro Text", 10),                  # 极小字
        "mono": ("Menlo", 11),                        # 等宽字体 (Menlo alignment is better)
        "button": ("SF Pro Text", 13, "bold"),        # 按钮
    }
else:  # Windows / Linux
    FONTS = {
        "title": ("Segoe UI", 20, "bold"),
        "subtitle": ("Segoe UI", 11),
        "h1": ("Segoe UI", 16, "bold"),
        "h2": ("Segoe UI", 13, "bold"),
        "h3": ("Segoe UI", 11, "bold"),
        "body": ("Segoe UI", 11),
        "small": ("Segoe UI", 10),
        "tiny": ("Segoe UI", 9),
        "mono": ("Consolas", 10),
        "button": ("Segoe UI", 12, "bold"),
    }

# 防御模式元数据
MODE_META = {
    "no_def": {"color": COLORS["mode_no_def"], "label": "No Defense"},
    "rolling": {"color": COLORS["mode_rolling"], "label": "Rolling Counter"},
    "window": {"color": COLORS["mode_window"], "label": "Sliding Window"},
    "challenge": {"color": COLORS["mode_challenge"], "label": "Challenge-Response"},
}
