#!/usr/bin/env python3
"""修复特定Mermaid图表问题"""

import os
import re
import sys

# 添加项目根目录到Python路径
sys.path.insert(0, os.getcwd())

from src.utils.mermaid_realtime_validator import _auto_fix_mermaid_block
from src.utils.mermaid_validator import validate_mermaid_syntax_sync

# 要修复的文件路径
FILE_PATH = "/Users/lanws/workspace/ai-agents/codebase-knowledge-builder/docs_output/requests/index.md"

# 读取文件内容
with open(FILE_PATH, "r", encoding="utf-8") as f:
    content = f.read()

print(f"📝 已读取文件: {FILE_PATH}")
print(f"总字符数: {len(content)}")

# 查找所有Mermaid代码块
mermaid_pattern = r"```mermaid\n((?:(?!```)[\s\S])*?)\n```"
mermaid_blocks = re.findall(mermaid_pattern, content, re.DOTALL)

print(f"🔍 找到 {len(mermaid_blocks)} 个Mermaid图表")

# 打印每个图表的前几行和状态
for i, block in enumerate(mermaid_blocks):
    # 只打印前50个字符，避免输出过多
    preview = block[:50].replace("\n", " ") + "..." if len(block) > 50 else block
    print(f"\n图表 {i + 1}: {preview}")

    # 验证语法
    is_valid, errors = validate_mermaid_syntax_sync(block)
    if is_valid:
        print("  ✅ 语法正确")
    else:
        print(f"  ❌ 语法错误: {errors}")

        # 尝试修复
        fixed_block = _auto_fix_mermaid_block(block)
        is_fixed_valid, fixed_errors = validate_mermaid_syntax_sync(fixed_block)

        if is_fixed_valid:
            print("  🔧 自动修复成功!")

            # 将修复后的内容替换到原文件中
            old_block_with_markers = f"```mermaid\n{block}\n```"
            new_block_with_markers = f"```mermaid\n{fixed_block}\n```"

            # 更新内容
            content = content.replace(old_block_with_markers, new_block_with_markers)
            print("  📝 已更新图表内容")
        else:
            print(f"  ⚠️ 自动修复失败: {fixed_errors}")

# 保存修复后的内容
if content != content:
    with open(FILE_PATH, "w", encoding="utf-8") as f:
        f.write(content)
    print("\n💾 已保存修复后的内容到文件")
else:
    print("\n📋 没有进行任何修改")

print("\n🎉 处理完成!")
