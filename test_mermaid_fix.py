#!/usr/bin/env python3
"""
测试 Mermaid 修复功能
"""

import os
import tempfile

from src.utils.mermaid_regenerator import validate_and_fix_file_mermaid


def test_mermaid_fix():
    """测试 Mermaid 修复功能"""
    # 创建一个包含错误 Mermaid 语法的测试文件
    test_content = """# 测试文档

这是一个测试文档，包含错误的 Mermaid 语法。

```mermaid
pie title 数据分布
    title 重复的标题
    "Python" : 36
    "JavaScript" : 24
    "Other" : 40
    invalid_syntax_here
```

## 另一个图表

```mermaid
graph TD
    A[开始] --> B{判断}
    B -->|是| C[执行]
    B -->|否| D[结束]
    C --> D
```

这是正常的内容。
"""

    # 创建临时文件
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(test_content)
        temp_file = f.name

    try:
        print(f"📝 创建测试文件: {temp_file}")
        print("📋 原始内容:")
        with open(temp_file, "r", encoding="utf-8") as f:
            print(f.read())

        print("\n🔧 开始修复 Mermaid 语法错误...")

        # 测试修复功能（不使用 LLM 客户端）
        was_fixed = validate_and_fix_file_mermaid(temp_file, None, "测试文档")

        print(f"✅ 修复结果: {'已修复' if was_fixed else '无需修复'}")

        print("\n📋 修复后内容:")
        with open(temp_file, "r", encoding="utf-8") as f:
            print(f.read())

    finally:
        # 清理临时文件
        if os.path.exists(temp_file):
            os.unlink(temp_file)
            print(f"🗑️ 已删除临时文件: {temp_file}")


if __name__ == "__main__":
    test_mermaid_fix()
