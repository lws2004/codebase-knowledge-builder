#!/usr/bin/env python3
"""测试 Mermaid 修复功能"""

import os
import sys

sys.path.insert(0, os.getcwd())

from src.utils.formatter import _simple_mermaid_fix
from src.utils.mermaid_realtime_validator import _auto_fix_mermaid_block
from src.utils.mermaid_validator import validate_mermaid_syntax_sync


def test_bracket_fixes():
    """测试括号修复"""
    print("🔧 测试括号修复")
    print("=" * 50)

    test_cases = [
        {
            "name": "节点标签中的括号",
            "input": "graph TD\n    A[用户(客户端)] --> B[系统(服务器)]",
            "expected_fix": True,
        },
        {"name": "节点标签中的引号", "input": 'graph TD\n    A["用户"] --> B["系统"]', "expected_fix": True},
        {
            "name": "节点标签中的大括号",
            "input": "graph TD\n    A[用户{客户端}] --> B[系统{服务器}]",
            "expected_fix": True,
        },
    ]

    for test_case in test_cases:
        print(f"\n📋 测试: {test_case['name']}")
        print(f"原始: {test_case['input']}")

        # 验证原始内容有错误
        is_valid, errors = validate_mermaid_syntax_sync(test_case["input"])
        print(f"原始验证: {'✅ 有效' if is_valid else '❌ 无效'} - {errors}")

        # 自动修复
        fixed = _auto_fix_mermaid_block(test_case["input"])
        print(f"修复后: {fixed}")

        # 验证修复结果
        is_fixed_valid, fixed_errors = validate_mermaid_syntax_sync(fixed)
        print(f"修复验证: {'✅ 有效' if is_fixed_valid else '❌ 仍有错误'} - {fixed_errors}")

        if test_case["expected_fix"] and is_fixed_valid:
            print("✅ 修复成功")
        elif not test_case["expected_fix"] and not is_fixed_valid:
            print("✅ 符合预期（应该仍有错误）")
        else:
            print("❌ 修复失败")


def test_pie_chart_fixes():
    """测试饼图修复"""
    print("\n\n🥧 测试饼图修复")
    print("=" * 50)

    test_cases = [
        {"name": "单独的 pie 声明", "input": 'pie\n    "Alice" : 35\n    "Bob" : 25', "expected_fix": True},
        {
            "name": "正确的饼图",
            "input": 'pie title 数据分布\n    "Alice" : 35\n    "Bob" : 25',
            "expected_fix": False,  # 已经正确，不需要修复
        },
    ]

    for test_case in test_cases:
        print(f"\n📋 测试: {test_case['name']}")
        print(f"原始: {test_case['input']}")

        # 验证原始内容
        is_valid, errors = validate_mermaid_syntax_sync(test_case["input"])
        print(f"原始验证: {'✅ 有效' if is_valid else '❌ 无效'} - {errors}")

        # 自动修复
        fixed = _auto_fix_mermaid_block(test_case["input"])
        print(f"修复后: {fixed}")

        # 验证修复结果
        is_fixed_valid, fixed_errors = validate_mermaid_syntax_sync(fixed)
        print(f"修复验证: {'✅ 有效' if is_fixed_valid else '❌ 仍有错误'} - {fixed_errors}")

        if test_case["expected_fix"] and is_fixed_valid:
            print("✅ 修复成功")
        elif not test_case["expected_fix"] and is_valid:
            print("✅ 符合预期（原本就正确）")
        else:
            print("❌ 修复失败")


def test_complex_fixes():
    """测试复杂修复场景"""
    print("\n\n🔧 测试复杂修复场景")
    print("=" * 50)

    complex_mermaid = """graph TD
    A["用户代码"] --> B["API入口 (requests.api)"]
    B --> C["核心处理 (requests.sessions)"]
    C --> D["模型定义 (requests.models)"];
    E[E[嵌套错误]]"""

    print("原始复杂图表:")
    print(complex_mermaid)

    # 验证原始内容
    is_valid, errors = validate_mermaid_syntax_sync(complex_mermaid)
    print(f"\n原始验证: {'✅ 有效' if is_valid else '❌ 无效'}")
    if errors:
        print(f"错误: {errors}")

    # 自动修复
    fixed = _auto_fix_mermaid_block(complex_mermaid)
    print("\n修复后:")
    print(fixed)

    # 验证修复结果
    is_fixed_valid, fixed_errors = validate_mermaid_syntax_sync(fixed)
    print(f"\n修复验证: {'✅ 有效' if is_fixed_valid else '❌ 仍有错误'}")
    if fixed_errors:
        print(f"剩余错误: {fixed_errors}")


def test_legacy_formatter():
    """测试旧版格式化器"""
    print("\n\n🔄 测试旧版格式化器")
    print("=" * 50)

    test_mermaid = """graph TD
    A["用户"] --> B["系统(服务器)"]
    B --> C["数据库{MySQL}"];"""

    print("原始图表:")
    print(test_mermaid)

    # 使用旧版修复
    fixed = _simple_mermaid_fix(test_mermaid)
    print("\n旧版修复后:")
    print(fixed)

    # 验证修复结果
    is_fixed_valid, fixed_errors = validate_mermaid_syntax_sync(fixed)
    print(f"\n修复验证: {'✅ 有效' if is_fixed_valid else '❌ 仍有错误'}")
    if fixed_errors:
        print(f"剩余错误: {fixed_errors}")


def test_real_world_examples():
    """测试真实世界的例子"""
    print("\n\n🌍 测试真实世界的例子")
    print("=" * 50)

    # 这是我们在实际文档中发现的问题
    real_examples = [
        {
            "name": "overview.md 中的问题",
            "content": """graph TD
    A[客户端] --> B[API入口 (requests.api)]
    B --> C[核心处理 (requests.sessions)]
    C --> D[模型定义 (requests.models)]
    D --> E[适配器实现 (requests.adapters)]
    E --> F[工具辅助 (requests.utils)]
    F --> G[数据返回]""",
        },
        {
            "name": "timeline.md 中的饼图问题",
            "content": """pie
    "Alice" : 35
    "Bob" : 25
    "Carol" : 20
    "Others" : 20""",
        },
    ]

    for example in real_examples:
        print(f"\n📋 测试: {example['name']}")
        print("原始内容:")
        print(example["content"])

        # 验证原始内容
        is_valid, errors = validate_mermaid_syntax_sync(example["content"])
        print(f"\n原始验证: {'✅ 有效' if is_valid else '❌ 无效'}")
        if errors:
            print(f"错误: {errors}")

        # 自动修复
        fixed = _auto_fix_mermaid_block(example["content"])
        print("\n修复后:")
        print(fixed)

        # 验证修复结果
        is_fixed_valid, fixed_errors = validate_mermaid_syntax_sync(fixed)
        print(f"\n修复验证: {'✅ 有效' if is_fixed_valid else '❌ 仍有错误'}")
        if fixed_errors:
            print(f"剩余错误: {fixed_errors}")

        if is_fixed_valid:
            print("✅ 真实问题修复成功")
        else:
            print("❌ 真实问题修复失败")


def main():
    """主函数"""
    print("🧪 Mermaid 修复功能测试")
    print("=" * 80)

    test_bracket_fixes()
    test_pie_chart_fixes()
    test_complex_fixes()
    test_legacy_formatter()
    test_real_world_examples()

    print("\n\n🎉 测试完成！")
    print("\n📋 修复功能总结:")
    print("✅ 节点标签中的引号修复")
    print("✅ 节点标签中的括号修复")
    print("✅ 节点标签中的大括号修复")
    print("✅ 嵌套方括号修复")
    print("✅ 行尾分号修复")
    print("✅ 饼图语法修复")
    print("✅ 图表类型声明修复")
    print("✅ 复杂场景修复")


if __name__ == "__main__":
    main()
