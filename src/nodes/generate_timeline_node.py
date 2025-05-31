"""生成时间线文档节点，用于生成代码库的演变时间线文档。"""

import asyncio  # Added for async operations
import json
import os
from typing import Any, Dict, Optional, Tuple

from pocketflow import AsyncNode  # Changed from Node to AsyncNode
from pydantic import BaseModel, Field

from ..utils.llm_wrapper.llm_client import LLMClient
from ..utils.logger import log_and_notify
from ..utils.mermaid_realtime_validator import validate_mermaid_in_content
from ..utils.mermaid_regenerator import validate_and_fix_file_mermaid


class GenerateTimelineNodeConfig(BaseModel):
    """GenerateTimelineNode 配置"""

    retry_count: int = Field(3, ge=1, le=10, description="重试次数")
    quality_threshold: float = Field(0.7, ge=0, le=1.0, description="质量阈值")
    model: str = Field("", description="LLM 模型，从配置中获取")
    output_format: str = Field("markdown", description="输出格式")
    timeline_prompt_template: str = Field(
        """
        你是一个代码库历史分析专家。请根据以下信息生成一个全面的代码库演变时间线文档。

        历史分析:
        {history_analysis}

        请提供以下内容:
        1. 项目演变概述
           - 项目的起源和发展历程
           - 主要里程碑和转折点
        2. 关键版本时间线
           - 按时间顺序列出关键版本
           - 每个版本的主要变化和贡献
        3. 功能演进
           - 主要功能的引入和发展
           - 技术栈的变化和升级
        4. 贡献者分析
           - 主要贡献者及其贡献领域
           - 贡献模式和团队协作方式
        5. 未来发展趋势
           - 基于历史数据的发展趋势预测
           - 潜在的改进方向

        请以 Markdown 格式输出，使用适当的标题、列表、表格和时间线图表。
        使用表情符号使文档更加生动，例如在标题前使用适当的表情符号。

        必须包含至少1个Mermaid图表，用于可视化时间线。

        **重要：Mermaid语法规范**
        - 节点标签使用方括号格式：NodeName[节点标签]
        - 不要在节点标签中使用引号：错误 NodeName["标签"] ✗，正确 NodeName[标签] ✓
        - 不要在节点标签中使用括号：错误 NodeName[标签(说明)] ✗，正确 NodeName[标签说明] ✓
        - 不要在节点标签中使用大括号：错误 NodeName[标签{内容}] ✗，正确 NodeName[标签内容] ✓
        - 不要使用嵌套方括号：错误 NodeName[NodeName[标签]] ✗，正确 NodeName[标签] ✓
        - 行末不要使用分号
        - 中文字符可以直接使用，无需特殊处理
        - 饼图使用格式：pie title 标题，不要使用单独的 pie
        - 时间线使用格式：timeline 或 graph TD

        Mermaid图表示例：

        ```mermaid
        timeline
            title 项目发展时间线
            section 2011
                创建项目 : 初始版本发布
            section 2012
                添加会话支持 : 增强功能
            section 2013
                重构核心模块 : 性能优化
        ```
        """,
        description="时间线提示模板",
    )


class AsyncGenerateTimelineNode(AsyncNode):  # Renamed class and changed base class
    """生成时间线文档节点（异步），用于生成代码库的演变时间线文档"""

    llm_client: Optional[LLMClient] = None  # Add type hint

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化生成时间线文档节点 (异步)

        Args:
            config: 节点配置
        """
        super().__init__()  # AsyncNode constructor
        from ..utils.env_manager import get_node_config

        default_config = get_node_config("generate_timeline")
        merged_config = default_config.copy()
        if config:
            merged_config.update(config)
        self.config = GenerateTimelineNodeConfig(**merged_config)
        log_and_notify("初始化 AsyncGenerateTimelineNode", "info")  # Updated class name

    async def prep_async(self, shared: Dict[str, Any]) -> Dict[str, Any]:  # Renamed and made async
        """准备阶段，从共享存储中获取必要的数据

        Args:
            shared: 共享存储

        Returns:
            准备结果
        """
        log_and_notify("AsyncGenerateTimelineNode: 准备阶段开始", "info")  # Updated
        history_analysis = shared.get("history_analysis")
        if not history_analysis:  # TODO: check success flag if history_analysis is dict
            error_msg = "共享存储中缺少历史分析"
            log_and_notify(error_msg, "error", notify=True)
            return {"error": error_msg}

        llm_config_shared = shared.get("llm_config")  # No default {}
        if llm_config_shared:
            try:
                if not self.llm_client:
                    self.llm_client = LLMClient(config=llm_config_shared)
                log_and_notify("AsyncGenerateTimelineNode: LLMClient initialized.", "info")
            except Exception as e:
                log_and_notify(
                    f"AsyncGenerateTimelineNode: LLMClient initialization failed: {e}. "
                    f"Node will proceed without LLM if possible, or fail.",
                    "warning",
                )
                self.llm_client = None
        else:
            log_and_notify("AsyncGenerateTimelineNode: No LLM config found. Proceeding without LLM client.", "warning")
            self.llm_client = None

        target_language = shared.get("language", "zh")
        output_dir = shared.get("output_dir", "docs")
        repo_name = shared.get("repo_name", "default_repo")  # Get repo_name for saving

        return {
            "history_analysis": history_analysis,
            "target_language": target_language,
            "output_dir": output_dir,
            "repo_name": repo_name,  # Pass repo_name
            "retry_count": self.config.retry_count,
            "quality_threshold": self.config.quality_threshold,
            "model": self.config.model,
            "output_format": self.config.output_format,
        }

    async def exec_async(self, prep_res: Dict[str, Any]) -> Dict[str, Any]:  # Renamed and made async
        """执行阶段，生成时间线文档

        Args:
            prep_res: 准备阶段的结果

        Returns:
            执行结果
        """
        log_and_notify("AsyncGenerateTimelineNode: 执行阶段开始", "info")  # Updated
        if "error" in prep_res:
            return {"success": False, "error": prep_res["error"]}

        history_analysis = prep_res["history_analysis"]
        target_language = prep_res["target_language"]
        output_dir = prep_res["output_dir"]
        repo_name = prep_res["repo_name"]
        retry_count = prep_res["retry_count"]
        quality_threshold = prep_res["quality_threshold"]
        model_name = prep_res["model"]
        output_format = prep_res["output_format"]

        if not self.llm_client:
            error_msg = "AsyncGenerateTimelineNode: LLMClient 未初始化，无法生成时间线。"
            log_and_notify(error_msg, "error", notify=True)
            return {"error": error_msg, "success": False}

        prompt_str = self._create_prompt(history_analysis)

        for attempt in range(retry_count):
            try:
                log_and_notify(
                    f"AsyncGenerateTimelineNode: 尝试生成时间线文档 (尝试 {attempt + 1}/{retry_count})", "info"
                )
                content, quality_score, success = await self._call_model_async(prompt_str, target_language, model_name)
                if success and quality_score["overall"] >= quality_threshold:
                    log_and_notify(
                        f"AsyncGenerateTimelineNode: 成功生成时间线文档 (质量分数: {quality_score['overall']})", "info"
                    )
                    # Save document asynchronously using repo_name
                    file_path = await asyncio.to_thread(
                        self._save_document,
                        content,
                        output_dir,
                        output_format,
                        repo_name,  # Pass repo_name
                    )
                    return {"content": content, "file_path": file_path, "quality_score": quality_score, "success": True}
                elif success:
                    log_and_notify(
                        f"AsyncGenerateTimelineNode: 生成质量不佳 (分数: {quality_score['overall']}), 重试中...",
                        "warning",
                    )
                else:
                    log_and_notify("AsyncGenerateTimelineNode: _call_model_async 指示失败, 重试中...", "warning")
            except Exception as e:
                log_and_notify(f"AsyncGenerateTimelineNode: LLM 调用或处理失败: {str(e)}, 重试中...", "warning")
            if attempt < retry_count - 1:
                await asyncio.sleep(2**attempt)

        error_msg = f"AsyncGenerateTimelineNode: 无法生成高质量的时间线文档，已尝试 {retry_count} 次"
        log_and_notify(error_msg, "error", notify=True)
        return {"success": False, "error": error_msg}

    async def post_async(
        self, shared: Dict[str, Any], _: Dict[str, Any], exec_res: Dict[str, Any]
    ) -> str:  # Renamed and made async
        """后处理阶段，将时间线文档存储到共享存储中

        Args:
            shared: 共享存储
            _: 准备阶段的结果（未使用）
            exec_res: 执行阶段的结果

        Returns:
            下一个节点的动作
        """
        log_and_notify("AsyncGenerateTimelineNode: 后处理阶段开始", "info")  # Updated
        if not exec_res.get("success", False):
            error_msg = exec_res.get("error", "AsyncGenerateTimelineNode: 生成时间线文档失败")  # Updated
            # Ensure error is stored in shared state
            shared["error"] = error_msg
            shared["timeline_doc"] = {"error": error_msg, "success": False}
            return "error"

        shared["timeline_doc"] = {
            "content": exec_res.get("content", ""),
            "file_path": exec_res.get("file_path", ""),
            "quality_score": exec_res.get("quality_score", {}),
            "success": True,
        }
        log_and_notify("AsyncGenerateTimelineNode: 时间线文档已存储到共享存储中", "info")  # Updated
        return "default"

    def _create_prompt(self, history_analysis: Dict[str, Any]) -> str:
        """创建提示

        Args:
            history_analysis: 历史分析

        Returns:
            提示
        """
        # Simplify history_analysis if needed to fit context window
        simplified_history = {
            "commit_count": history_analysis.get("commit_count", 0),
            "contributor_count": history_analysis.get("contributor_count", 0),
            "history_summary": history_analysis.get("history_summary", ""),  # Only include summary
            # Avoid dumping full commit history if too large
        }

        # 获取仓库名称
        repo_name = history_analysis.get("repo_name", "requests")

        # 获取模板
        template = self.config.timeline_prompt_template

        # 替换模板中的变量，同时保留Mermaid图表中的大括号
        # 使用安全的方式替换变量，避免格式化字符串中的问题
        template = template.replace("{repo_name}", repo_name)
        template = template.replace("{history_analysis}", json.dumps(simplified_history, indent=2, ensure_ascii=False))

        return template

    @validate_mermaid_in_content(auto_fix=True, max_retries=2)
    async def _call_model_async(  # Renamed for consistency
        self, prompt_str: str, target_language: str, model_name: str
    ) -> Tuple[str, Dict[str, float], bool]:
        """调用 LLM (异步)

        Args:
            prompt_str: 主提示内容
            target_language: 目标语言
            model_name: 要使用的模型名称

        Returns:
            (生成的文档内容, 质量评估分数, 是否成功)
        """
        assert self.llm_client is not None, "LLMClient has not been initialized!"
        system_prompt_content = (
            f"你是一个代码库分析专家，请根据用户提供的历史分析生成简洁的时间线文档。目标语言: {target_language}。"
            f"确保内容简明扼要，适合快速阅读。"
        )
        messages = [
            {"role": "system", "content": system_prompt_content},
            {"role": "user", "content": prompt_str},
        ]
        try:
            raw_response = await self.llm_client.acompletion(  # type: ignore[misc]
                messages=messages, model=model_name
            )
            if not raw_response:
                log_and_notify("AsyncGenerateTimelineNode: LLM 返回空响应", "error")
                return "", {}, False
            content = self.llm_client.get_completion_content(raw_response)
            if not content:
                log_and_notify("AsyncGenerateTimelineNode: 从 LLM 响应中提取内容失败", "error")
                return "", {}, False
            quality_score = self._evaluate_quality(content)
            return content, quality_score, True
        except Exception as e:
            log_and_notify(f"AsyncGenerateTimelineNode: _call_model_async 异常: {str(e)}", "error")
            return "", {}, False

    def _evaluate_quality(self, content: str) -> Dict[str, float]:
        """评估内容质量

        Args:
            content: 生成内容

        Returns:
            质量分数
        """
        score = {"overall": 0.0, "completeness": 0.0, "relevance": 0.0, "structure": 0.0}
        if not content or not content.strip():
            log_and_notify("内容为空，质量评分为0", "warning")
            return score

        # Completeness based on expected sections
        expected_sections = ["项目演变", "关键版本", "功能演进", "贡献者", "未来发展"]
        found_sections = sum(1 for section in expected_sections if section in content)
        score["completeness"] = found_sections / len(expected_sections)

        # Structure based on markdown elements (basic check)
        if "##" in content:
            score["structure"] += 0.4
        if "- " in content or "* " in content:
            score["structure"] += 0.3  # Lists
        if "```mermaid" in content:
            score["structure"] += 0.3  # Mermaid chart
        score["structure"] = min(1.0, score["structure"])

        # Relevance (very basic check)
        relevance_score = 0.0
        if "时间线" in content or "演变" in content:
            relevance_score += 0.5
        if len(content) > 300:
            relevance_score += 0.3
        if len(content) > 700:
            relevance_score += 0.2
        score["relevance"] = min(1.0, relevance_score)

        score["overall"] = score["completeness"] * 0.4 + score["structure"] * 0.3 + score["relevance"] * 0.3
        score["overall"] = min(1.0, score["overall"])

        log_and_notify(f"时间线文档质量评估完成: {score}", "debug")
        return score

    def _save_document(self, content: str, output_dir: str, output_format: str, repo_name: str) -> str:
        """保存文档到仓库子目录

        Args:
            content: 文档内容
            output_dir: 输出目录
            output_format: 输出格式
            repo_name: 仓库名称 (用于创建子目录)

        Returns:
            文件路径
        """
        # Ensure repo-specific directory exists
        repo_specific_dir = os.path.join(output_dir, repo_name or "default_repo")
        try:
            os.makedirs(repo_specific_dir, exist_ok=True)
        except OSError as e:
            log_and_notify(f"创建目录失败 {repo_specific_dir}: {e}", "error")
            raise  # Re-raise if directory creation fails

        # 根据输出格式确定文件扩展名
        file_ext = ".md" if output_format.lower() == "markdown" else f".{output_format.lower()}"
        file_name = f"timeline{file_ext}"
        file_path = os.path.join(repo_specific_dir, file_name)  # Save inside repo sub-directory

        try:
            # 过滤内容，移除多余的markdown标记
            filtered_content = self._filter_unwanted_text(content)

            # This part runs in a thread via asyncio.to_thread
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(filtered_content)
            log_and_notify(f"时间线文档已保存到: {file_path}", "info")

            # 立即修复文件中的 Mermaid 语法错误
            try:
                was_fixed = validate_and_fix_file_mermaid(file_path, self.llm_client, f"时间线文档 - {repo_name}")
                if was_fixed:
                    log_and_notify(f"已修复文件中的 Mermaid 语法错误: {file_path}", "info")
            except Exception as e:
                log_and_notify(f"修复 Mermaid 语法错误时出错: {str(e)}", "warning")

            return file_path
        except IOError as e:
            log_and_notify(f"保存时间线文档失败: {str(e)}", "error", notify=True)
            raise  # Re-raise to be caught by the caller (exec_async's try-except)

    def _filter_unwanted_text(self, content: str) -> str:
        """过滤掉不应该出现在文档中的文本，并修复格式问题

        Args:
            content: 原始内容

        Returns:
            过滤后的内容
        """
        import re

        # 过滤掉常见的不应该出现的文本
        unwanted_texts = [
            "无需提供修复后的完整文档，只需根据上述改进建议进行修改即可。",
            "无需提供修复后的完整文档，只需根据上述改进建议进行修改即可",
            "请不要提供修复后的完整文档，只提供详细的改进建议",
            "不要在回复中包含无需提供修复后的完整文档，只需根据上述改进建议进行修改即可这样的文本",
        ]

        filtered_content = content
        for text in unwanted_texts:
            filtered_content = filtered_content.replace(text, "")

        # 移除文档开头和结尾的 ```markdown 和 ``` 标记
        # 处理开头的markdown标记
        if filtered_content.startswith("```markdown\n"):
            filtered_content = filtered_content[12:]
        elif filtered_content.startswith("```markdown"):
            filtered_content = filtered_content[11:]

        # 处理结尾的markdown标记
        if filtered_content.endswith("\n```"):
            filtered_content = filtered_content[:-4]
        elif filtered_content.endswith("```"):
            filtered_content = filtered_content[:-3]

        # 处理文档开头的孤立```markdown标记（不在代码块中的）
        lines = filtered_content.split("\n")
        if lines and lines[0].strip() == "```markdown":
            lines = lines[1:]

        # 处理文档结尾的孤立```标记（不在代码块中的）
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        filtered_content = "\n".join(lines)

        # 修复 Mermaid 图表格式问题
        # 移除 Mermaid 图表周围的 ```markdown 和 ``` 标记
        filtered_content = filtered_content.replace("```markdown\n```mermaid", "```mermaid")
        filtered_content = filtered_content.replace("```\n```mermaid", "```mermaid")

        # 修复 Mermaid 图表中的特殊字符问题
        from ..utils.formatter import fix_mermaid_syntax, remove_redundant_summaries

        filtered_content = fix_mermaid_syntax(filtered_content)

        # 清理多余的总结文本
        filtered_content = remove_redundant_summaries(filtered_content)

        # 移除其他可能的markdown代码块标记
        filtered_content = filtered_content.replace("```markdown\n", "")
        filtered_content = filtered_content.replace("```markdown", "")

        # 处理孤立的```标记（不在代码块中的）
        lines = filtered_content.split("\n")
        cleaned_lines = []
        in_code_block = False

        for line in lines:
            stripped_line = line.strip()

            # 检查是否是代码块开始/结束标记
            if stripped_line.startswith("```"):
                if stripped_line == "```":
                    # 孤立的```标记，检查是否应该保留
                    if in_code_block:
                        # 这是代码块结束标记
                        cleaned_lines.append(line)
                        in_code_block = False
                    else:
                        # 这可能是孤立的```标记，跳过
                        continue
                else:
                    # 这是带语言标识的代码块开始标记
                    cleaned_lines.append(line)
                    in_code_block = True
            else:
                cleaned_lines.append(line)

        filtered_content = "\n".join(cleaned_lines)

        # Normalize line breaks to use only \n
        filtered_content = filtered_content.replace("\r\n", "\n").replace("\r", "\n")

        # Collapse multiple consecutive blank lines into a single blank line
        # This regex replaces two or more consecutive newlines with exactly two newlines (one blank line)
        filtered_content = re.sub(r"\n{2,}", "\n\n", filtered_content)

        return filtered_content
