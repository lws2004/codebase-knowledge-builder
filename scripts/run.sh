#!/bin/bash
# 运行主程序

# 检查是否提供了仓库 URL
if [ -z "$1" ]; then
    echo "错误: 缺少仓库 URL"
    echo "用法: ./scripts/run.sh <repo_url> [branch] [env] [language] [output_dir]"
    exit 1
fi

REPO_URL=$1
BRANCH=${2:-main}  # 默认分支为 main
ENV=${3:-default}  # 默认环境为 default
LANGUAGE=${4:-zh}  # 默认语言为中文
OUTPUT_DIR=${5:-docs_output}  # 默认输出目录为 docs_output

# 激活虚拟环境
source .venv/bin/activate

# 运行主程序
echo "运行主程序..."
echo "仓库 URL: $REPO_URL"
echo "分支: $BRANCH"
echo "环境: $ENV"
echo "输出语言: $LANGUAGE"
echo "输出目录: $OUTPUT_DIR"

python main.py --repo-url "$REPO_URL" --branch "$BRANCH" --env "$ENV" --language "$LANGUAGE" --output-dir "$OUTPUT_DIR"

# 检查结果
if [ $? -eq 0 ]; then
    echo "文档生成成功！"
    echo "输出目录: $OUTPUT_DIR"
else
    echo "文档生成失败！"
    exit 1
fi
