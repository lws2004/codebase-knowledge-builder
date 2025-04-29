#!/bin/bash
# 使用 uv 设置项目环境

# 确保 scripts 目录存在
mkdir -p scripts

# 创建虚拟环境
echo "创建虚拟环境..."
uv venv .venv

# 激活虚拟环境
echo "激活虚拟环境..."
source .venv/bin/activate

# 安装依赖
echo "安装依赖..."
uv pip install -r requirements.txt

echo "环境设置完成！"
echo "使用 'source .venv/bin/activate' 激活虚拟环境"
