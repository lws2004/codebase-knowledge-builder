"""实时 Mermaid 验证装饰器

在 LLM 生成内容后立即验证 Mermaid 图表，确保语法正确。
"""

import re
from functools import wraps
from typing import Any, Callable, List, Tuple

from .logger import log_and_notify
from .mermaid_validator import validate_mermaid_syntax_sync


def validate_mermaid_in_content(auto_fix: bool = True, max_retries: int = 2):
    """装饰器：验证生成内容中的 Mermaid 图表

    Args:
        auto_fix: 是否自动修复语法错误
        max_retries: 最大重试次数

    Returns:
        装饰器函数
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            """异步包装器"""
            # 执行原函数
            result = await func(*args, **kwargs)

            # 如果结果包含内容，验证其中的 Mermaid 图表
            if isinstance(result, tuple) and len(result) >= 3:
                content, quality_score, success = result[:3]
                if success and content:
                    validated_content, was_fixed = _validate_and_fix_content(
                        content, auto_fix, max_retries, args, kwargs
                    )
                    if was_fixed:
                        log_and_notify("检测到 Mermaid 语法错误并已修复", "info")
                        # 重新评估质量（如果有评估函数）
                        if hasattr(args[0], "_evaluate_quality"):
                            quality_score = args[0]._evaluate_quality(validated_content)
                    return (validated_content, quality_score, success) + result[3:]

            return result

        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            """同步包装器"""
            # 执行原函数
            result = func(*args, **kwargs)

            # 如果结果包含内容，验证其中的 Mermaid 图表
            if isinstance(result, tuple) and len(result) >= 3:
                content, quality_score, success = result[:3]
                if success and content:
                    validated_content, was_fixed = _validate_and_fix_content(
                        content, auto_fix, max_retries, args, kwargs
                    )
                    if was_fixed:
                        log_and_notify("检测到 Mermaid 语法错误并已修复", "info")
                        # 重新评估质量（如果有评估函数）
                        if hasattr(args[0], "_evaluate_quality"):
                            quality_score = args[0]._evaluate_quality(validated_content)
                    return (validated_content, quality_score, success) + result[3:]

            return result

        # 根据函数是否为协程选择包装器
        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def _validate_and_fix_content(
    content: str, auto_fix: bool, max_retries: int, args: tuple, kwargs: dict
) -> Tuple[str, bool]:
    """验证并修复内容中的 Mermaid 图表

    Args:
        content: 原始内容
        auto_fix: 是否自动修复
        max_retries: 最大重试次数
        args: 原函数参数
        kwargs: 原函数关键字参数

    Returns:
        (修复后的内容, 是否进行了修复)
    """
    # 查找所有 Mermaid 代码块
    mermaid_pattern = r"```mermaid\n((?:(?!```)[\s\S])*?)\n```"
    mermaid_blocks = re.findall(mermaid_pattern, content, re.DOTALL)

    if not mermaid_blocks:
        return content, False

    fixed_content = content
    was_fixed = False

    for block in mermaid_blocks:
        is_valid, errors = validate_mermaid_syntax_sync(block.strip())

        if not is_valid:
            log_and_notify(f"检测到 Mermaid 语法错误: {errors}", "warning")

            if auto_fix:
                # 尝试自动修复
                fixed_block = _auto_fix_mermaid_block(block.strip())

                # 验证修复结果
                is_fixed_valid, _ = validate_mermaid_syntax_sync(fixed_block)

                if is_fixed_valid:
                    # 替换原内容中的错误块
                    fixed_content = fixed_content.replace(
                        f"```mermaid\n{block}\n```", f"```mermaid\n{fixed_block}\n```"
                    )
                    was_fixed = True
                    log_and_notify("Mermaid 图表已自动修复", "info")
                else:
                    log_and_notify("自动修复失败，保留原图表", "warning")

    return fixed_content, was_fixed


def _auto_fix_mermaid_block(mermaid_content: str) -> str:
    """自动修复 Mermaid 图表中的常见语法错误

    Args:
        mermaid_content: 原始 Mermaid 内容

    Returns:
        修复后的 Mermaid 内容
    """
    import re

    fixed_content = mermaid_content

    # 1. 移除节点标签中的引号
    # 将 NodeName["标签"] 改为 NodeName[标签]
    fixed_content = re.sub(r'(\w+)\["([^"]*?)"\]', r"\1[\2]", fixed_content)

    # 2. 移除节点标签中的括号
    # 将 NodeName[标签(说明)] 改为 NodeName[标签说明]
    fixed_content = re.sub(r"(\w+)\[([^]]*?)\(([^)]*?)\)", r"\1[\2\3]", fixed_content)

    # 3. 移除节点标签中的大括号
    # 将 NodeName[标签{内容}] 改为 NodeName[标签内容]
    fixed_content = re.sub(r"(\w+)\[([^]]*?)\{([^}]*?)\}", r"\1[\2\3]", fixed_content)

    # 4. 修复嵌套方括号
    # 将 NodeName[NodeName[标签]] 改为 NodeName[标签]
    fixed_content = re.sub(r"(\w+)\[\1\[([^]]*?)\]\]", r"\1[\2]", fixed_content)

    # 5. 移除行尾分号
    fixed_content = re.sub(r";\s*$", "", fixed_content, flags=re.MULTILINE)

    # 6. 修复 [|text|text] 格式
    fixed_content = re.sub(r"\[\|([^|]*?)\|([^|]*?)\]", r"[\1]", fixed_content)

    # 7. 修复饼图语法错误
    # 将单独的 "pie" 改为 "pie title 标题"
    if re.search(r"^pie\s*$", fixed_content, re.MULTILINE):
        fixed_content = re.sub(r"^pie\s*$", "pie title 数据分布", fixed_content, flags=re.MULTILINE)

    # 8. 修复图表类型声明错误
    # 确保图表类型声明正确
    if not re.search(
        r"^(graph|flowchart|sequenceDiagram|classDiagram|stateDiagram|gitgraph|timeline|mindmap|pie)",
        fixed_content,
        re.MULTILINE,
    ):
        # 如果没有有效的图表类型声明，添加一个
        if "title" in fixed_content.lower() and ("pie" in fixed_content.lower() or "数据" in fixed_content):
            fixed_content = "pie title 数据分布\n" + fixed_content
        else:
            fixed_content = "graph TD\n" + fixed_content

    return fixed_content


def extract_mermaid_blocks(content: str) -> List[str]:
    """从内容中提取所有 Mermaid 代码块

    Args:
        content: 文档内容

    Returns:
        Mermaid 代码块列表
    """
    mermaid_pattern = r"```mermaid\n((?:(?!```)[\s\S])*?)\n```"
    return re.findall(mermaid_pattern, content, re.DOTALL)


def validate_all_mermaid_in_content(content: str) -> Tuple[bool, List[str]]:
    """验证内容中的所有 Mermaid 图表

    Args:
        content: 文档内容

    Returns:
        (是否全部有效, 错误列表)
    """
    mermaid_blocks = extract_mermaid_blocks(content)

    if not mermaid_blocks:
        return True, []

    all_errors = []
    all_valid = True

    for i, block in enumerate(mermaid_blocks):
        is_valid, errors = validate_mermaid_syntax_sync(block.strip())
        if not is_valid:
            all_valid = False
            all_errors.extend([f"图表 {i + 1}: {error}" for error in errors])

    return all_valid, all_errors


def get_mermaid_syntax_guidelines() -> str:
    """获取 Mermaid 语法指导原则

    Returns:
        语法指导原则文本
    """
    return """
**Mermaid语法规范**
- 节点标签使用方括号格式：NodeName[节点标签]
- 不要在节点标签中使用引号：错误 NodeName["标签"] ✗，正确 NodeName[标签] ✓
- 不要在节点标签中使用括号：错误 NodeName[标签(说明)] ✗，正确 NodeName[标签说明] ✓
- 不要在节点标签中使用大括号：错误 NodeName[标签{内容}] ✗，正确 NodeName[标签内容] ✓
- 不要使用嵌套方括号：错误 NodeName[NodeName[标签]] ✗，正确 NodeName[标签] ✓
- 行末不要使用分号
- 中文字符可以直接使用，无需特殊处理
"""
