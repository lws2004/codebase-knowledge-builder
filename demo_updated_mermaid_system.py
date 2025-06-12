#!/usr/bin/env python3
"""演示更新后的 Mermaid 验证和修复系统"""

from src.utils.mermaid_realtime_validator import (
    _auto_fix_mermaid_block,
    extract_mermaid_blocks,
    get_mermaid_syntax_guidelines,
    validate_all_mermaid_in_content,
)
from src.utils.mermaid_regenerator import validate_and_regenerate_mermaid
from src.utils.mermaid_validator import validate_mermaid_syntax_sync


def demo_enhanced_validation():
    """演示增强的验证功能"""
    print("🔍 演示增强的 Mermaid 验证功能")
    print("=" * 60)

    # 测试各种语法错误
    test_cases = [
        {
            "name": "引号错误",
            "mermaid": """graph TD
    A["用户"] --> B["系统"]
    B --> C["数据库"]""",
            "expected_errors": ["节点标签中包含引号"],
        },
        {
            "name": "括号错误",
            "mermaid": """graph TD
    A[用户(客户端)] --> B[系统(服务器)]
    B --> C[数据库(MySQL)]""",
            "expected_errors": ["节点标签中包含括号"],
        },
        {
            "name": "大括号错误",
            "mermaid": """graph TD
    A[用户{客户端}] --> B[系统{服务器}]
    B --> C[数据库{MySQL}]""",
            "expected_errors": ["节点标签中包含大括号"],
        },
        {
            "name": "行尾分号错误",
            "mermaid": """graph TD
    A[用户] --> B[系统];
    B --> C[数据库];""",
            "expected_errors": ["包含行尾分号"],
        },
        {
            "name": "正确的图表",
            "mermaid": """graph TD
    A[用户] --> B[系统]
    B --> C[数据库]
    C --> D[响应]""",
            "expected_errors": [],
        },
    ]

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n📋 测试案例 {i}: {test_case['name']}")
        print("-" * 40)
        print("图表内容:")
        print(test_case["mermaid"])

        is_valid, errors = validate_mermaid_syntax_sync(test_case["mermaid"])

        print(f"验证结果: {'✅ 有效' if is_valid else '❌ 无效'}")
        if errors:
            print(f"检测到的错误: {errors}")

        # 检查是否符合预期
        if test_case["expected_errors"]:
            if not is_valid and any(expected in str(errors) for expected in test_case["expected_errors"]):
                print("✅ 错误检测符合预期")
            else:
                print("❌ 错误检测不符合预期")
        else:
            if is_valid:
                print("✅ 正确图表验证通过")
            else:
                print("❌ 正确图表验证失败")


def demo_auto_fix():
    """演示自动修复功能"""
    print("\n\n🛠️ 演示自动修复功能")
    print("=" * 60)

    problematic_mermaid = """graph TD
    A["用户代码"] --> B["requests.compat"]
    B --> C["模块(说明)"]
    C --> D["结果{内容}"];
    E[E[嵌套错误]]"""

    print("原始有问题的图表:")
    print(problematic_mermaid)

    print("\n🔧 自动修复中...")
    fixed_mermaid = _auto_fix_mermaid_block(problematic_mermaid)

    print("\n修复后的图表:")
    print(fixed_mermaid)

    # 验证修复结果
    is_valid, errors = validate_mermaid_syntax_sync(fixed_mermaid)
    print(f"\n修复结果验证: {'✅ 有效' if is_valid else '❌ 仍有错误'}")
    if errors:
        print(f"剩余错误: {errors}")


def demo_content_validation():
    """演示文档内容验证"""
    print("\n\n📄 演示文档内容验证")
    print("=" * 60)

    document_content = """# 系统架构文档

## 概述
这是一个示例文档，包含多个 Mermaid 图表。

## 系统架构

```mermaid
graph TD
    A["用户"] --> B["API网关"]
    B --> C["业务服务"]
    C --> D["数据库"]
```

## 数据流程

```mermaid
sequenceDiagram
    participant User["用户"]
    participant API["API"]
    participant DB["数据库"]
    User->>API: 请求数据
    API->>DB: 查询
    DB-->>API: 返回结果
    API-->>User: 响应
```

## 总结
以上是系统的主要组件。
"""

    print("文档内容:")
    print(document_content)

    # 提取 Mermaid 块
    mermaid_blocks = extract_mermaid_blocks(document_content)
    print(f"\n📊 检测到 {len(mermaid_blocks)} 个 Mermaid 图表")

    # 验证所有图表
    all_valid, all_errors = validate_all_mermaid_in_content(document_content)
    print(f"整体验证结果: {'✅ 全部有效' if all_valid else '❌ 存在错误'}")
    if all_errors:
        print(f"错误详情: {all_errors}")


def demo_integration_with_llm():
    """演示与 LLM 集成的修复功能"""
    print("\n\n🤖 演示与 LLM 集成的修复功能")
    print("=" * 60)

    content_with_errors = """# API 文档

## 请求流程

```mermaid
graph TD
    A["客户端(Client)"] --> B["API网关(Gateway)"]
    B --> C{"验证(Valid)"}
    C -->|有效| D["处理(Process)"]
    C -->|无效| E["错误(Error)"];
    D --> F["响应(Response)"]
```

这个图表展示了 API 请求的处理流程。
"""

    print("包含错误的文档:")
    print(content_with_errors)

    print("\n🔍 检测错误...")
    all_valid, all_errors = validate_all_mermaid_in_content(content_with_errors)

    if not all_valid:
        print(f"❌ 检测到错误: {all_errors}")
        print("\n🛠️ 尝试自动修复...")

        # 使用验证和重新生成功能（不使用 LLM，仅自动修复）
        fixed_content, was_fixed = validate_and_regenerate_mermaid(content_with_errors)

        if was_fixed:
            print("✅ 已自动修复")
            print("\n修复后的内容:")
            print(fixed_content)

            # 再次验证
            final_valid, final_errors = validate_all_mermaid_in_content(fixed_content)
            print(f"\n最终验证结果: {'✅ 修复成功' if final_valid else '❌ 仍有问题'}")
            if final_errors:
                print(f"剩余错误: {final_errors}")
        else:
            print("❌ 自动修复失败")
    else:
        print("✅ 所有图表语法正确")


def demo_syntax_guidelines():
    """演示语法指导原则"""
    print("\n\n📚 Mermaid 语法指导原则")
    print("=" * 60)
    print(get_mermaid_syntax_guidelines())

    print("\n✅ 正确示例:")
    correct_examples = [
        "graph TD\n    A[用户] --> B[系统]\n    B --> C[数据库]",
        "sequenceDiagram\n    participant User[用户]\n    participant API[接口]\n    User->>API: 请求",
        "flowchart LR\n    Start[开始] --> Process[处理]\n    Process --> End[结束]",
    ]

    for i, example in enumerate(correct_examples, 1):
        print(f"\n示例 {i}:")
        print(example)
        is_valid, _ = validate_mermaid_syntax_sync(example)
        print(f"验证: {'✅ 正确' if is_valid else '❌ 错误'}")

    print("\n❌ 错误示例:")
    wrong_examples = [
        'graph TD\n    A["用户"] --> B["系统"]  # 包含引号',
        "graph TD\n    A[用户(客户端)] --> B[系统]  # 包含括号",
        "graph TD\n    A[用户] --> B[系统];  # 行尾分号",
    ]

    for i, example in enumerate(wrong_examples, 1):
        parts = example.split("  # ")
        code = parts[0]
        comment = parts[1] if len(parts) > 1 else ""
        print(f"\n错误示例 {i}: {comment}")
        print(code)
        is_valid, errors = validate_mermaid_syntax_sync(code)
        print(f"验证: {'✅ 正确' if is_valid else '❌ 错误'}")
        if errors:
            print(f"错误: {errors}")


def main():
    """主函数"""
    print("🎯 更新后的 Mermaid 验证和修复系统演示")
    print("=" * 80)
    print()

    # 运行各种演示
    demo_enhanced_validation()
    demo_auto_fix()
    demo_content_validation()
    demo_integration_with_llm()
    demo_syntax_guidelines()

    print("\n\n🎉 演示完成！")
    print("\n📋 系统更新总结:")
    print("✅ 增强的 Mermaid 语法验证器")
    print("✅ 实时验证装饰器")
    print("✅ 自动修复功能")
    print("✅ 更新的 prompt 模板")
    print("✅ 集成到主流程")
    print("✅ 完整的配置支持")
    print("✅ 预防性错误检测")


if __name__ == "__main__":
    main()
