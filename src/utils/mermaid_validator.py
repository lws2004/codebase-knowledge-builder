"""Mermaid 图表语法验证工具

使用真实的 Mermaid 渲染引擎来验证语法，而不是自定义逻辑。
为了避免主线程问题，使用进程池进行验证。
"""

import asyncio
import os
import subprocess
import tempfile
import threading
from typing import List, Optional, Tuple

from ..utils.logger import log_and_notify


def _validate_mermaid_in_process(mermaid_content: str) -> Tuple[bool, List[str]]:
    """在独立进程中验证 Mermaid 语法

    Args:
        mermaid_content: Mermaid 图表内容

    Returns:
        (是否有效, 错误列表)
    """
    try:
        # 使用 mermaid-cli 进行验证
        return _validate_with_mermaid_cli(mermaid_content)
    except Exception:
        # 回退到简单验证
        return _simple_validate_mermaid(mermaid_content)


def _validate_with_mermaid_cli(mermaid_content: str) -> Tuple[bool, List[str]]:
    """使用 mermaid-cli 验证语法

    Args:
        mermaid_content: Mermaid 图表内容

    Returns:
        (是否有效, 错误列表)
    """
    try:
        # 检查是否安装了 mermaid-cli
        result = subprocess.run(["mmdc", "--version"], capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            raise FileNotFoundError("mermaid-cli not found")

        # 创建临时文件
        with tempfile.NamedTemporaryFile(mode="w", suffix=".mmd", delete=False) as f:
            f.write(mermaid_content)
            input_file = f.name

        try:
            # 创建输出文件路径
            output_file = input_file.replace(".mmd", ".svg")

            # 运行 mermaid-cli 验证
            result = subprocess.run(
                ["mmdc", "-i", input_file, "-o", output_file, "--quiet"], capture_output=True, text=True, timeout=10
            )

            if result.returncode == 0:
                # 验证成功
                return True, []
            else:
                # 验证失败，解析错误信息
                error_msg = result.stderr.strip() or result.stdout.strip()
                return False, [error_msg] if error_msg else ["Unknown syntax error"]

        finally:
            # 清理临时文件
            for file_path in [input_file, output_file]:
                if os.path.exists(file_path):
                    os.unlink(file_path)

    except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError):
        # mermaid-cli 不可用，回退到简单验证
        return _simple_validate_mermaid(mermaid_content)


def _simple_validate_mermaid(mermaid_content: str) -> Tuple[bool, List[str]]:
    """简单的 Mermaid 语法验证

    Args:
        mermaid_content: Mermaid 图表内容

    Returns:
        (是否有效, 错误列表)
    """
    import re

    errors = []

    # 检查基本结构
    if not re.search(
        r"(graph|flowchart|sequenceDiagram|classDiagram|stateDiagram|gitgraph|timeline|mindmap)", mermaid_content
    ):
        errors.append("缺少有效的图表类型声明")

    # 检查常见语法错误
    if re.search(r"\[\|[^|]*\|[^|]*\]", mermaid_content):
        errors.append("包含无效的 [|text|text] 格式")

    if re.search(r"([A-Z])\[\1\[", mermaid_content):
        errors.append("包含嵌套方括号错误")

    if re.search(r'-->\s*[A-Z]\s*\([^)]*\)"\]', mermaid_content):
        errors.append("包含箭头语法错误")

    if re.search(r";\s*$", mermaid_content, re.MULTILINE):
        errors.append("包含行尾分号")

    # 检查节点标签中的特殊符号
    if re.search(r"\[([^]]*)\([^)]*\)", mermaid_content):
        errors.append("节点标签中包含括号")

    if re.search(r'\[([^]]*)"([^"]*)"', mermaid_content):
        errors.append("节点标签中包含引号")

    if re.search(r"\[([^]]*)\{([^}]*)\}", mermaid_content):
        errors.append("节点标签中包含大括号")

    return len(errors) == 0, errors


class MermaidValidator:
    """Mermaid 语法验证器（线程安全版本）"""

    def __init__(self):
        """初始化验证器"""
        self._executor = None
        self._lock = threading.Lock()

    def _get_executor(self):
        """获取进程池执行器

        Returns:
            进程池执行器
        """
        with self._lock:
            if self._executor is None:
                try:
                    # 使用进程池避免主线程问题
                    import concurrent.futures

                    self._executor = concurrent.futures.ProcessPoolExecutor(max_workers=2)
                    log_and_notify("Mermaid 验证器初始化成功（进程池模式）", "info")
                except Exception as e:
                    log_and_notify(f"进程池初始化失败，使用线程池: {str(e)}", "warning")
                    # 回退到线程池
                    self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
            return self._executor

    async def validate_mermaid_syntax(self, mermaid_content: str) -> Tuple[bool, List[str]]:
        """验证 Mermaid 图表语法

        Args:
            mermaid_content: Mermaid 图表内容

        Returns:
            (是否有效, 错误列表)
        """
        try:
            # 清理内容
            cleaned_content = mermaid_content.strip()
            if not cleaned_content:
                return False, ["内容为空"]

            # 使用进程池进行验证，避免主线程问题
            executor = self._get_executor()
            loop = asyncio.get_event_loop()

            # 在进程池中运行验证
            result = await loop.run_in_executor(executor, _validate_mermaid_in_process, cleaned_content)

            return result

        except Exception as e:
            log_and_notify(f"Mermaid 语法验证失败: {str(e)}", "error")
            # 回退到简单验证
            return _simple_validate_mermaid(mermaid_content)

    def close(self):
        """关闭执行器"""
        with self._lock:
            if self._executor:
                self._executor.shutdown(wait=False)
                self._executor = None


# 全局验证器实例
_validator_instance: Optional[MermaidValidator] = None


async def validate_mermaid_syntax(mermaid_content: str) -> Tuple[bool, List[str]]:
    """验证 Mermaid 图表语法（全局函数）

    Args:
        mermaid_content: Mermaid 图表内容

    Returns:
        (是否有效, 错误列表)
    """
    global _validator_instance

    if _validator_instance is None:
        _validator_instance = MermaidValidator()

    return await _validator_instance.validate_mermaid_syntax(mermaid_content)


def validate_mermaid_syntax_sync(mermaid_content: str) -> Tuple[bool, List[str]]:
    """同步版本的 Mermaid 语法验证

    Args:
        mermaid_content: Mermaid 图表内容

    Returns:
        (是否有效, 错误列表)
    """
    try:
        # 尝试在现有事件循环中运行
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 如果已经在事件循环中，使用简单验证
            return _simple_validate_mermaid(mermaid_content)
        else:
            # 创建新的事件循环
            return loop.run_until_complete(validate_mermaid_syntax(mermaid_content))
    except RuntimeError:
        # 没有事件循环，创建新的
        return asyncio.run(validate_mermaid_syntax(mermaid_content))


def cleanup_validator():
    """清理验证器资源"""
    global _validator_instance

    if _validator_instance:
        _validator_instance.close()
        _validator_instance = None
