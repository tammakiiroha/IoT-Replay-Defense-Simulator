#!/bin/bash
# GUI启动脚本 GUI Launch Script

# 激活虚拟环境
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# 运行图形界面
python gui.py

