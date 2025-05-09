"""生成依赖关系文档节点，用于生成代码库的依赖关系文档。"""

import asyncio  # Add asyncio import
import json
import os
from typing import Any, Dict, Optional, Tuple

from pocketflow import AsyncNode
from pydantic import BaseModel, Field

from ..utils.llm_wrapper.llm_client import LLMClient
from ..utils.logger import log_and_notify


class GenerateDependencyNodeConfig(BaseModel):
    """GenerateDependencyNode 配置"""

    retry_count: int = Field(3, ge=1, le=10, description="重试次数")
    quality_threshold: float = Field(0.7, ge=0, le=1.0, description="质量阈值")
    model: str = Field("", description="LLM 模型，从配置中获取，不应设置默认值")
    output_format: str = Field("markdown", description="输出格式")
    dependency_prompt_template: str = Field(
        """
        你是一个代码库依赖分析专家。请根据以下信息生成一个全面的代码库依赖关系文档。

        你正在分析的是{repo_name}代码库。请确保你的分析基于实际的{repo_name}代码，而不是生成通用示例项目。

        代码库结构:
        {code_structure}

        核心模块:
        {core_modules}

        请提供以下内容:
        1. 依赖概述
           - 主要依赖类型和分类
           - 依赖管理策略
        2. 内部依赖关系
           - 模块间的依赖关系
           - 关键组件的依赖图
        3. 外部依赖分析
           - 主要第三方依赖
           - 版本要求和兼容性
        4. 依赖优化建议
           - 潜在的循环依赖问题
           - 依赖简化和优化方向
        5. 依赖管理最佳实践
           - 推荐的依赖管理方法
           - 版本控制和更新策略

        请以 Markdown 格式输出，使用适当的标题、列表、表格和依赖图。
        使用表情符号使文档更加生动，例如在标题前使用适当的表情符号。
        如果可能，请使用 Mermaid 语法创建依赖关系图。
        重要提示：
        1. 请确保你的分析是基于{repo_name}的实际代码，而不是生成通用示例项目。
        2. 不要使用"unknown"作为项目名称，应该使用"{repo_name}"。
        3. 不要生成虚构的模块名称，应该使用代码库中实际存在的模块名称。
        4. 不要生成虚构的API，应该使用代码库中实际存在的API。
        5. 如果你不确定某个信息，请基于提供的代码库结构和核心模块进行合理推断，而不是编造。
        """,
        description="依赖关系提示模板",
    )


class AsyncGenerateDependencyNode(AsyncNode):
    """生成依赖关系文档节点（异步），用于生成代码库的依赖关系文档"""

    llm_client: Optional[LLMClient] = None

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化生成依赖关系文档节点 (异步)

        Args:
            config: 节点配置
        """
        super().__init__()
        from ..utils.env_manager import get_node_config

        default_config = get_node_config("generate_dependency")

        merged_config = default_config.copy()
        if config:
            merged_config.update(config)

        self.config = GenerateDependencyNodeConfig(**merged_config)
        self.llm_client = None
        log_and_notify("初始化 AsyncGenerateDependencyNode", "info")

    async def prep_async(self, shared: Dict[str, Any]) -> Dict[str, Any]:
        """准备阶段，从共享存储中获取必要的数据

        Args:
            shared: 共享存储

        Returns:
            准备结果
        """
        log_and_notify("AsyncGenerateDependencyNode: 准备阶段开始", "info")
        code_structure = shared.get("code_structure")
        if not code_structure:
            error_msg = "共享存储中缺少代码结构"
            log_and_notify(error_msg, "error", notify=True)
            return {"error": error_msg}

        core_modules = shared.get("core_modules")
        if not core_modules:
            log_and_notify("共享存储中缺少核心模块，将使用空数据", "warning")
            core_modules = {"modules": [], "architecture": "", "relationships": [], "success": True}

        llm_config_shared = shared.get("llm_config")
        if llm_config_shared:
            try:
                if not self.llm_client:
                    self.llm_client = LLMClient(config=llm_config_shared)
                log_and_notify("AsyncGenerateDependencyNode: LLMClient initialized.", "info")
            except Exception as e:
                log_and_notify(
                    f"AsyncGenerateDependencyNode: LLMClient initialization failed: {e}. "
                    f"Node will proceed without LLM if possible, or fail.",
                    "warning",
                )
                self.llm_client = None
        else:
            log_and_notify(
                "AsyncGenerateDependencyNode: No LLM config found. Proceeding without LLM client.", "warning"
            )
            self.llm_client = None

        target_language = shared.get("language", "zh")
        output_dir = shared.get("output_dir", "docs")
        repo_name = shared.get("repo_name", "default_repo")
        log_and_notify(f"AsyncGenerateDependencyNode.prep_async: 从共享存储中获取仓库名称 {repo_name}", "info")

        return {
            "code_structure": code_structure,
            "core_modules": core_modules,
            "target_language": target_language,
            "output_dir": output_dir,
            "repo_name": repo_name,
            "retry_count": self.config.retry_count,
            "quality_threshold": self.config.quality_threshold,
            "model": self.config.model,
            "output_format": self.config.output_format,
        }

    async def exec_async(self, prep_res: Dict[str, Any]) -> Dict[str, Any]:
        """执行阶段，生成依赖关系文档

        Args:
            prep_res: 准备阶段的结果

        Returns:
            执行结果
        """
        log_and_notify("AsyncGenerateDependencyNode: 执行阶段开始", "info")
        if "error" in prep_res:
            return {"success": False, "error": prep_res["error"]}

        code_structure = prep_res["code_structure"]
        core_modules = prep_res["core_modules"]
        target_language = prep_res["target_language"]
        output_dir = prep_res["output_dir"]
        retry_count = prep_res["retry_count"]
        quality_threshold = prep_res["quality_threshold"]
        model_name = prep_res["model"]
        output_format = prep_res["output_format"]
        repo_name = prep_res.get("repo_name", "default_repo")
        log_and_notify(f"AsyncGenerateDependencyNode.exec_async: 使用仓库名称 {repo_name}", "info")

        if not self.llm_client:
            error_msg = "AsyncGenerateDependencyNode: LLMClient 未初始化，无法生成依赖文档。"
            log_and_notify(error_msg, "error", notify=True)
            return {"error": error_msg, "success": False}

        prompt_str = self._create_prompt(code_structure, core_modules, repo_name)

        for attempt in range(retry_count):
            try:
                log_and_notify(
                    f"AsyncGenerateDependencyNode: 尝试生成依赖关系文档 (尝试 {attempt + 1}/{retry_count})", "info"
                )

                content, quality_score, success = await self._call_model_async(
                    prompt_str,
                    target_language,
                    model_name,
                    repo_name,
                )

                if success and quality_score["overall"] >= quality_threshold:
                    log_and_notify(
                        f"AsyncGenerateDependencyNode: 成功生成依赖关系文档 (质量分数: {quality_score['overall']})",
                        "info",
                    )
                    file_path = await asyncio.to_thread(
                        self._save_document,
                        content,
                        output_dir,
                        output_format,
                        repo_name,
                    )
                    return {"content": content, "file_path": file_path, "quality_score": quality_score, "success": True}
                elif success:
                    log_and_notify(
                        f"AsyncGenerateDependencyNode: 生成质量不佳 (分数: {quality_score['overall']}), 重试中...",
                        "warning",
                    )
                else:
                    log_and_notify("AsyncGenerateDependencyNode: _call_model_async 指示失败, 重试中...", "warning")

            except Exception as e:
                log_and_notify(f"AsyncGenerateDependencyNode: LLM 调用或处理失败: {str(e)}, 重试中...", "warning")

            if attempt < retry_count - 1:
                await asyncio.sleep(2**attempt)

        error_msg = f"AsyncGenerateDependencyNode: 无法生成高质量的依赖关系文档，已尝试 {retry_count} 次"
        log_and_notify(error_msg, "error", notify=True)
        return {"success": False, "error": error_msg}

    async def post_async(self, shared: Dict[str, Any], _: Dict[str, Any], exec_res: Dict[str, Any]) -> str:
        """后处理阶段，将依赖关系文档存储到共享存储中

        Args:
            shared: 共享存储
            _: 准备阶段的结果 (未使用)
            exec_res: 执行阶段的结果

        Returns:
            下一个节点的动作
        """
        log_and_notify("AsyncGenerateDependencyNode: 后处理阶段开始", "info")
        if not exec_res.get("success", False):
            error_msg = exec_res.get("error", "AsyncGenerateDependencyNode: 生成依赖关系文档失败")
            shared["error"] = error_msg
            shared["dependency_doc"] = {
                "error": error_msg,
                "success": False,
            }
            return "error"

        shared["dependency_doc"] = {
            "content": exec_res.get("content", ""),
            "file_path": exec_res.get("file_path", ""),
            "quality_score": exec_res.get("quality_score", {}),
            "success": True,
        }

        log_and_notify("AsyncGenerateDependencyNode: 依赖关系文档已存储到共享存储中", "info")
        return "default"

    def _create_prompt(self, code_structure: Dict[str, Any], core_modules: Dict[str, Any], repo_name: str) -> str:
        """创建提示

        Args:
            code_structure: 代码结构
            core_modules: 核心模块
            repo_name: 仓库名称

        Returns:
            提示
        """
        simplified_structure = {
            "file_count": code_structure.get("file_count", 0),
            "directory_count": code_structure.get("directory_count", 0),
            "language_stats": code_structure.get("language_stats", {}),
            "file_types": code_structure.get("file_types", {}),
        }

        simplified_modules = {
            "modules": core_modules.get("modules", []),
            "architecture": core_modules.get("architecture", ""),
            "relationships": core_modules.get("relationships", []),
        }

        # 确保repo_name不为空
        if not repo_name or repo_name == "unknown":
            repo_name = code_structure.get("repo_name", "requests")

        # 获取模板
        template = self.config.dependency_prompt_template

        # 替换模板中的变量，同时保留Mermaid图表中的大括号
        # 使用安全的方式替换变量，避免格式化字符串中的问题
        template = template.replace("{repo_name}", repo_name)
        template = template.replace("{code_structure}", json.dumps(simplified_structure, indent=2, ensure_ascii=False))
        template = template.replace("{core_modules}", json.dumps(simplified_modules, indent=2, ensure_ascii=False))

        return template

    async def _call_model_async(
        self,
        prompt_str: str,
        target_language: str,
        model_name: str,
        repo_name: str,
    ) -> Tuple[str, Dict[str, float], bool]:
        """调用 LLM (异步)

        Args:
            prompt_str: 提示
            target_language: 目标语言
            model_name: 模型名称
            repo_name: 仓库名称

        Returns:
            生成内容、质量分数和成功标志
        """
        assert self.llm_client is not None, "LLMClient has not been initialized!"  # Ensure llm_client is init

        system_prompt_content = (
            f"你是一个代码库依赖分析专家。请根据用户提供的信息为 {repo_name} 代码库生成依赖关系文档。"
            f"目标语言: {target_language}。请确保你的分析基于实际的 {repo_name} 代码。"
            f"如果可能，请使用 Mermaid 语法创建依赖关系图。"
        )
        messages = [
            {"role": "system", "content": system_prompt_content},
            {"role": "user", "content": prompt_str},
        ]

        try:
            raw_response = await self.llm_client.acompletion(  # type: ignore[misc] # Call acompletion
                messages=messages,
                model=model_name,  # Pass model_name
            )
            if not raw_response:
                log_and_notify("AsyncGenerateDependencyNode: LLM 返回空响应", "error")
                return "", {}, False

            content = self.llm_client.get_completion_content(raw_response)
            if not content:
                log_and_notify("AsyncGenerateDependencyNode: 从 LLM 响应中提取内容失败", "error")
                return "", {}, False

            quality_score = self._evaluate_quality(content)  # This is a sync method, remains as is
            return content, quality_score, True

        except Exception as e:
            log_and_notify(f"AsyncGenerateDependencyNode: _call_model_async 异常: {str(e)}", "error")
            return "", {}, False

    def _evaluate_quality(self, content: str) -> Dict[str, float]:
        """评估内容质量

        Args:
            content: 生成内容

        Returns:
            质量分数
        """
        # Placeholder for actual quality evaluation logic
        score = {"overall": 0.0, "completeness": 0.0, "relevance": 0.0}
        if not content or not content.strip():
            log_and_notify("内容为空，质量评分为0", "warning")
            return score

        expected_keywords = ["依赖概述", "内部依赖", "外部依赖", "优化建议", "Mermaid"]
        found_keywords = sum(1 for kw in expected_keywords if kw in content)
        score["completeness"] = min(1.0, found_keywords / len(expected_keywords) * 1.5)  # Boost if all found

        if len(content) > 300:  # Basic check for some content
            score["relevance"] = 0.5
        if len(content) > 700:  # More content might mean more relevance
            score["relevance"] = 1.0

        # Check for Mermaid diagram for structure
        if "graph TD" in content or "flowchart" in content:
            score["completeness"] = min(1.0, score["completeness"] + 0.2)

        score["overall"] = min(1.0, (score["completeness"] + score["relevance"]) / 2)
        score["overall"] = min(1.0, score["overall"])  # Cap at 1.0

        log_and_notify(f"依赖关系文档质量评估完成: {score}", "debug")
        return score

    def _save_document(self, content: str, output_dir: str, output_format: str, repo_name: str) -> str:
        """保存文档

        Args:
            content: 文档内容
            output_dir: 输出目录
            output_format: 输出格式
            repo_name: 仓库名称

        Returns:
            文件路径
        """
        # Ensure repo-specific directory exists
        repo_specific_dir = os.path.join(output_dir, repo_name or "default_repo")
        try:
            os.makedirs(repo_specific_dir, exist_ok=True)
        except OSError as e:
            log_and_notify(f"创建目录失败 {repo_specific_dir}: {e}", "error")
            raise

        # 确保使用.md扩展名
        file_ext = ".md"
        file_name = f"dependency{file_ext}"
        file_path = os.path.join(repo_specific_dir, file_name)  # Save inside repo sub-directory

        try:
            # This part runs in a thread via asyncio.to_thread
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            log_and_notify(f"依赖关系文档已保存到: {file_path}", "info")
            return file_path
        except IOError as e:
            log_and_notify(f"保存依赖关系文档失败: {str(e)}", "error", notify=True)
            raise
