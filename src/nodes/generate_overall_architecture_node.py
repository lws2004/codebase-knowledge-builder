"""生成整体架构节点，用于生成代码库的整体架构文档。"""

import asyncio  # Added for async operations
import json
import os
from typing import Any, Dict, Optional  # Ensure Tuple is imported for type hints if needed later

from pocketflow import AsyncNode  # Changed from Node to AsyncNode
from pydantic import BaseModel, Field

from ..utils.llm_wrapper.llm_client import LLMClient  # Import LLMClient
from ..utils.logger import log_and_notify
from ..utils.mermaid_realtime_validator import validate_mermaid_in_content
from ..utils.mermaid_regenerator import validate_and_fix_file_mermaid


class GenerateOverallArchitectureNodeConfig(BaseModel):
    """GenerateOverallArchitectureNode 配置"""

    retry_count: int = Field(3, ge=1, le=10, description="重试次数")
    quality_threshold: float = Field(0.7, ge=0, le=1.0, description="质量阈值")
    model: str = Field("", description="LLM 模型，从配置中获取，不应设置默认值")
    output_format: str = Field("markdown", description="输出格式")
    architecture_prompt_template: str = Field(
        """
        你是一个代码库架构专家。请根据以下信息生成一个全面的代码库架构文档。

        你正在分析的是{repo_name}代码库。请确保你的分析基于实际的{repo_name}代码，而不是生成通用示例项目。

        代码库结构:
        {code_structure}

        核心模块:
        {core_modules}

        历史分析:
        {history_analysis}

        请提供以下内容:
        1. 代码库概述
           - 项目名称({repo_name})和简介
           - 主要功能和用途
           - 技术栈概述
        2. 系统架构
           - 高层架构图（必须使用Mermaid或ASCII图表表示）
           - 主要组件和它们的职责
           - 组件之间的交互
        3. 核心模块详解
           - 每个核心模块的功能和职责
           - 模块之间的依赖关系（使用Mermaid流程图或时序图表示）
           - 关键接口和数据流
        4. 设计模式和原则
           - 使用的主要设计模式
           - 代码组织原则
           - 最佳实践
        5. 部署架构（如果适用）
           - 部署环境（使用Mermaid图表表示）
           - 部署流程
           - 扩展性考虑

        请以 Markdown 格式输出，使用适当的标题、列表、表格和代码块。
        使用表情符号使文档更加生动，例如在标题前使用适当的表情符号。

        必须包含至少2个Mermaid图表，用于可视化系统架构和模块依赖关系。

        **重要：Mermaid语法规范**
        - 节点标签使用方括号格式：NodeName[节点标签]
        - 不要在节点标签中使用引号：错误 NodeName["标签"] ✗，正确 NodeName[标签] ✓
        - 不要在节点标签中使用括号：错误 NodeName[标签(说明)] ✗，正确 NodeName[标签说明] ✓
        - 不要在节点标签中使用大括号：错误 NodeName[标签{内容}] ✗，正确 NodeName[标签内容] ✓
        - 不要使用嵌套方括号：错误 NodeName[NodeName[标签]] ✗，正确 NodeName[标签] ✓
        - 行末不要使用分号
        - 中文字符可以直接使用，无需特殊处理

        Mermaid图表示例：

        ```mermaid
        graph TD
            ModuleA[模块A] --> ModuleB[模块B]
            ModuleA --> ModuleC[模块C]
            ModuleB --> ModuleD[模块D]
            ModuleC --> ModuleD
        ```

        ```mermaid
        sequenceDiagram
            participant User[用户]
            participant API[API接口]
            participant DB[数据库]
            User->>API: 请求数据
            API->>DB: 查询数据
            DB-->>API: 返回结果
            API-->>User: 响应
        ```

        重要提示：
        1. 请确保你的分析是基于{repo_name}的实际代码，而不是生成通用示例项目。
        2. 不要使用"unknown"作为项目名称，应该使用"{repo_name}"。
        3. 不要生成虚构的模块名称，应该使用代码库中实际存在的模块名称。
        4. 不要生成虚构的API，应该使用代码库中实际存在的API。
        5. 如果你不确定某个信息，请基于提供的代码库结构和历史分析进行合理推断，而不是编造。
        6. 必须包含至少2个Mermaid图表，这是强制要求！文档中必须包含Mermaid图表来可视化系统架构和模块依赖关系。
        """,
        description="架构提示模板",
    )


class AsyncGenerateOverallArchitectureNode(AsyncNode):  # Renamed class and changed base class
    """生成整体架构节点（异步），用于生成代码库的整体架构文档"""

    llm_client: Optional[LLMClient] = None  # Add type hint

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化生成整体架构节点 (异步)

        Args:
            config: 节点配置
        """
        super().__init__()  # AsyncNode constructor

        # 从配置文件获取默认配置
        from ..utils.env_manager import get_node_config

        default_config = get_node_config("generate_overall_architecture")

        # 合并配置
        merged_config = default_config.copy()
        if config:
            merged_config.update(config)

        self.config = GenerateOverallArchitectureNodeConfig(**merged_config)
        # self._current_repo_name = None # No longer needed
        log_and_notify("初始化 AsyncGenerateOverallArchitectureNode", "info")  # Updated class name

    async def prep_async(self, shared: Dict[str, Any]) -> Dict[str, Any]:  # Renamed and made async
        """准备阶段，从共享存储中获取代码结构、核心模块和历史分析

        Args:
            shared: 共享存储

        Returns:
            包含代码结构、核心模块和历史分析的字典
        """
        log_and_notify("AsyncGenerateOverallArchitectureNode: 准备阶段开始", "info")  # Updated

        # 从共享存储中获取代码结构
        code_structure = shared.get("code_structure")
        if not code_structure:
            error_msg = "共享存储中缺少代码结构"
            log_and_notify(error_msg, "error", notify=True)
            return {"error": error_msg}

        # 检查代码结构是否有效
        if not code_structure.get("success", False):
            error_msg = "代码结构无效"
            log_and_notify(error_msg, "error", notify=True)
            return {"error": error_msg}

        # 从共享存储中获取核心模块
        core_modules = shared.get("core_modules")
        if (
            not core_modules
        ):  # TODO: Check for core_modules.get("success", False) as well if it's a dict from another node
            log_and_notify("共享存储中缺少核心模块，将使用空数据", "warning")
            core_modules = {"modules": [], "architecture": "", "relationships": [], "success": True}

        # 从共享存储中获取历史分析
        history_analysis = shared.get("history_analysis")
        if not history_analysis:  # TODO: Check for history_analysis.get("success", False) as well
            log_and_notify("共享存储中缺少历史分析，将使用空数据", "warning")
            history_analysis = {"commit_count": 0, "contributor_count": 0, "history_summary": "", "success": True}

        # Initialize LLMClient
        llm_config_shared = shared.get("llm_config")
        if not llm_config_shared:
            error_msg = "共享存储中缺少 LLM 配置"
            log_and_notify(error_msg, "error", notify=True)
            return {"error": error_msg}
        try:
            if not self.llm_client:  # Initialize only if not already initialized (e.g. by a parent flow)
                self.llm_client = LLMClient(config=llm_config_shared)
        except Exception as e:
            error_msg = f"AsyncGenerateOverallArchitectureNode: 初始化 LLMClient 失败: {e}"
            log_and_notify(error_msg, "error", notify=True)
            return {"error": error_msg}

        # 获取目标语言
        target_language = shared.get("language", "zh")

        # 获取输出目录
        output_dir = shared.get("output_dir", "docs")

        # 获取仓库名称
        repo_name = shared.get("repo_name", "docs")
        log_and_notify(
            f"AsyncGenerateOverallArchitectureNode.prep: 从共享存储中获取仓库名称 {repo_name}", "info"
        )  # Updated

        # 将仓库名称添加到代码结构中，以便在exec方法中使用
        if isinstance(code_structure, dict):
            code_structure["repo_name"] = repo_name

        return {
            "code_structure": code_structure,
            "core_modules": core_modules,
            "history_analysis": history_analysis,
            "target_language": target_language,
            "output_dir": output_dir,
            "retry_count": self.config.retry_count,
            "quality_threshold": self.config.quality_threshold,
            "model": self.config.model,
            "output_format": self.config.output_format,
            "repo_name": repo_name,  # 添加仓库名称
        }

    async def exec_async(self, prep_res: Dict[str, Any]) -> Dict[str, Any]:  # Renamed and made async
        """执行阶段，生成代码库的整体架构文档

        Args:
            prep_res: 准备阶段的结果

        Returns:
            生成结果
        """
        log_and_notify("AsyncGenerateOverallArchitectureNode: 执行阶段开始", "info")  # Updated

        # 检查准备阶段是否出错
        if "error" in prep_res:
            return {"error": prep_res["error"], "success": False}

        # 使用解构赋值简化代码
        code_structure, core_modules, history_analysis = (
            prep_res["code_structure"],
            prep_res["core_modules"],
            prep_res["history_analysis"],
        )
        target_language, output_dir = prep_res["target_language"], prep_res["output_dir"]
        retry_count, quality_threshold = prep_res["retry_count"], prep_res["quality_threshold"]
        model, output_format = prep_res["model"], prep_res["output_format"]

        # 获取仓库名称，这个应该从prep_res中获取
        # 在prep方法中，我们已经从shared中获取了这个值并添加到prep_res中
        repo_name = prep_res.get("repo_name", "docs")

        # 打印仓库名称，用于调试
        log_and_notify(f"AsyncGenerateOverallArchitectureNode: 使用仓库名称 {repo_name}", "info")  # Updated

        # 准备提示
        prompt = self._create_prompt(code_structure, core_modules, history_analysis, repo_name)

        # 尝试调用 LLM
        for attempt in range(retry_count):
            try:
                log_and_notify(
                    f"AsyncGenerateOverallArchitectureNode: 尝试生成整体架构文档 (尝试 {attempt + 1}/{retry_count})",
                    "info",
                )  # Updated

                # 调用 LLM
                content, quality_score, success = await self._call_model(prompt, target_language, model)

                if success and quality_score["overall"] >= quality_threshold:
                    log_and_notify(
                        f"AsyncGenerateOverallArchitectureNode: 成功生成整体架构文档 "
                        f"(质量分数: {quality_score['overall']})",
                        "info",
                    )

                    # 保存文档 (异步)
                    file_path = await asyncio.to_thread(
                        self._save_document, content, output_dir, output_format, repo_name
                    )

                    return {"content": content, "file_path": file_path, "quality_score": quality_score, "success": True}
                elif success:
                    log_and_notify(
                        f"AsyncGenerateOverallArchitectureNode: 生成质量不佳 "
                        f"(分数: {quality_score['overall']}), 重试中...",
                        "warning",
                    )
                else:
                    log_and_notify("AsyncGenerateOverallArchitectureNode: _call_model指示失败, 重试中...", "warning")

            except Exception as e:
                log_and_notify(
                    f"AsyncGenerateOverallArchitectureNode: LLM 调用或处理失败: {str(e)}, 重试中...", "warning"
                )  # Updated

            if attempt < retry_count - 1:
                await asyncio.sleep(2**attempt)  # Exponential backoff

        # 所有尝试都失败
        error_msg = f"AsyncGenerateOverallArchitectureNode: 无法生成整体架构文档，{retry_count} 次尝试后失败"  # Updated
        log_and_notify(error_msg, "error", notify=True)
        return {"error": error_msg, "success": False}

    async def post_async(
        self, shared: Dict[str, Any], _prep_res: Dict[str, Any], exec_res: Dict[str, Any]
    ) -> str:  # Renamed and made async
        """后处理阶段，将生成结果存储到共享存储中

        Args:
            shared: 共享存储
            _prep_res: 准备阶段的结果（未使用）
            exec_res: 执行阶段的结果

        Returns:
            下一个节点的动作
        """
        log_and_notify("AsyncGenerateOverallArchitectureNode: 后处理阶段开始", "info")  # Updated

        # 检查执行阶段是否出错
        if not exec_res.get("success", False):
            error_msg = exec_res.get("error", "AsyncGenerateOverallArchitectureNode: 未知错误")  # Updated
            log_and_notify(
                f"AsyncGenerateOverallArchitectureNode: 生成整体架构文档失败: {error_msg}", "error", notify=True
            )  # Updated
            shared["architecture_doc"] = {"error": error_msg, "success": False}
            return "error"

        # 将生成结果存储到共享存储中
        shared["architecture_doc"] = {
            "content": exec_res.get("content", ""),
            "file_path": exec_res.get("file_path", ""),
            "quality_score": exec_res.get("quality_score", {}),
            "success": True,
        }

        log_and_notify("AsyncGenerateOverallArchitectureNode: 整体架构文档已存储到共享存储中", "info")  # Updated
        return "default"

    def _create_prompt(
        self,
        code_structure: Dict[str, Any],
        core_modules: Dict[str, Any],
        history_analysis: Dict[str, Any],
        repo_name: str,
    ) -> str:
        """创建提示

        Args:
            code_structure: 代码结构
            core_modules: 核心模块
            history_analysis: 历史分析
            repo_name: 仓库名称

        Returns:
            提示
        """
        # 简化代码结构，避免提示过长
        simplified_structure = {
            "file_count": code_structure.get("file_count", 0),
            "directory_count": code_structure.get("directory_count", 0),
            "language_stats": code_structure.get("language_stats", {}),
            "file_types": code_structure.get("file_types", {}),
        }

        # 简化核心模块
        simplified_modules = {
            "modules": core_modules.get("modules", []),
            "architecture": core_modules.get("architecture", ""),
            "relationships": core_modules.get("relationships", []),
        }

        # 简化历史分析
        simplified_history = {
            "commit_count": history_analysis.get("commit_count", 0),
            "contributor_count": history_analysis.get("contributor_count", 0),
            "history_summary": history_analysis.get("history_summary", ""),
        }

        # 获取模板
        template = self.config.architecture_prompt_template

        # 替换模板中的变量，同时保留Mermaid图表中的大括号
        # 使用安全的方式替换变量，避免格式化字符串中的问题
        template = template.replace("{repo_name}", repo_name)
        template = template.replace("{code_structure}", json.dumps(simplified_structure, indent=2, ensure_ascii=False))
        template = template.replace("{core_modules}", json.dumps(simplified_modules, indent=2, ensure_ascii=False))
        template = template.replace("{history_analysis}", json.dumps(simplified_history, indent=2, ensure_ascii=False))

        return template

    @validate_mermaid_in_content(auto_fix=True, max_retries=2)
    async def _call_model(  # Made async
        self, prompt: str, target_language: str, model: str
    ) -> tuple:  # Python 3.8 doesn't support Tuple from typing for return type hint like this, use tuple
        """调用 LLM 生成整体架构文档 (异步)

        Args:
            prompt: 主提示内容
            target_language: 目标语言
            model: 要使用的模型名称

        Returns:
            (生成的文档内容, 质量评估分数, 是否成功)
        """
        assert self.llm_client is not None, "LLMClient has not been initialized!"

        system_prompt_content = f"你是一个专业的代码库架构专家，请按照用户要求生成文档。目标语言: {target_language}。"

        messages = [
            {"role": "system", "content": system_prompt_content},
            {"role": "user", "content": prompt},
        ]

        try:
            raw_response = await self.llm_client.acompletion(messages=messages, model=model)  # type: ignore[misc]

            if not raw_response:
                log_and_notify("AsyncGenerateOverallArchitectureNode: LLM 返回空响应", "error")
                return "", {}, False

            content = self.llm_client.get_completion_content(raw_response)
            if not content:
                log_and_notify("AsyncGenerateOverallArchitectureNode: 从 LLM 响应中提取内容失败", "error")
                return "", {}, False

            quality_score = self._evaluate_quality(content)  # This is a sync method
            return content, quality_score, True

        except Exception as e:
            log_and_notify(f"AsyncGenerateOverallArchitectureNode: _call_model 异常: {str(e)}", "error")
            return "", {}, False

    def _evaluate_quality(self, content: str) -> Dict[str, float]:
        """评估内容质量

        Args:
            content: 生成内容

        Returns:
            质量分数
        """
        score = {"overall": 0.0, "completeness": 0.0, "relevance": 0.0}
        if not content or not content.strip():
            log_and_notify("内容为空，质量评分为0", "warning")
            return score
        expected_keywords = ["代码库概述", "系统架构", "核心模块", "设计模式", "部署架构"]
        found_keywords = sum(1 for kw in expected_keywords if kw in content)
        score["completeness"] = min(1.0, found_keywords / len(expected_keywords) * 1.5)
        if len(content) > 500:
            score["relevance"] = 0.5
        if len(content) > 1000:
            score["relevance"] = 1.0
        score["overall"] = min(1.0, (score["completeness"] + score["relevance"]) / 2)
        score["overall"] = min(1.0, score["overall"])
        log_and_notify(f"质量评估完成: {score}", "debug")
        return score

    def _save_document(self, content: str, output_dir: str, output_format: str, repo_name: str) -> str:
        """保存文档

        Args:
            content: 文档内容
            output_dir: 输出目录
            output_format: 输出格式
            repo_name: 仓库名称，用于创建子目录

        Returns:
            文件路径
        """
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)

        # 使用传入的仓库名称
        repo_output_dir = os.path.join(output_dir, repo_name or "default_repo")
        os.makedirs(repo_output_dir, exist_ok=True)

        # 确定文件名和路径 - 将架构文档内容整合到overview.md中
        # 确保使用.md扩展名
        file_ext = ".md"
        file_name = f"overall_architecture{file_ext}"
        file_path = os.path.join(repo_output_dir, file_name)

        # 如果文件已存在，则将架构文档内容追加到文件末尾
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                existing_content = f.read()

            # 添加分隔符和架构文档内容
            combined_content = existing_content + "\n\n## 系统架构\n\n" + content

            # 保存合并后的文档
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(combined_content)
        else:
            # 如果文件不存在，则直接保存架构文档内容
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

        log_and_notify(f"整体架构文档已保存到: {file_path}", "info")

        # 立即修复文件中的 Mermaid 语法错误
        try:
            was_fixed = validate_and_fix_file_mermaid(file_path, self.llm_client, f"整体架构文档 - {repo_name}")
            if was_fixed:
                log_and_notify(f"已修复文件中的 Mermaid 语法错误: {file_path}", "info")
        except Exception as e:
            log_and_notify(f"修复 Mermaid 语法错误时出错: {str(e)}", "warning")

        return file_path
