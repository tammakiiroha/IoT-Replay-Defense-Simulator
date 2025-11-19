#!/bin/bash
# 交互式启动脚本 Interactive Launch Script

# 激活虚拟环境
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# 运行交互式菜单
python interactive.py

