"""生成术语表文档节点，用于生成代码库的术语表文档。"""

import asyncio
import json
import os
from typing import Any, Dict, Optional, Tuple

from pocketflow import AsyncNode
from pydantic import BaseModel, Field

from ..utils.llm_wrapper import LLMClient
from ..utils.logger import log_and_notify


class GenerateGlossaryNodeConfig(BaseModel):
    """GenerateGlossaryNode 配置"""

    retry_count: int = Field(3, ge=1, le=10, description="重试次数")
    quality_threshold: float = Field(0.7, ge=0, le=1.0, description="质量阈值")
    model: str = Field("", description="LLM 模型，从配置中获取，不应设置默认值")
    output_format: str = Field("markdown", description="输出格式")
    glossary_prompt_template: str = Field(
        """
        你是一个代码库术语专家。请根据以下信息生成一个全面的代码库术语表文档。

        代码库结构:
        {code_structure}

        核心模块:
        {core_modules}

        历史分析:
        {history_analysis}

        请提供以下内容:
        1. 术语表概述
           - 术语表的目的和使用方法
           - 术语分类和组织方式
        2. 项目特定术语
           - 项目中使用的特定术语和概念
           - 每个术语的定义和用法
        3. 技术术语
           - 项目中使用的技术术语
           - 每个术语的定义和相关技术背景
        4. 缩写和首字母缩略词
           - 项目中使用的缩写和首字母缩略词
           - 每个缩写的全称和含义
        5. 术语关系
           - 术语之间的关系和层次结构
           - 相关术语的交叉引用

        请以 Markdown 格式输出，使用适当的标题、列表和表格。
        使用表情符号使文档更加生动，例如在标题前使用适当的表情符号。
        术语表应按字母顺序排列，便于查找。
        """,
        description="术语表提示模板",
    )


class AsyncGenerateGlossaryNode(AsyncNode):
    """生成术语表文档节点（异步），用于生成代码库的术语表文档"""

    llm_client: Optional[LLMClient] = None

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化生成术语表文档节点 (异步)

        Args:
            config: 节点配置
        """
        super().__init__()

        from ..utils.env_manager import get_node_config

        default_config = get_node_config("generate_glossary")
        merged_config = default_config.copy()
        if config:
            merged_config.update(config)

        self.config = GenerateGlossaryNodeConfig(**merged_config)
        log_and_notify("初始化 AsyncGenerateGlossaryNode", "info")

    async def prep_async(self, shared: Dict[str, Any]) -> Dict[str, Any]:
        """准备阶段，从共享存储中获取必要的数据

        Args:
            shared: 共享存储

        Returns:
            准备结果
        """
        log_and_notify("AsyncGenerateGlossaryNode: 准备阶段开始", "info")
        code_structure = shared.get("code_structure")
        if not code_structure:
            error_msg = "共享存储中缺少代码结构"
            log_and_notify(error_msg, "error", notify=True)
            return {"error": error_msg}

        core_modules = shared.get("core_modules")
        if not core_modules:
            log_and_notify("共享存储中缺少核心模块，将使用空数据", "warning")
            core_modules = {"modules": [], "architecture": "", "relationships": [], "success": True}

        history_analysis = shared.get("history_analysis")
        if not history_analysis:
            log_and_notify("共享存储中缺少历史分析，将使用空数据", "warning")
            history_analysis = {"commit_count": 0, "contributor_count": 0, "history_summary": "", "success": True}

        llm_config_shared = shared.get("llm_config")
        if llm_config_shared:
            try:
                if not self.llm_client:
                    self.llm_client = LLMClient(config=llm_config_shared)
                log_and_notify("AsyncGenerateGlossaryNode: LLMClient initialized.", "info")
            except Exception as e:
                log_and_notify(
                    f"AsyncGenerateGlossaryNode: LLMClient initialization failed: {e}. "
                    f"Node will proceed without LLM if possible, or fail.",
                    "warning",
                )
                self.llm_client = None
        else:
            log_and_notify("AsyncGenerateGlossaryNode: No LLM config found. Proceeding without LLM client.", "warning")
            self.llm_client = None

        target_language = shared.get("language", "zh")
        output_dir = shared.get("output_dir", "docs")
        repo_name = shared.get("repo_name", "default_repo")

        return {
            "code_structure": code_structure,
            "core_modules": core_modules,
            "history_analysis": history_analysis,
            "target_language": target_language,
            "output_dir": output_dir,
            "repo_name": repo_name,
            "retry_count": self.config.retry_count,
            "quality_threshold": self.config.quality_threshold,
            "model": self.config.model,
            "output_format": self.config.output_format,
        }

    async def exec_async(self, prep_res: Dict[str, Any]) -> Dict[str, Any]:
        """执行阶段，生成术语表文档

        Args:
            prep_res: 准备阶段的结果

        Returns:
            执行结果
        """
        log_and_notify("AsyncGenerateGlossaryNode: 执行阶段开始", "info")
        if "error" in prep_res:
            return {"success": False, "error": prep_res["error"]}

        code_structure = prep_res["code_structure"]
        core_modules = prep_res["core_modules"]
        history_analysis = prep_res["history_analysis"]
        target_language = prep_res["target_language"]
        output_dir = prep_res["output_dir"]
        repo_name = prep_res["repo_name"]
        retry_count = prep_res["retry_count"]
        quality_threshold = prep_res["quality_threshold"]
        model_name = prep_res["model"]
        output_format = prep_res["output_format"]

        if not self.llm_client:
            error_msg = "AsyncGenerateGlossaryNode: LLMClient 未初始化，无法生成术语表。"
            log_and_notify(error_msg, "error", notify=True)
            return {"error": error_msg, "success": False}

        prompt_str = self._create_prompt(code_structure, core_modules, history_analysis)

        for attempt in range(retry_count):
            try:
                log_and_notify(
                    f"AsyncGenerateGlossaryNode: 尝试生成术语表文档 (尝试 {attempt + 1}/{retry_count})", "info"
                )

                content, quality_score, success = await self._call_model(prompt_str, target_language, model_name)

                if success and quality_score["overall"] >= quality_threshold:
                    log_and_notify(
                        f"AsyncGenerateGlossaryNode: 成功生成术语表文档 (质量分数: {quality_score['overall']})", "info"
                    )
                    file_path = await asyncio.to_thread(
                        self._save_document, content, output_dir, output_format, repo_name
                    )
                    return {"content": content, "file_path": file_path, "quality_score": quality_score, "success": True}
                elif success:
                    log_and_notify(
                        f"AsyncGenerateGlossaryNode: 生成质量不佳 (分数: {quality_score['overall']}), 重试中...",
                        "warning",
                    )
                else:
                    log_and_notify("AsyncGenerateGlossaryNode: _call_model指示失败, 重试中...", "warning")

            except Exception as e:
                log_and_notify(f"AsyncGenerateGlossaryNode: LLM 调用或处理失败: {str(e)}, 重试中...", "warning")

            if attempt < retry_count - 1:
                await asyncio.sleep(2**attempt)

        error_msg = f"AsyncGenerateGlossaryNode: 无法生成高质量的术语表文档，已尝试 {retry_count} 次"
        log_and_notify(error_msg, "error", notify=True)
        return {"success": False, "error": error_msg}

    async def post_async(self, shared: Dict[str, Any], _: Dict[str, Any], exec_res: Dict[str, Any]) -> str:
        """后处理阶段，将术语表文档存储到共享存储中

        Args:
            shared: 共享存储
            _: 准备阶段的结果（未使用）
            exec_res: 执行阶段的结果

        Returns:
            下一个节点的动作
        """
        log_and_notify("AsyncGenerateGlossaryNode: 后处理阶段开始", "info")
        if not exec_res.get("success", False):
            shared["error"] = exec_res.get("error", "AsyncGenerateGlossaryNode: 生成术语表文档失败")
            return "error"

        shared["glossary_doc"] = {
            "content": exec_res["content"],
            "file_path": exec_res["file_path"],
            "quality_score": exec_res["quality_score"],
            "success": True,
        }
        log_and_notify("AsyncGenerateGlossaryNode: 术语表文档已存储到共享存储中", "info")
        return "default"

    def _create_prompt(
        self, code_structure: Dict[str, Any], core_modules: Dict[str, Any], history_analysis: Dict[str, Any]
    ) -> str:
        """创建提示

        Args:
            code_structure: 代码结构
            core_modules: 核心模块
            history_analysis: 历史分析

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

        simplified_history = {
            "commit_count": history_analysis.get("commit_count", 0),
            "contributor_count": history_analysis.get("contributor_count", 0),
            "history_summary": history_analysis.get("history_summary", ""),
        }

        # 获取仓库名称
        repo_name = code_structure.get("repo_name", "requests")

        # 格式化提示
        return self.config.glossary_prompt_template.format(
            repo_name=repo_name,
            code_structure=json.dumps(simplified_structure, indent=2, ensure_ascii=False),
            core_modules=json.dumps(simplified_modules, indent=2, ensure_ascii=False),
            history_analysis=json.dumps(simplified_history, indent=2, ensure_ascii=False),
        )

    async def _call_model(
        self, prompt_str: str, target_language: str, model_name: str
    ) -> Tuple[str, Dict[str, float], bool]:
        """调用 LLM 生成术语表文档 (异步)

        Args:
            prompt_str: 主提示内容
            target_language: 目标语言
            model_name: 要使用的模型名称 (包含提供商)

        Returns:
            (生成的文档内容, 质量评估分数, 是否成功)
        """
        if not self.llm_client:
            log_and_notify("AsyncGenerateGlossaryNode: LLMClient未初始化!", "error")
            return "", {}, False

        system_prompt_content = f"你是一个专业的代码库术语专家，请按照用户要求生成文档。目标语言: {target_language}。"

        messages = [
            {"role": "system", "content": system_prompt_content},
            {"role": "user", "content": prompt_str},
        ]

        # Temperature and max_tokens will be handled by self.llm_client.acompletion using its own defaults
        # if not explicitly passed or if passed as None.

        try:
            # 使用 self.llm_client 进行异步调用
            raw_response = await self.llm_client.acompletion(
                messages=messages,
                # Ensure model_name is correctly formatted (e.g., "openai/gpt-3.5-turbo")
                model=model_name,  # FIXED E501
                # temperature and max_tokens are omitted to use defaults from LLMClient instance
            )

            if not raw_response:
                log_and_notify("AsyncGenerateGlossaryNode: LLM 返回空响应", "error")
                return "", {}, False

            content = self.llm_client.get_completion_content(raw_response)
            if not content:
                log_and_notify("AsyncGenerateGlossaryNode: 从 LLM 响应中提取内容失败", "error")
                return "", {}, False

            quality_score = self._evaluate_quality(content)
            return content, quality_score, True

        except Exception as e:
            log_and_notify(f"AsyncGenerateGlossaryNode: _call_model 异常: {str(e)}", "error")
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

        expected_keywords = ["术语", "定义", "用法", "项目特定", "技术术语"]
        found_keywords = sum(1 for kw in expected_keywords if kw in content)

        score["completeness"] = min(1.0, found_keywords / len(expected_keywords) * 1.5)

        if len(content) > 100:
            score["relevance"] = 0.5
        if len(content) > 500:
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
            repo_name: 仓库名称 (用于创建子目录)

        Returns:
            文件路径
        """
        repo_specific_dir = os.path.join(output_dir, repo_name or "default_repo")
        os.makedirs(repo_specific_dir, exist_ok=True)

        # 确保使用.md扩展名
        file_ext = ".md"
        file_name = f"glossary{file_ext}"
        file_path = os.path.join(repo_specific_dir, file_name)

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            log_and_notify(f"术语表文档已保存到: {file_path}", "info")
            return file_path
        except IOError as e:
            log_and_notify(f"保存术语表文档失败: {str(e)}", "error", notify=True)
            raise
