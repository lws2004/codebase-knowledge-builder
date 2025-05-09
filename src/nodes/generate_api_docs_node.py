"""生成API文档节点，用于生成代码库的API文档。"""

import asyncio
import json
import os
from typing import Any, Dict, Optional, Tuple

from pocketflow import AsyncNode
from pydantic import BaseModel, Field

from ..utils.llm_wrapper import LLMClient
from ..utils.logger import log_and_notify


class GenerateApiDocsNodeConfig(BaseModel):
    """GenerateApiDocsNode 配置"""

    retry_count: int = Field(3, ge=1, le=10, description="重试次数")
    quality_threshold: float = Field(0.7, ge=0, le=1.0, description="质量阈值")
    model: str = Field("", description="LLM 模型，从配置中获取，不应设置默认值")
    output_format: str = Field("markdown", description="输出格式")
    api_docs_prompt_template: str = Field(
        "{code_structure}\n{core_modules}\n{repo_name}",  # 简单的占位符，实际模板将从配置文件中加载
        description="API文档提示模板，从配置文件中加载",
    )


class AsyncGenerateApiDocsNode(AsyncNode):
    """生成API文档节点（异步），用于生成代码库的API文档"""

    llm_client: Optional[LLMClient] = None

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化生成API文档节点 (异步)

        Args:
            config: 节点配置
        """
        super().__init__()

        # 从配置文件获取默认配置
        from ..utils.env_manager import get_node_config

        default_config = get_node_config("generate_api_docs")

        # 合并配置
        merged_config = default_config.copy()
        if config:
            merged_config.update(config)

        # 记录配置加载信息
        log_and_notify("从配置文件加载API文档生成节点配置", "debug")
        log_and_notify(f"提示模板长度: {len(merged_config.get('api_docs_prompt_template', ''))}", "debug")

        self.config = GenerateApiDocsNodeConfig(**merged_config)
        log_and_notify("初始化 AsyncGenerateApiDocsNode", "info")

    async def prep_async(self, shared: Dict[str, Any]) -> Dict[str, Any]:
        """准备阶段，从共享存储中获取必要的数据

        Args:
            shared: 共享存储

        Returns:
            准备结果或包含错误的字典
        """
        log_and_notify("AsyncGenerateApiDocsNode: 准备阶段开始", "info")
        code_structure = shared.get("code_structure")
        if not code_structure:
            error_msg = "共享存储中缺少代码结构"
            log_and_notify(error_msg, "error", notify=True)
            return {"error": error_msg}  # 返回错误

        core_modules = shared.get("core_modules")
        if not core_modules:
            log_and_notify("共享存储中缺少核心模块，将使用空数据", "warning")
            core_modules = {"modules": [], "architecture": "", "relationships": "", "success": True}
        elif not core_modules.get("success", False):
            log_and_notify("共享存储中的核心模块标记为失败，API文档可能不完整", "warning")

        llm_config_shared = shared.get("llm_config")
        if llm_config_shared:
            try:
                if not self.llm_client:
                    self.llm_client = LLMClient(config=llm_config_shared)
                log_and_notify("AsyncGenerateApiDocsNode: LLMClient initialized.", "info")
            except Exception as e:
                error_msg = f"AsyncGenerateApiDocsNode: 初始化 LLM 客户端失败: {e}"
                log_and_notify(error_msg, "error", notify=True)
                self.llm_client = None
        else:
            log_and_notify(
                "AsyncGenerateApiDocsNode: No LLM config in shared state. LLM-dependent features will fail.", "warning"
            )
            self.llm_client = None

        target_language = shared.get("language", "zh")
        output_dir = shared.get("output_dir", "docs")
        repo_name = shared.get("repo_name", "requests")  # Default to 'requests' if not found?
        log_and_notify(f"AsyncGenerateApiDocsNode.prep_async: 使用仓库名称 {repo_name}", "info")

        # Ensure repo_name consistency if code_structure is dict
        if isinstance(code_structure, dict):
            code_structure["repo_name"] = repo_name

        # Prepare data for exec_async, ensuring multi-line formatting
        prep_data = {
            "code_structure": code_structure,
            "core_modules": core_modules,
            "target_language": target_language,
            "output_dir": output_dir,
            "retry_count": self.config.retry_count,
            "quality_threshold": self.config.quality_threshold,
            "model": self.config.model,
            "output_format": self.config.output_format,
            "repo_name": repo_name,
            # Note: Removed "language" key as it's duplicated by "target_language"
            # Note: Removed non-existent "api_example" key
        }
        return prep_data

    async def exec_async(self, prep_res: Dict[str, Any]) -> Dict[str, Any]:
        """执行阶段，生成API文档

        Args:
            prep_res: 准备阶段的结果

        Returns:
            执行结果
        """
        log_and_notify("AsyncGenerateApiDocsNode: 执行阶段开始", "info")
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
        repo_name = prep_res.get("repo_name", "requests")
        log_and_notify(f"AsyncGenerateApiDocsNode.exec_async: 使用仓库名称 {repo_name}", "info")
        prompt_str = self._create_prompt(code_structure, core_modules, repo_name)
        for attempt in range(retry_count):
            try:
                log_and_notify(f"AsyncGenerateApiDocsNode: 尝试生成API文档 (尝试 {attempt + 1}/{retry_count})", "info")
                content, quality_score, success = await self._call_model(
                    prompt_str, target_language, model_name, repo_name
                )
                if success and quality_score["overall"] >= quality_threshold:
                    log_and_notify(
                        f"AsyncGenerateApiDocsNode: 成功生成API文档 (质量分数: {quality_score['overall']})", "info"
                    )
                    file_path = await asyncio.to_thread(
                        self._save_document, content, output_dir, output_format, repo_name
                    )
                    return {"content": content, "file_path": file_path, "quality_score": quality_score, "success": True}
                elif success:
                    log_and_notify(
                        f"AsyncGenerateApiDocsNode: 生成质量不佳 (分数: {quality_score['overall']}), 重试中...",
                        "warning",
                    )
                else:
                    log_and_notify("AsyncGenerateApiDocsNode: _call_model 指示失败, 重试中...", "warning")
            except Exception as e:
                log_and_notify(f"AsyncGenerateApiDocsNode: LLM 调用或处理失败: {str(e)}, 重试中...", "warning")
            if attempt < retry_count - 1:
                await asyncio.sleep(2**attempt)
        error_msg = f"AsyncGenerateApiDocsNode: 无法生成高质量的API文档，已尝试 {retry_count} 次"
        log_and_notify(error_msg, "error", notify=True)
        return {"success": False, "error": error_msg}

    async def post_async(self, shared: Dict[str, Any], _: Dict[str, Any], exec_res: Dict[str, Any]) -> str:
        """后处理阶段，将API文档存储到共享存储中

        Args:
            shared: 共享存储
            _: 准备阶段的结果（未使用）
            exec_res: 执行阶段的结果

        Returns:
            下一个节点的动作
        """
        log_and_notify("AsyncGenerateApiDocsNode: 后处理阶段开始", "info")
        if not exec_res.get("success", False):
            shared["error"] = exec_res.get("error", "AsyncGenerateApiDocsNode: 生成API文档失败")
            return "error"

        shared["api_docs"] = {
            "content": exec_res.get("content", ""),
            "file_path": exec_res.get("file_path", ""),
            "quality_score": exec_res.get("quality_score", {}),
            "success": True,
        }
        log_and_notify("AsyncGenerateApiDocsNode: API文档已存储到共享存储中", "info")
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

        # 获取模板
        template = self.config.api_docs_prompt_template

        # 替换模板中的变量，同时保留Mermaid图表中的大括号
        # 使用安全的方式替换变量，避免格式化字符串中的问题
        template = template.replace("{repo_name}", repo_name)
        template = template.replace("{code_structure}", json.dumps(simplified_structure, indent=2, ensure_ascii=False))
        template = template.replace("{core_modules}", json.dumps(simplified_modules, indent=2, ensure_ascii=False))

        return template

    async def _call_model(
        self, prompt_str: str, target_language: str, model_name: str, repo_name: str
    ) -> Tuple[str, Dict[str, float], bool]:
        """调用 LLM 生成API文档 (异步)

        Args:
            prompt_str: 主提示内容
            target_language: 目标语言
            model_name: 要使用的模型名称
            repo_name: 仓库名称 (用于系统提示)

        Returns:
            (生成的文档内容, 质量评估分数, 是否成功)
        """
        assert self.llm_client is not None, "LLMClient has not been initialized!"

        system_prompt_content = (
            f"你是一个代码库API文档专家。请根据以下信息为 {repo_name} 代码库生成一个全面的代码库API文档。"
            f"目标语言: {target_language}。请确保你的分析基于实际的 {repo_name} 代码。"
            f"使用 Markdown 格式，包含标题、列表、表格和代码块。使用表情符号使文档生动。"
        )

        messages = [
            {"role": "system", "content": system_prompt_content},
            {"role": "user", "content": prompt_str},
        ]

        try:
            raw_response = await self.llm_client.acompletion(messages=messages, model=model_name)

            if not raw_response:
                log_and_notify("AsyncGenerateApiDocsNode: LLM 返回空响应", "error")
                return "", {}, False

            content = self.llm_client.get_completion_content(raw_response)
            if not content:
                log_and_notify("AsyncGenerateApiDocsNode: 从 LLM 响应中提取内容失败", "error")
                return "", {}, False

            quality_score = self._evaluate_quality(content)
            return content, quality_score, True

        except Exception as e:
            log_and_notify(f"AsyncGenerateApiDocsNode: _call_model 异常: {str(e)}", "error")
            return "", {}, False

    def _evaluate_quality(self, content: str) -> Dict[str, float]:
        """评估内容质量

        Args:
            content: 生成内容

        Returns:
            质量分数
        """
        scores = {"completeness": 0.0, "structure": 0.0, "relevance": 0.0, "overall": 0.0}

        # 检查完整性
        required_sections = ["API概述", "核心API", "API分类", "错误处理"]

        found_sections = 0
        for section in required_sections:
            if section in content:
                found_sections += 1

        scores["completeness"] = found_sections / len(required_sections)

        # 检查结构
        structure_score = 0.0
        if "# " in content or "## " in content:
            structure_score += 0.5
        if "- " in content or "* " in content:
            structure_score += 0.3
        if "```" in content:
            structure_score += 0.2

        scores["structure"] = structure_score

        # 检查相关性
        relevance_score = 0.0
        relevance_keywords = ["API", "接口", "函数", "方法", "参数", "返回值", "示例"]
        for keyword in relevance_keywords:
            if keyword in content:
                relevance_score += 1.0 / len(relevance_keywords)

        scores["relevance"] = relevance_score

        # 计算总体分数
        scores["overall"] = scores["completeness"] * 0.4 + scores["structure"] * 0.3 + scores["relevance"] * 0.3

        return scores

    def _save_document(self, content: str, output_dir: str, _: str, repo_name: str) -> str:
        """保存文档

        Args:
            content: 文档内容
            output_dir: 输出目录
            output_format: 输出格式
            repo_name: 仓库名称

        Returns:
            文件路径
        """
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)

        # 使用传入的仓库名称
        log_and_notify(f"AsyncGenerateApiDocsNode._save_document: 使用仓库名称 {repo_name}", "debug")

        # 确保仓库目录存在
        repo_specific_dir = os.path.join(output_dir, repo_name or "default_repo")
        os.makedirs(repo_specific_dir, exist_ok=True)

        # 确定文件名和路径 - 将API文档内容整合到overview.md中
        file_name = "overview"
        # 确保使用.md扩展名
        file_ext = ".md"

        # 将文件保存到仓库子目录中
        file_path = os.path.join(repo_specific_dir, file_name + file_ext)

        # 如果文件已存在，则将API文档内容追加到文件末尾
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                existing_content = f.read()

            # 添加分隔符和API文档内容
            combined_content = existing_content + "\n\n## API文档\n\n" + content

            # 保存合并后的文档
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(combined_content)
        else:
            # 如果文件不存在，则直接保存API文档内容
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

        log_and_notify(f"API文档已整合到: {file_path}", "info")

        return file_path
