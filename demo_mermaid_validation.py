#!/usr/bin/env python3
"""演示 Mermaid 验证和重新生成功能"""

import os
import tempfile

from src.utils.llm_wrapper.llm_client import LLMClient
from src.utils.mermaid_regenerator import validate_and_regenerate_mermaid
from src.utils.mermaid_validator import validate_mermaid_syntax_sync


def demo_basic_validation():
    """演示基本的 Mermaid 验证功能"""
    print("🔍 演示基本 Mermaid 验证功能")
    print("=" * 50)

    # 测试有效的 Mermaid 图表
    valid_mermaid = """
graph TD
    A[开始] --> B[处理数据]
    B --> C{是否成功}
    C -->|是| D[保存结果]
    C -->|否| E[错误处理]
    D --> F[结束]
    E --> F
"""

    print("✅ 测试有效的 Mermaid 图表:")
    print(valid_mermaid)
    is_valid, errors = validate_mermaid_syntax_sync(valid_mermaid)
    print(f"验证结果: {'✅ 有效' if is_valid else '❌ 无效'}")
    if errors:
        print(f"错误: {errors}")
    print()

    # 测试无效的 Mermaid 图表
    invalid_mermaid = """
graph TD
    A[A[嵌套错误的方括号]]
    B[文本(包含括号)]
    C --> D;
"""

    print("❌ 测试无效的 Mermaid 图表:")
    print(invalid_mermaid)
    is_valid, errors = validate_mermaid_syntax_sync(invalid_mermaid)
    print(f"验证结果: {'✅ 有效' if is_valid else '❌ 无效'}")
    if errors:
        print(f"错误: {errors}")
    print()


def demo_content_validation():
    """演示文档内容中的 Mermaid 验证"""
    print("📄 演示文档内容中的 Mermaid 验证")
    print("=" * 50)

    # 包含多个 Mermaid 图表的文档内容
    content_with_mermaid = """
# 系统架构文档

## 概述

这是一个示例系统的架构文档。

## 系统流程图

```mermaid
graph TD
    A[用户请求] --> B[API网关]
    B --> C[业务逻辑层]
    C --> D[数据库]
    D --> C
    C --> B
    B --> A
```

## 错误的图表示例

```mermaid
graph TD
    A[A[嵌套错误]]
    B[文本(包含括号)]
    C --> D;
```

## 类图示例

```mermaid
classDiagram
    class User {
        +String name
        +String email
        +login()
        +logout()
    }
    
    class Order {
        +int id
        +Date date
        +calculate()
    }
    
    User --> Order
```

## 结论

以上是系统的主要架构图表。
"""

    print("📝 原始文档内容:")
    print(content_with_mermaid)
    print()

    # 验证内容中的 Mermaid 图表
    print("🔍 验证结果:")
    fixed_content, was_fixed = validate_and_regenerate_mermaid(content_with_mermaid)

    if was_fixed:
        print("✅ 检测到错误并已修复")
        print("\n📝 修复后的内容:")
        print(fixed_content)
    else:
        print("✅ 所有 Mermaid 图表语法正确，无需修复")
    print()


def demo_with_llm():
    """演示使用 LLM 进行 Mermaid 重新生成"""
    print("🤖 演示使用 LLM 进行 Mermaid 重新生成")
    print("=" * 50)

    # 检查是否有 LLM 配置
    if not os.path.exists(".env"):
        print("❌ 未找到 .env 文件，跳过 LLM 演示")
        return

    try:
        # 加载环境变量
        from dotenv import load_dotenv

        load_dotenv()

        # 创建 LLM 配置
        llm_config = {
            "model": os.getenv("LLM_MODEL", "qwen/qwen-2.5-72b-instruct"),
            "api_key": os.getenv("LLM_API_KEY"),
            "base_url": os.getenv("LLM_BASE_URL"),
            "max_tokens": 1500,
        }

        if not llm_config["api_key"]:
            print("❌ 未找到 LLM API 密钥，跳过 LLM 演示")
            return

        # 初始化 LLM 客户端
        llm_client = LLMClient(llm_config)

        # 包含错误 Mermaid 图表的内容
        content_with_errors = """
# API 文档

## 请求流程

```mermaid
graph TD
    A[客户端请求] --> B[API网关(验证)]
    B --> C{请求是否有效}
    C -->|有效| D[业务处理(逻辑)]
    C -->|无效| E[返回错误(400)]
    D --> F[数据库操作(CRUD)]
    F --> G[返回结果(JSON)]
    E --> H[记录日志(错误)]
    G --> I[客户端接收]
    H --> I
```

这个图表展示了 API 请求的完整流程。
"""

        print("📝 包含错误的原始内容:")
        print(content_with_errors)
        print()

        print("🤖 使用 LLM 进行修复...")
        fixed_content, was_fixed = validate_and_regenerate_mermaid(
            content_with_errors, llm_client, "API 文档中的请求流程图"
        )

        if was_fixed:
            print("✅ LLM 已修复 Mermaid 图表")
            print("\n📝 修复后的内容:")
            print(fixed_content)
        else:
            print("✅ Mermaid 图表语法正确，无需修复")

    except Exception as e:
        print(f"❌ LLM 演示失败: {str(e)}")


def demo_file_validation():
    """演示文件级别的 Mermaid 验证"""
    print("📁 演示文件级别的 Mermaid 验证")
    print("=" * 50)

    # 创建临时文件
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write("""---
title: 测试文档
---

# 测试文档

## 架构图

```mermaid
graph TD
    A[开始] --> B[处理]
    B --> C[结束]
```

## 错误图表

```mermaid
graph TD
    A[A[错误嵌套]]
    B --> C;
```
""")
        temp_file = f.name

    try:
        print(f"📄 创建临时文件: {temp_file}")

        # 读取文件内容
        with open(temp_file, "r", encoding="utf-8") as f:
            content = f.read()

        print("📝 文件内容:")
        print(content)
        print()

        # 验证和修复
        fixed_content, was_fixed = validate_and_regenerate_mermaid(content)

        if was_fixed:
            print("✅ 检测到错误并已修复")

            # 写回文件
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(fixed_content)

            print(f"💾 已将修复后的内容写回文件: {temp_file}")

            # 显示修复后的内容
            print("\n📝 修复后的内容:")
            print(fixed_content)
        else:
            print("✅ 文件中的 Mermaid 图表语法正确，无需修复")

    finally:
        # 清理临时文件
        if os.path.exists(temp_file):
            os.unlink(temp_file)
            print(f"🗑️ 已删除临时文件: {temp_file}")


def main():
    """主函数"""
    print("🎯 Mermaid 验证和重新生成功能演示")
    print("=" * 60)
    print()

    # 运行各种演示
    demo_basic_validation()
    print("\n" + "=" * 60 + "\n")

    demo_content_validation()
    print("\n" + "=" * 60 + "\n")

    demo_file_validation()
    print("\n" + "=" * 60 + "\n")

    demo_with_llm()

    print("\n🎉 演示完成！")
    print("\n📋 功能总结:")
    print("✅ 基本 Mermaid 语法验证")
    print("✅ 文档内容中的 Mermaid 验证")
    print("✅ 文件级别的 Mermaid 验证和修复")
    print("✅ 使用 LLM 进行智能重新生成")
    print("✅ 支持多种 Mermaid 图表类型")
    print("✅ 自动备份和错误恢复")


if __name__ == "__main__":
    main()
