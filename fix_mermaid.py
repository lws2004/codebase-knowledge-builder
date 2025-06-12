#!/usr/bin/env python3
"""修复文档中的Mermaid图表语法错误"""

import os
import re
import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, os.getcwd())

from src.utils.mermaid_realtime_validator import _auto_fix_mermaid_block
from src.utils.mermaid_validator import validate_mermaid_syntax_sync


def fix_mermaid_in_file(file_path):
    """修复指定文件中的Mermaid图表

    Args:
        file_path: 文件路径

    Returns:
        bool: 是否进行了修复
    """
    # 读取文件内容
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"❌ 读取文件失败: {str(e)}")
        return False

    # 查找所有Mermaid代码块
    mermaid_pattern = r"```mermaid\n((?:(?!```)[\s\S])*?)\n```"
    mermaid_matches = list(re.finditer(mermaid_pattern, content, re.DOTALL))

    if not mermaid_matches:
        print(f"📋 文件中没有找到Mermaid图表: {file_path}")
        return False

    print(f"🔍 在文件中找到 {len(mermaid_matches)} 个Mermaid图表")

    # 检查并修复每个Mermaid块
    fixed_content = content
    was_fixed = False
    offset = 0  # 替换引起的偏移量

    for match in mermaid_matches:
        # 获取原始块的内容和位置
        original_block = match.group(1).strip()
        start_pos = match.start(1) + offset
        end_pos = match.end(1) + offset

        # 验证语法
        is_valid, errors = validate_mermaid_syntax_sync(original_block)

        if not is_valid:
            print(f"❌ 检测到语法错误: {errors}")

            # 自动修复
            fixed_block = _auto_fix_mermaid_block(original_block)

            # 验证修复结果
            is_fixed_valid, fixed_errors = validate_mermaid_syntax_sync(fixed_block)

            if is_fixed_valid:
                print("✅ 自动修复成功!")

                # 更新内容
                block_with_markers = f"```mermaid\n{original_block}\n```"
                fixed_block_with_markers = f"```mermaid\n{fixed_block}\n```"

                # 替换并更新偏移量
                new_content = fixed_content[: start_pos - 10] + fixed_block + fixed_content[end_pos + 3 :]
                offset += len(fixed_block) - len(original_block)
                fixed_content = new_content
                was_fixed = True
            else:
                print(f"❌ 自动修复失败，仍有错误: {fixed_errors}")

    # 如果有修复，写回文件
    if was_fixed:
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(fixed_content)
            print(f"💾 已将修复后的内容写回文件: {file_path}")
            return True
        except Exception as e:
            print(f"❌ 写入文件失败: {str(e)}")
            return False
    else:
        print("📋 没有需要修复的内容")
        return False


def fix_all_mermaid_in_directory(directory_path, extensions=None):
    """修复目录中所有文件的Mermaid图表

    Args:
        directory_path: 目录路径
        extensions: 要处理的文件扩展名列表，默认为['.md']
    """
    if extensions is None:
        extensions = [".md"]

    directory = Path(directory_path)
    if not directory.exists() or not directory.is_dir():
        print(f"❌ 目录不存在或不是一个有效的目录: {directory_path}")
        return

    fixed_files = 0
    total_files = 0

    for ext in extensions:
        for file_path in directory.glob(f"**/*{ext}"):
            total_files += 1
            print(f"\n🔍 检查文件: {file_path}")
            if fix_mermaid_in_file(file_path):
                fixed_files += 1

    print(f"\n🎉 处理完成! 检查了 {total_files} 个文件，修复了 {fixed_files} 个文件的Mermaid图表")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        target = sys.argv[1]
        path = Path(target)

        if path.is_file():
            print(f"🔧 修复单个文件中的Mermaid图表: {path}")
            fix_mermaid_in_file(path)
        elif path.is_dir():
            print(f"🔧 修复目录中所有文件的Mermaid图表: {path}")
            fix_all_mermaid_in_directory(path)
        else:
            print(f"❌ 无效的路径: {path}")
    else:
        current_dir = os.getcwd()
        print(f"🔧 修复当前目录中所有文件的Mermaid图表: {current_dir}")
        fix_all_mermaid_in_directory(current_dir)
