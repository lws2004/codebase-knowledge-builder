#!/usr/bin/env python3
"""自动修复所有生成节点，在保存文件后立即修复 Mermaid 语法错误"""

import os
import re

# 需要修改的节点文件
NODE_FILES = [
    "src/nodes/generate_dependency_node.py",
    "src/nodes/generate_glossary_node.py",
    "src/nodes/generate_quick_look_node.py",
    "src/nodes/generate_api_docs_node.py",
    "src/nodes/generate_module_details_node.py",
]

# 导入语句模式
IMPORT_PATTERN = r"(from \.\.utils\.mermaid_realtime_validator import validate_mermaid_in_content)"
NEW_IMPORT = r"\1\nfrom ..utils.mermaid_regenerator import validate_and_fix_file_mermaid"

# 保存文档后的模式
SAVE_PATTERN = r'(log_and_notify\(f"[^"]*已保存到: \{file_path\}", "info"\))\s*\n(\s*return file_path)'
MERMAID_FIX_CODE = r"""\1

            # 立即修复文件中的 Mermaid 语法错误
            try:
                was_fixed = validate_and_fix_file_mermaid(file_path, self.llm_client, f"文档 - {repo_name}")
                if was_fixed:
                    log_and_notify(f"已修复文件中的 Mermaid 语法错误: {file_path}", "info")
            except Exception as e:
                log_and_notify(f"修复 Mermaid 语法错误时出错: {str(e)}", "warning")

\2"""


def fix_node_file(file_path: str) -> bool:
    """修复单个节点文件

    Args:
        file_path: 文件路径

    Returns:
        是否进行了修改
    """
    if not os.path.exists(file_path):
        print(f"❌ 文件不存在: {file_path}")
        return False

    try:
        # 读取文件内容
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        original_content = content

        # 1. 添加导入语句（如果还没有）
        if "from ..utils.mermaid_regenerator import validate_and_fix_file_mermaid" not in content:
            content = re.sub(IMPORT_PATTERN, NEW_IMPORT, content)
            print(f"✅ 已添加导入语句: {file_path}")

        # 2. 在保存文档后添加 Mermaid 修复代码
        # 查找所有保存文档的位置
        save_patterns = [
            r'(log_and_notify\(f"[^"]*已保存到: \{file_path\}", "info"\))\s*\n(\s*return file_path)',
            r'(log_and_notify\(f"[^"]*文档已保存到: \{file_path\}", "info"\))\s*\n(\s*return file_path)',
            r'(log_and_notify\(f"[^"]*已整合到: \{file_path\}", "info"\))\s*\n(\s*return file_path)',
        ]

        for pattern in save_patterns:
            if re.search(pattern, content):
                # 检查是否已经有修复代码
                if "validate_and_fix_file_mermaid" not in content:
                    content = re.sub(pattern, MERMAID_FIX_CODE, content)
                    print(f"✅ 已添加 Mermaid 修复代码: {file_path}")
                break

        # 如果内容有变化，写回文件
        if content != original_content:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"💾 已更新文件: {file_path}")
            return True
        else:
            print(f"📋 文件无需修改: {file_path}")
            return False

    except Exception as e:
        print(f"❌ 处理文件时出错 {file_path}: {str(e)}")
        return False


def main():
    """主函数"""
    print("🔧 开始修复生成节点文件...")

    fixed_count = 0
    total_count = len(NODE_FILES)

    for file_path in NODE_FILES:
        print(f"\n🔍 处理文件: {file_path}")
        if fix_node_file(file_path):
            fixed_count += 1

    print(f"\n🎉 处理完成! 修改了 {fixed_count}/{total_count} 个文件")


if __name__ == "__main__":
    main()
