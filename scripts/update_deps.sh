#!/bin/bash
# 使用 uv 更新项目依赖

# 激活虚拟环境
source .venv/bin/activate

# 更新依赖
echo "更新依赖..."
uv pip install -U -r requirements.txt

echo "依赖更新完成！"
