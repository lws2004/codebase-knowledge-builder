"""Mermaid 图表重新生成器

当 Mermaid 语法检查失败时，使用 LLM 重新生成正确的图表。
"""

import re
from typing import List, Optional, Tuple

from .logger import log_and_notify
from .mermaid_validator import validate_mermaid_syntax_sync


class MermaidRegenerator:
    """Mermaid 图表重新生成器"""

    def __init__(self, llm_client=None):
        """初始化重新生成器

        Args:
            llm_client: LLM 客户端实例
        """
        self.llm_client = llm_client
        self.max_retries = 3

    def regenerate_mermaid_content(self, content: str, context: Optional[str] = None) -> str:
        """重新生成内容中的所有 Mermaid 图表

        Args:
            content: 包含 Mermaid 图表的内容
            context: 上下文信息，用于帮助 LLM 理解图表用途

        Returns:
            修复后的内容
        """
        # 查找所有 Mermaid 代码块
        mermaid_pattern = r"```mermaid\n((?:(?!```)[\s\S])*?)\n```"

        def regenerate_block(match):
            mermaid_content = match.group(1).strip()

            if not mermaid_content:
                return match.group(0)

            # 验证当前语法
            is_valid, errors = validate_mermaid_syntax_sync(mermaid_content)

            if is_valid:
                log_and_notify("Mermaid 图表语法正确，无需重新生成", "debug")
                return match.group(0)

            log_and_notify(f"检测到 Mermaid 语法错误: {errors}", "warning")

            # 重新生成图表
            regenerated_content = self._regenerate_single_mermaid(mermaid_content, errors, context)

            if regenerated_content:
                return f"```mermaid\n{regenerated_content}\n```"
            else:
                log_and_notify("重新生成失败，保留原图表", "warning")
                return match.group(0)

        # 应用重新生成到所有 Mermaid 代码块
        fixed_content = re.sub(mermaid_pattern, regenerate_block, content, flags=re.DOTALL)

        return fixed_content

    def _regenerate_single_mermaid(
        self, mermaid_content: str, errors: List[str], context: Optional[str] = None
    ) -> Optional[str]:
        """重新生成单个 Mermaid 图表

        Args:
            mermaid_content: 原始 Mermaid 内容
            errors: 语法错误列表
            context: 上下文信息

        Returns:
            重新生成的 Mermaid 内容，如果失败则返回 None
        """
        if not self.llm_client:
            log_and_notify("没有可用的 LLM 客户端，无法重新生成", "error")
            return None

        for attempt in range(self.max_retries):
            try:
                log_and_notify(f"尝试重新生成 Mermaid 图表 (第 {attempt + 1}/{self.max_retries} 次)", "info")

                # 构建提示
                prompt = self._build_regeneration_prompt(mermaid_content, errors, context)

                # 调用 LLM
                response = self.llm_client.generate_text(prompt, max_tokens=1500)

                # 清理响应
                cleaned_response = self._clean_llm_response(response)

                if not cleaned_response:
                    log_and_notify(f"第 {attempt + 1} 次尝试：LLM 返回空内容", "warning")
                    continue

                # 验证重新生成的内容
                is_valid, new_errors = validate_mermaid_syntax_sync(cleaned_response)

                if is_valid:
                    log_and_notify(f"第 {attempt + 1} 次尝试：重新生成成功", "info")
                    return cleaned_response
                else:
                    log_and_notify(f"第 {attempt + 1} 次尝试：仍有语法错误: {new_errors}", "warning")

            except Exception as e:
                log_and_notify(f"第 {attempt + 1} 次尝试失败: {str(e)}", "error")

        log_and_notify("所有重新生成尝试都失败了", "error")
        return None

    def _build_regeneration_prompt(self, mermaid_content: str, errors: List[str], context: Optional[str] = None) -> str:
        """构建重新生成的提示

        Args:
            mermaid_content: 原始 Mermaid 内容
            errors: 语法错误列表
            context: 上下文信息

        Returns:
            LLM 提示
        """
        context_info = f"\n\n上下文信息：\n{context}" if context else ""

        errors_info = "\n".join(f"- {error}" for error in errors)

        prompt = f"""请重新生成以下 Mermaid 图表，修复所有语法错误：

原始图表：
```mermaid
{mermaid_content}
```

检测到的语法错误：
{errors_info}

{context_info}

**重要：Mermaid语法规范**
- 节点标签使用方括号格式：NodeName[节点标签]
- 不要在节点标签中使用引号：错误 NodeName["标签"] ✗，正确 NodeName[标签] ✓
- 不要在节点标签中使用括号：错误 NodeName[标签(说明)] ✗，正确 NodeName[标签说明] ✓
- 不要在节点标签中使用大括号：错误 NodeName[标签{{内容}}] ✗，正确 NodeName[标签内容] ✓
- 不要使用嵌套方括号：错误 NodeName[NodeName[标签]] ✗，正确 NodeName[标签] ✓
- 行末不要使用分号
- 中文字符可以直接使用，无需特殊处理

重新生成要求：
1. 保持图表的原始含义和结构
2. 修复所有语法错误
3. 严格遵循上述 Mermaid 语法规范
4. 支持中文字符显示
5. 使用简洁清晰的节点标签
6. 避免使用特殊符号和复杂嵌套

常见修复规则：
- 严格按照语法规范修复节点标签
- 修复嵌套方括号问题
- 确保箭头语法正确
- 移除行尾分号
- 确保图表类型声明正确

请只返回修复后的 Mermaid 代码（不包含 ```mermaid 标记），不要添加任何解释："""

        return prompt

    def _clean_llm_response(self, response: str) -> str:
        """清理 LLM 响应

        Args:
            response: LLM 原始响应

        Returns:
            清理后的 Mermaid 内容
        """
        if not response:
            return ""

        # 移除可能的代码块标记
        cleaned = response.strip()

        # 移除 ```mermaid 开始标记
        if cleaned.startswith("```mermaid"):
            cleaned = cleaned[10:].strip()
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:].strip()

        # 移除 ``` 结束标记
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()

        # 移除多余的空行
        lines = [line.rstrip() for line in cleaned.split("\n")]
        cleaned = "\n".join(line for line in lines if line.strip() or not line)

        return cleaned.strip()


def regenerate_mermaid_in_content(content: str, llm_client=None, context: Optional[str] = None) -> str:
    """重新生成内容中的 Mermaid 图表（便捷函数）

    Args:
        content: 包含 Mermaid 图表的内容
        llm_client: LLM 客户端实例
        context: 上下文信息

    Returns:
        修复后的内容
    """
    regenerator = MermaidRegenerator(llm_client)
    return regenerator.regenerate_mermaid_content(content, context)


def validate_and_regenerate_mermaid(content: str, llm_client=None, context: Optional[str] = None) -> Tuple[str, bool]:
    """验证并重新生成 Mermaid 图表

    Args:
        content: 包含 Mermaid 图表的内容
        llm_client: LLM 客户端实例
        context: 上下文信息

    Returns:
        (修复后的内容, 是否进行了修复)
    """
    # 查找所有 Mermaid 代码块
    mermaid_pattern = r"```mermaid\n((?:(?!```)[\s\S])*?)\n```"
    mermaid_blocks = re.findall(mermaid_pattern, content, re.DOTALL)

    needs_regeneration = False

    # 检查是否有语法错误
    for block in mermaid_blocks:
        is_valid, _ = validate_mermaid_syntax_sync(block.strip())
        if not is_valid:
            needs_regeneration = True
            break

    if not needs_regeneration:
        log_and_notify("所有 Mermaid 图表语法正确，无需重新生成", "info")
        return content, False

    # 重新生成
    log_and_notify("检测到 Mermaid 语法错误，开始重新生成", "info")
    fixed_content = regenerate_mermaid_in_content(content, llm_client, context)

    return fixed_content, True


def validate_and_fix_file_mermaid(file_path: str, llm_client=None, context: Optional[str] = None) -> bool:
    """验证并修复文件中的 Mermaid 图表

    Args:
        file_path: 文件路径
        llm_client: LLM 客户端实例
        context: 上下文信息

    Returns:
        是否进行了修复
    """
    try:
        # 读取文件内容
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # 验证并修复 Mermaid 图表
        fixed_content, was_fixed = validate_and_regenerate_mermaid(content, llm_client, context)

        # 如果有修复，写回文件
        if was_fixed:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(fixed_content)
            log_and_notify(f"已修复文件中的 Mermaid 图表: {file_path}", "info")

        return was_fixed

    except Exception as e:
        log_and_notify(f"修复文件 Mermaid 图表时出错 {file_path}: {str(e)}", "error")
        return False
