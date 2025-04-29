#!/bin/bash
# 清理项目环境

echo "清理环境..."

# 删除虚拟环境
if [ -d ".venv" ]; then
    echo "删除虚拟环境..."
    rm -rf .venv
fi

# 删除 uv 缓存
if [ -d ".uv/cache" ]; then
    echo "删除 uv 缓存..."
    rm -rf .uv/cache
fi

# 删除 Python 缓存文件
echo "删除 Python 缓存文件..."
find . -name "__pycache__" -type d -exec rm -rf {} +
find . -name "*.pyc" -delete

echo "环境清理完成！"
