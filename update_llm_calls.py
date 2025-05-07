#!/usr/bin/env python3
"""脚本用于更新所有节点中的LLM调用，添加max_input_tokens=None参数。"""

import os
import re

# 定义要搜索的目录
SRC_DIR = "src"
NODES_DIR = os.path.join(SRC_DIR, "nodes")

# 定义要匹配的模式
# 匹配 LLM 调用模式
COMPLETION_PATTERN = (
    r"(response\s*=\s*llm_client\.completion\s*\(\s*(?:[^)]*,\s*)?"
    r"messages\s*=\s*messages\s*,\s*temperature\s*=\s*[^,)]+\s*,\s*"
    r"model\s*=\s*model\s*,\s*trace_name\s*=\s*[^,)]+)(\s*\))"
)

# 定义替换模式
REPLACEMENT = r"\1, max_input_tokens=None\2"


def update_file(file_path):
    """更新文件中的LLM调用"""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 检查文件是否包含LLM调用
    if "llm_client.completion" in content:
        # 使用正则表达式替换
        updated_content = re.sub(COMPLETION_PATTERN, REPLACEMENT, content)

        # 如果内容有变化，写回文件
        if updated_content != content:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(updated_content)
            print(f"已更新: {file_path}")
            return True

    return False


def main():
    """主函数"""
    # 获取所有Python文件
    updated_files = 0
    for root, _, files in os.walk(NODES_DIR):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                if update_file(file_path):
                    updated_files += 1

    print(f"共更新了 {updated_files} 个文件")


if __name__ == "__main__":
    main()
