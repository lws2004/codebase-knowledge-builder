"""生成速览文档节点，用于生成代码库的速览文档。"""

import asyncio
import json
import os
from typing import Any, Dict, Optional, Tuple

from pocketflow import AsyncNode
from pydantic import BaseModel, Field

from ..utils.llm_wrapper import LLMClient
from ..utils.logger import log_and_notify


class GenerateQuickLookNodeConfig(BaseModel):
    """GenerateQuickLookNode 配置"""

    retry_count: int = Field(3, ge=1, le=10, description="重试次数")
    quality_threshold: float = Field(0.7, ge=0, le=1.0, description="质量阈值")
    model: str = Field("", description="LLM 模型，从配置中获取，不应设置默认值")
    output_format: str = Field("markdown", description="输出格式")
    quick_look_prompt_template: str = Field(
        """
        你是一个代码库分析专家。请根据以下信息生成一个简洁的代码库速览文档，让读者能在5分钟内了解这个代码库的核心内容。

        代码库结构:
        {code_structure}

        核心模块:
        {core_modules}

        历史分析:
        {history_analysis}

        请提供以下内容:
        1. 项目概述 (1-2段)
           - 项目的主要目的和功能
           - 核心价值和应用场景
        2. 关键特性 (5-7个要点)
           - 最重要的功能和特性
           - 每个特性的简短描述
        3. 技术栈概览 (简短列表)
           - 主要编程语言和框架
           - 关键依赖和工具
        4. 架构速览 (简短描述)
           - 核心架构模式
           - 主要组件及其关系
        5. 快速上手指南 (3-5个步骤)
           - 如何快速开始使用
           - 基本使用示例

        请以 Markdown 格式输出，使用简洁明了的语言，避免冗长的解释。
        使用表情符号使文档更加生动，例如在标题前使用适当的表情符号。
        整个文档应该简短精炼，让读者能在5分钟内阅读完毕。
        """,
        description="速览提示模板",
    )


class AsyncGenerateQuickLookNode(AsyncNode):
    """生成速览文档节点（异步），用于生成代码库的速览文档"""

    llm_client: Optional[LLMClient] = None

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化生成速览文档节点 (异步)

        Args:
            config: 节点配置
        """
        super().__init__()
        from ..utils.env_manager import get_node_config

        default_config = get_node_config("generate_quick_look")
        merged_config = default_config.copy()
        if config:
            merged_config.update(config)
        self.config = GenerateQuickLookNodeConfig(**merged_config)
        log_and_notify("初始化 AsyncGenerateQuickLookNode", "info")

    async def prep_async(self, shared: Dict[str, Any]) -> Dict[str, Any]:
        """准备阶段，从共享存储中获取必要的数据

        Args:
            shared: 共享存储

        Returns:
            准备结果
        """
        log_and_notify("AsyncGenerateQuickLookNode: 准备阶段开始", "info")
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
                log_and_notify("AsyncGenerateQuickLookNode: LLMClient initialized.", "info")
            except Exception as e:
                log_and_notify(
                    f"AsyncGenerateQuickLookNode: LLMClient initialization failed: {e}. "
                    f"Node will proceed without LLM if possible, or fail.",
                    "warning",
                )
                self.llm_client = None
        else:
            log_and_notify("AsyncGenerateQuickLookNode: No LLM config found. Proceeding without LLM client.", "warning")
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
        """执行阶段，生成速览文档

        Args:
            prep_res: 准备阶段的结果

        Returns:
            执行结果
        """
        log_and_notify("AsyncGenerateQuickLookNode: 执行阶段开始", "info")
        if "error" in prep_res:
            return {"success": False, "error": prep_res["error"]}

        # 使用解构赋值简化代码
        code_structure, core_modules, history_analysis = (
            prep_res["code_structure"],
            prep_res["core_modules"],
            prep_res["history_analysis"],
        )
        target_language, output_dir, repo_name = (
            prep_res["target_language"],
            prep_res["output_dir"],
            prep_res["repo_name"],
        )
        retry_count, quality_threshold = prep_res["retry_count"], prep_res["quality_threshold"]
        model_name, output_format = prep_res["model"], prep_res["output_format"]

        if not self.llm_client:
            error_msg = "AsyncGenerateQuickLookNode: LLMClient 未初始化，无法生成速览文档。"
            log_and_notify(error_msg, "error", notify=True)
            return {"error": error_msg, "success": False}

        prompt_str = self._create_prompt(code_structure, core_modules, history_analysis)

        for attempt in range(retry_count):
            try:
                log_and_notify(
                    f"AsyncGenerateQuickLookNode: 尝试生成速览文档 (尝试 {attempt + 1}/{retry_count})", "info"
                )
                content, quality_score, success = await self._call_model(prompt_str, target_language, model_name)
                if success and quality_score["overall"] >= quality_threshold:
                    log_and_notify(
                        f"AsyncGenerateQuickLookNode: 成功生成速览文档 (质量分数: {quality_score['overall']})", "info"
                    )
                    file_path = await asyncio.to_thread(
                        self._save_document, content, output_dir, output_format, repo_name
                    )
                    return {"content": content, "file_path": file_path, "quality_score": quality_score, "success": True}
                elif success:
                    log_and_notify(
                        f"AsyncGenerateQuickLookNode: 生成质量不佳 (分数: {quality_score['overall']}), 重试中...",
                        "warning",
                    )
                else:
                    log_and_notify("AsyncGenerateQuickLookNode: _call_model 指示失败, 重试中...", "warning")
            except Exception as e:
                log_and_notify(f"AsyncGenerateQuickLookNode: LLM 调用或处理失败: {str(e)}, 重试中...", "warning")
            if attempt < retry_count - 1:
                await asyncio.sleep(2**attempt)

        error_msg = f"AsyncGenerateQuickLookNode: 无法生成高质量的速览文档，已尝试 {retry_count} 次"
        log_and_notify(error_msg, "error", notify=True)
        return {"success": False, "error": error_msg}

    async def post_async(self, shared: Dict[str, Any], _: Dict[str, Any], exec_res: Dict[str, Any]) -> str:
        """后处理阶段，将速览文档存储到共享存储中

        Args:
            shared: 共享存储
            _: 准备阶段的结果（未使用）
            exec_res: 执行阶段的结果

        Returns:
            下一个节点的动作
        """
        log_and_notify("AsyncGenerateQuickLookNode: 后处理阶段开始", "info")
        if not exec_res.get("success", False):
            error_msg = exec_res.get("error", "AsyncGenerateQuickLookNode: 生成速览文档失败")
            shared["error"] = error_msg
            shared["quick_look_doc"] = {
                "error": error_msg,
                "success": False,
            }  # Ensure specific doc key is updated on error
            return "error"
        shared["quick_look_doc"] = {
            "content": exec_res.get("content", ""),
            "file_path": exec_res.get("file_path", ""),
            "quality_score": exec_res.get("quality_score", {}),
            "success": True,
        }
        log_and_notify("AsyncGenerateQuickLookNode: 速览文档已存储到共享存储中", "info")
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

        # 获取仓库名称
        repo_name = code_structure.get("repo_name", "docs")

        # 获取模板
        template = self.config.quick_look_prompt_template

        # 替换模板中的变量，同时保留Mermaid图表中的大括号
        # 使用安全的方式替换变量，避免格式化字符串中的问题
        template = template.replace("{repo_name}", repo_name)
        template = template.replace("{code_structure}", json.dumps(simplified_structure, indent=2, ensure_ascii=False))
        template = template.replace("{core_modules}", json.dumps(simplified_modules, indent=2, ensure_ascii=False))
        template = template.replace("{history_analysis}", json.dumps(simplified_history, indent=2, ensure_ascii=False))

        return template

    async def _call_model(
        self, prompt_str: str, target_language: str, model_name: str
    ) -> Tuple[str, Dict[str, float], bool]:
        """调用 LLM 生成速览文档 (异步)

        Args:
            prompt_str: 主提示内容
            target_language: 目标语言
            model_name: 要使用的模型名称

        Returns:
            (生成的文档内容, 质量评估分数, 是否成功)
        """
        assert self.llm_client is not None, "LLMClient has not been initialized!"
        system_prompt_content = (
            f"你是一个代码库分析专家，请按照用户要求生成简洁的速览文档。目标语言: {target_language}。"
            f"确保内容简明扼要，适合快速阅读。"
        )
        messages = [
            {"role": "system", "content": system_prompt_content},
            {"role": "user", "content": prompt_str},
        ]
        try:
            raw_response = await self.llm_client.acompletion(messages=messages, model=model_name)
            if not raw_response:
                log_and_notify("AsyncGenerateQuickLookNode: LLM 返回空响应", "error")
                return "", {}, False
            content = self.llm_client.get_completion_content(raw_response)
            if not content:
                log_and_notify("AsyncGenerateQuickLookNode: 从 LLM 响应中提取内容失败", "error")
                return "", {}, False
            quality_score = self._evaluate_quality(content)
            return content, quality_score, True
        except Exception as e:
            log_and_notify(f"AsyncGenerateQuickLookNode: _call_model 异常: {str(e)}", "error")
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
        expected_keywords = ["项目概述", "关键特性", "技术栈", "架构速览", "快速上手"]
        found_keywords = sum(1 for kw in expected_keywords if kw in content)
        score["completeness"] = min(1.0, found_keywords / len(expected_keywords) * 1.5)
        # Quick look should be concise
        if 100 < len(content) < 2000:  # Arbitrary length check for quick look
            score["relevance"] = 1.0
        elif len(content) <= 100:
            score["relevance"] = 0.2
        else:  # Too long
            score["relevance"] = 0.5

        score["overall"] = min(1.0, (score["completeness"] + score["relevance"]) / 2)
        score["overall"] = min(1.0, score["overall"])
        log_and_notify(f"速览文档质量评估完成: {score}", "debug")
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
        # Ensure repo-specific directory exists
        repo_specific_dir = os.path.join(output_dir, repo_name or "default_repo")
        try:
            os.makedirs(repo_specific_dir, exist_ok=True)
        except OSError as e:
            log_and_notify(f"创建目录失败 {repo_specific_dir}: {e}", "error")
            raise

        # 确保使用.md扩展名
        file_ext = ".md"
        file_name = f"quick_look{file_ext}"
        file_path = os.path.join(repo_specific_dir, file_name)

        try:
            # This part runs in a thread via asyncio.to_thread
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            log_and_notify(f"速览文档已保存到: {file_path}", "info")

            # 立即修复文件中的 Mermaid 语法错误
            try:
                was_fixed = validate_and_fix_file_mermaid(file_path, self.llm_client, f"文档 - {repo_name}")
                if was_fixed:
                    log_and_notify(f"已修复文件中的 Mermaid 语法错误: {file_path}", "info")
            except Exception as e:
                log_and_notify(f"修复 Mermaid 语法错误时出错: {str(e)}", "warning")

            return file_path
        except IOError as e:
            log_and_notify(f"保存速览文档失败: {str(e)}", "error", notify=True)
            raise
