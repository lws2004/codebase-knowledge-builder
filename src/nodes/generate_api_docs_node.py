"""生成API文档节点，用于生成代码库的API文档。"""
import json
import os
from typing import Any, Dict, Optional, Tuple

from pocketflow import Node
from pydantic import BaseModel, Field

from ..utils.llm_wrapper.llm_client import LLMClient
from ..utils.logger import log_and_notify


class GenerateApiDocsNodeConfig(BaseModel):
    """GenerateApiDocsNode 配置"""
    retry_count: int = Field(3, ge=1, le=10, description="重试次数")
    quality_threshold: float = Field(0.7, ge=0, le=1.0, description="质量阈值")
    model: str = Field("${LLM_MODEL:-gpt-4}", description="LLM 模型")
    output_format: str = Field("markdown", description="输出格式")
    api_docs_prompt_template: str = Field(
        """
        你是一个代码库API文档专家。请根据以下信息生成一个全面的代码库API文档。

        代码库结构:
        {code_structure}

        核心模块:
        {core_modules}

        请提供以下内容:
        1. API概述
           - 主要API接口和功能
           - API设计原则和约定
        2. 核心API详解
           - 每个核心API的功能和用法
           - 参数说明和返回值
           - 使用示例
        3. API分类
           - 按功能分类的API列表
           - 每类API的主要用途
        4. 错误处理
           - 常见错误码和含义
           - 错误处理最佳实践
        5. 版本兼容性（如果适用）
           - 版本间的API变化
           - 向后兼容性考虑

        请以 Markdown 格式输出，使用适当的标题、列表、表格和代码块。
        使用表情符号使文档更加生动，例如在标题前使用适当的表情符号。
        确保文档中的代码引用能够链接到源代码。
        """,
        description="API文档提示模板"
    )

class GenerateApiDocsNode(Node):
    """生成API文档节点，用于生成代码库的API文档"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化生成API文档节点

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

        self.config = GenerateApiDocsNodeConfig(**merged_config)
        log_and_notify("初始化生成API文档节点", "info")

    def prep(self, shared: Dict[str, Any]) -> Dict[str, Any]:
        """准备阶段，从共享存储中获取必要的数据

        Args:
            shared: 共享存储

        Returns:
            准备结果
        """
        # 从共享存储中获取代码结构
        code_structure = shared.get("code_structure")
        if not code_structure:
            error_msg = "共享存储中缺少代码结构"
            log_and_notify(error_msg, "error", notify=True)
            return {"error": error_msg}

        # 从共享存储中获取核心模块
        core_modules = shared.get("core_modules")
        if not core_modules:
            log_and_notify("共享存储中缺少核心模块，将使用空数据", "warning")
            core_modules = {"modules": [], "architecture": "", "relationships": [], "success": True}

        # 获取 LLM 配置
        llm_config = shared.get("llm_config", {})

        # 获取目标语言
        target_language = shared.get("language", "zh")

        # 获取输出目录
        output_dir = shared.get("output_dir", "docs")

        return {
            "code_structure": code_structure,
            "core_modules": core_modules,
            "llm_config": llm_config,
            "target_language": target_language,
            "output_dir": output_dir,
            "retry_count": self.config.retry_count,
            "quality_threshold": self.config.quality_threshold,
            "model": self.config.model,
            "output_format": self.config.output_format,
        }

    def exec(self, prep_res: Dict[str, Any]) -> Dict[str, Any]:
        """执行阶段，生成API文档

        Args:
            prep_res: 准备阶段的结果

        Returns:
            执行结果
        """
        # 检查准备阶段是否有错误
        if "error" in prep_res:
            return {"success": False, "error": prep_res["error"]}

        # 获取必要的数据
        code_structure = prep_res["code_structure"]
        core_modules = prep_res["core_modules"]
        llm_config = prep_res["llm_config"]
        target_language = prep_res["target_language"]
        output_dir = prep_res["output_dir"]
        retry_count = prep_res["retry_count"]
        quality_threshold = prep_res["quality_threshold"]
        model = prep_res["model"]
        output_format = prep_res["output_format"]

        # 准备提示
        prompt = self._create_prompt(code_structure, core_modules)

        # 尝试调用 LLM
        for attempt in range(retry_count):
            try:
                log_and_notify(f"尝试生成API文档 (尝试 {attempt + 1}/{retry_count})", "info")

                # 调用 LLM
                content, quality_score, success = self._call_model(
                    llm_config, prompt, target_language, model
                )

                if success and quality_score["overall"] >= quality_threshold:
                    log_and_notify(f"成功生成API文档 (质量分数: {quality_score['overall']})", "info")

                    # 保存文档
                    file_path = self._save_document(content, output_dir, output_format)

                    return {
                        "content": content,
                        "file_path": file_path,
                        "quality_score": quality_score,
                        "success": True
                    }
                elif success:
                    log_and_notify(
                        f"生成质量不佳 (分数: {quality_score['overall']}), 重试中...",
                        "warning"
                    )
            except Exception as e:
                log_and_notify(f"LLM 调用失败: {str(e)}, 重试中...", "warning")

        # 所有重试都失败
        error_msg = f"无法生成高质量的API文档，已尝试 {retry_count} 次"
        log_and_notify(error_msg, "error", notify=True)
        return {"success": False, "error": error_msg}

    def post(self, shared: Dict[str, Any], prep_res: Dict[str, Any], exec_res: Dict[str, Any]) -> str:
        """后处理阶段，将API文档存储到共享存储中

        Args:
            shared: 共享存储
            prep_res: 准备阶段的结果
            exec_res: 执行阶段的结果

        Returns:
            下一个节点的动作
        """
        if not exec_res.get("success", False):
            shared["error"] = exec_res.get("error", "生成API文档失败")
            return "error"

        # 将API文档存储到共享存储中
        shared["api_docs"] = {
            "content": exec_res["content"],
            "file_path": exec_res["file_path"],
            "quality_score": exec_res["quality_score"],
            "success": True
        }

        log_and_notify("API文档已存储到共享存储中", "info")
        return "default"

    def _create_prompt(
        self,
        code_structure: Dict[str, Any],
        core_modules: Dict[str, Any]
    ) -> str:
        """创建提示

        Args:
            code_structure: 代码结构
            core_modules: 核心模块

        Returns:
            提示
        """
        # 简化代码结构，避免提示过长
        simplified_structure = {
            "file_count": code_structure.get("file_count", 0),
            "directory_count": code_structure.get("directory_count", 0),
            "language_stats": code_structure.get("language_stats", {}),
            "file_types": code_structure.get("file_types", {})
        }

        # 简化核心模块
        simplified_modules = {
            "modules": core_modules.get("modules", []),
            "architecture": core_modules.get("architecture", ""),
            "relationships": core_modules.get("relationships", [])
        }

        # 格式化提示
        return self.config.api_docs_prompt_template.format(
            code_structure=json.dumps(simplified_structure, indent=2, ensure_ascii=False),
            core_modules=json.dumps(simplified_modules, indent=2, ensure_ascii=False)
        )

    def _call_model(
        self,
        llm_config: Dict[str, Any],
        prompt: str,
        target_language: str,
        model: str
    ) -> Tuple[str, Dict[str, float], bool]:
        """调用 LLM

        Args:
            llm_config: LLM 配置
            prompt: 提示
            target_language: 目标语言
            model: 模型

        Returns:
            生成内容、质量分数和成功标志
        """
        try:
            # 创建 LLM 客户端
            llm_client = LLMClient(llm_config)

            # 准备系统提示
            system_prompt = f"""你是一个代码库API文档专家，擅长分析代码库并生成全面的API文档。
请用{target_language}语言回答，但保持代码、变量名和技术术语的原始形式。
你的回答应该是格式良好的 Markdown，使用适当的标题、列表、表格和代码块。
使用表情符号使文档更加生动，例如在标题前使用适当的表情符号。
确保文档中的代码引用能够链接到源代码。"""

            # 调用 LLM
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]

            response = llm_client.completion(
                messages=messages,
                temperature=0.3,
                model=model,
                trace_name="生成API文档"
            )

            # 获取响应内容
            content = llm_client.get_completion_content(response)

            # 评估质量
            quality_score = self._evaluate_quality(content)

            return content, quality_score, True
        except Exception as e:
            log_and_notify(f"调用 LLM 失败: {str(e)}", "error")
            raise

    def _evaluate_quality(self, content: str) -> Dict[str, float]:
        """评估内容质量

        Args:
            content: 生成内容

        Returns:
            质量分数
        """
        scores = {
            "completeness": 0.0,
            "structure": 0.0,
            "relevance": 0.0,
            "overall": 0.0
        }

        # 检查完整性
        required_sections = [
            "API概述", "核心API", "API分类", "错误处理"
        ]

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
        scores["overall"] = (
            scores["completeness"] * 0.4 +
            scores["structure"] * 0.3 +
            scores["relevance"] * 0.3
        )

        return scores

    def _save_document(self, content: str, output_dir: str, output_format: str) -> str:
        """保存文档

        Args:
            content: 文档内容
            output_dir: 输出目录
            output_format: 输出格式

        Returns:
            文件路径
        """
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)

        # 确定文件名
        file_name = "api"
        file_ext = ".md" if output_format == "markdown" else f".{output_format}"
        file_path = os.path.join(output_dir, file_name + file_ext)

        # 保存文档
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        log_and_notify(f"API文档已保存到: {file_path}", "info")

        return file_path
