#!/bin/bash
# 运行主程序

# 检查是否提供了仓库 URL
if [ -z "$1" ]; then
    echo "错误: 缺少仓库 URL"
    echo "用法: ./scripts/run.sh <repo_url> [branch] [env]"
    exit 1
fi

REPO_URL=$1
BRANCH=${2:-main}  # 默认分支为 main
ENV=${3:-default}  # 默认环境为 default

# 激活虚拟环境
source .venv/bin/activate

# 运行主程序
echo "运行主程序..."
python main.py --repo-url "$REPO_URL" --branch "$BRANCH" --env "$ENV"

echo "程序执行完成！"
