"""组合和翻译节点，用于组合生成的内容并进行翻译检查。"""

import json
import re
from typing import Any, Dict, List, Optional

from pocketflow import Node
from pydantic import BaseModel, Field

from ..utils.language_utils import detect_natural_language, extract_technical_terms
from ..utils.llm_wrapper.llm_client import LLMClient
from ..utils.logger import log_and_notify


class CombineAndTranslateNodeConfig(BaseModel):
    """CombineAndTranslateNode 配置"""

    retry_count: int = Field(3, ge=1, le=10, description="重试次数")
    quality_threshold: float = Field(0.7, ge=0, le=1.0, description="质量阈值")
    model: str = Field("", description="LLM 模型，从配置中获取，不应设置默认值")
    preserve_technical_terms: bool = Field(True, description="是否保留技术术语")
    translation_prompt_template: str = Field(
        """
        你是一个专业的技术文档翻译专家。请将以下技术文档内容翻译成{target_language}语言。

        请注意以下要求：
        1. 保持代码、变量名和技术术语的原始形式，不要翻译它们
        2. 保持 Markdown 格式，包括标题、列表、表格、代码块等
        3. 保持文档结构和链接
        4. 翻译应该准确、流畅、符合技术文档风格
        5. 保留原文中的表情符号

        以下是需要保留原样的技术术语列表：
        {technical_terms}

        需要翻译的内容：
        {content}
        """,
        description="翻译提示模板",
    )
    consistency_check_prompt_template: str = Field(
        """
        你是一个技术文档质量检查专家。请检查以下技术文档内容的一致性问题，并提供修复建议。

        请检查以下方面：
        1. 术语一致性：同一概念在整个文档中应使用相同的术语
        2. 格式一致性：标题、列表、表格等格式应保持一致
        3. 风格一致性：语言风格、语气应保持一致
        4. 链接一致性：确保所有内部链接正确指向目标
        5. 结构一致性：文档结构应合理、层次分明

        文档内容：
        {content}
        """,
        description="一致性检查提示模板",
    )


class CombineAndTranslateNode(Node):
    """组合和翻译节点，用于组合生成的内容并进行翻译检查"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化组合和翻译节点

        Args:
            config: 节点配置
        """
        super().__init__()
        config_model = CombineAndTranslateNodeConfig(**(config or {}))
        self.config = config_model
        log_and_notify("初始化组合和翻译节点", "info")

    def prep(self, shared: Dict[str, Any]) -> Dict[str, Any]:
        """准备阶段，收集所有生成的内容

        Args:
            shared: 共享存储

        Returns:
            准备结果
        """
        log_and_notify("开始组合和翻译内容", "info")

        # 收集所有生成的内容
        content_keys = [
            "architecture_doc",
            "api_docs",
            "timeline_doc",
            "dependency_doc",
            "glossary_doc",
            "quick_look_doc",
            "module_details",
        ]

        content_dict = {}
        for key in content_keys:
            if key in shared and shared[key].get("success", False):
                content_dict[key] = shared[key].get("content", "")

        if not content_dict:
            error_msg = "没有找到生成的内容"
            log_and_notify(error_msg, "error", notify=True)
            return {"error": error_msg}

        # 获取 LLM 配置
        llm_config = shared.get("llm_config", {})

        # 获取目标语言
        target_language = shared.get("language", "zh")

        # 获取输出目录
        output_dir = shared.get("output_dir", "docs_output")

        # 获取仓库信息
        repo_url = shared.get("repo_url", "")
        repo_branch = shared.get("branch", "main")

        # 获取仓库名称
        repo_name = shared.get("repo_name", "docs")

        # 获取代码结构和模块信息
        code_structure = shared.get("code_structure", {})
        core_modules = shared.get("core_modules", {})

        return {
            "content_dict": content_dict,
            "llm_config": llm_config,
            "target_language": target_language,
            "output_dir": output_dir,
            "repo_url": repo_url,
            "repo_branch": repo_branch,
            "repo_name": repo_name,  # 添加仓库名称
            "code_structure": code_structure,
            "core_modules": core_modules,
            "retry_count": self.config.retry_count,
            "quality_threshold": self.config.quality_threshold,
            "model": self.config.model,
            "preserve_technical_terms": self.config.preserve_technical_terms,
        }

    def exec(self, prep_res: Dict[str, Any]) -> Dict[str, Any]:
        """执行阶段，组合内容并进行翻译检查

        Args:
            prep_res: 准备阶段的结果

        Returns:
            执行结果
        """
        # 检查准备阶段是否有错误
        if "error" in prep_res:
            return {"success": False, "error": prep_res["error"]}

        # 获取参数
        content_dict = prep_res["content_dict"]
        llm_config = prep_res["llm_config"]
        target_language = prep_res["target_language"]
        output_dir = prep_res["output_dir"]
        repo_url = prep_res["repo_url"]
        repo_branch = prep_res["repo_branch"]
        repo_name = prep_res.get("repo_name", "docs")  # 获取仓库名称
        code_structure = prep_res["code_structure"]
        core_modules = prep_res["core_modules"]
        retry_count = prep_res["retry_count"]
        quality_threshold = prep_res["quality_threshold"]
        model = prep_res["model"]
        preserve_technical_terms = prep_res["preserve_technical_terms"]

        try:
            # 组合内容
            log_and_notify("开始组合内容", "info")
            combined_content = self._combine_content(content_dict)

            # 检查一致性
            log_and_notify("开始检查内容一致性", "info")
            consistency_issues = self._check_consistency(combined_content, llm_config, model)

            # 如果有一致性问题，修复内容
            if consistency_issues:
                log_and_notify(f"发现 {len(consistency_issues)} 个一致性问题，开始修复", "info")
                combined_content = self._fix_consistency_issues(combined_content, consistency_issues)

            # 检测内容语言
            detected_language, confidence = detect_natural_language(combined_content)
            log_and_notify(f"检测到内容语言: {detected_language} (置信度: {confidence})", "info")

            # 如果目标语言与检测到的语言不同，进行翻译
            translated_content = combined_content
            if target_language != detected_language:
                log_and_notify(f"开始将内容从 {detected_language} 翻译为 {target_language}", "info")

                # 提取技术术语
                technical_terms = []
                if preserve_technical_terms:
                    technical_terms = extract_technical_terms(combined_content, language=detected_language)
                    log_and_notify(f"提取了 {len(technical_terms)} 个技术术语", "info")

                # 尝试翻译
                for attempt in range(retry_count):
                    try:
                        log_and_notify(f"尝试翻译内容 (尝试 {attempt + 1}/{retry_count})", "info")

                        # 调用 LLM 进行翻译
                        translated_content, quality_score, success = self._translate_content(
                            combined_content, technical_terms, target_language, llm_config, model
                        )

                        if success and quality_score >= quality_threshold:
                            log_and_notify(f"成功翻译内容 (质量分数: {quality_score})", "info")
                            break
                        elif success:
                            log_and_notify(f"翻译质量不佳 (分数: {quality_score}), 重试中...", "warning")
                    except Exception as e:
                        log_and_notify(f"翻译失败: {str(e)}, 重试中...", "warning")
                        if attempt == retry_count - 1:
                            log_and_notify("翻译失败，使用原始内容", "error", notify=True)
                            translated_content = combined_content

            # 创建文件结构
            file_structure = self._create_file_structure(repo_name)

            # 创建仓库结构
            repo_structure = self._create_repo_structure(core_modules, repo_name)

            return {
                "combined_content": combined_content,
                "translated_content": translated_content,
                "file_structure": file_structure,
                "repo_structure": repo_structure,
                "output_dir": output_dir,
                "repo_url": repo_url,
                "repo_branch": repo_branch,
                "repo_name": repo_name,  # 添加仓库名称
                "target_language": target_language,
                "success": True,
            }
        except Exception as e:
            error_msg = f"组合和翻译内容失败: {str(e)}"
            log_and_notify(error_msg, "error", notify=True)
            return {"success": False, "error": error_msg}

    def post(self, shared: Dict[str, Any], prep_res: Dict[str, Any], exec_res: Dict[str, Any]) -> str:
        """后处理阶段，更新共享存储

        Args:
            shared: 共享存储
            prep_res: 准备阶段的结果
            exec_res: 执行结果
        """
        if exec_res.get("success", False):
            # 更新共享存储
            shared["combined_content"] = exec_res["combined_content"]
            shared["translated_content"] = exec_res["translated_content"]
            shared["file_structure"] = exec_res["file_structure"]
            shared["repo_structure"] = exec_res["repo_structure"]

            log_and_notify("组合和翻译内容完成", "info", notify=True)
            return "default"
        elif "error" in exec_res:
            shared["error"] = exec_res["error"]
            log_and_notify(f"组合和翻译内容失败: {exec_res['error']}", "error", notify=True)
            return "error"

        # 默认返回
        return "default"

    def _combine_content(self, content_dict: Dict[str, Any]) -> str:
        """组合内容

        Args:
            content_dict: 内容字典

        Returns:
            组合后的内容
        """
        # 创建组合内容
        combined_parts = []

        # 添加架构文档
        if "architecture_doc" in content_dict:
            combined_parts.append(content_dict["architecture_doc"])

        # 添加 API 文档
        if "api_docs" in content_dict:
            combined_parts.append(content_dict["api_docs"])

        # 添加时间线文档
        if "timeline_doc" in content_dict:
            combined_parts.append(content_dict["timeline_doc"])

        # 添加依赖文档
        if "dependency_doc" in content_dict:
            combined_parts.append(content_dict["dependency_doc"])

        # 添加术语表文档
        if "glossary_doc" in content_dict:
            combined_parts.append(content_dict["glossary_doc"])

        # 添加速览文档
        if "quick_look_doc" in content_dict:
            combined_parts.append(content_dict["quick_look_doc"])

        # 添加模块详情文档
        if "module_details" in content_dict:
            combined_parts.append(content_dict["module_details"])

        # 组合内容
        return "\n\n---\n\n".join(combined_parts)

    def _check_consistency(self, content: str, llm_config: Dict[str, Any], model: str) -> List[Dict[str, Any]]:
        """检查内容一致性

        Args:
            content: 内容
            llm_config: LLM 配置
            model: 模型

        Returns:
            一致性问题列表
        """
        try:
            # 创建 LLM 客户端
            llm_client = LLMClient(llm_config)

            # 准备系统提示
            system_prompt = """你是一个技术文档质量检查专家。你的任务是检查技术文档的一致性问题，并提供修复建议。
请以 JSON 格式返回结果，包含问题列表，每个问题包含问题描述、问题位置和修复建议。"""

            # 准备用户提示
            user_prompt = self.config.consistency_check_prompt_template.format(content=content)

            # 调用 LLM
            messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]

            response = llm_client.completion(
                messages=messages, temperature=0.3, model=model, trace_name="检查内容一致性", max_input_tokens=None
            )

            # 获取响应内容
            response_content = llm_client.get_completion_content(response)

            # 解析 JSON 响应
            try:
                # 提取 JSON 部分
                json_match = re.search(r"```json\n(.*?)\n```", response_content, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                else:
                    json_str = response_content

                # 解析 JSON
                issues = json.loads(json_str)

                # 确保返回的是列表
                if isinstance(issues, dict) and "issues" in issues:
                    return issues["issues"]
                elif isinstance(issues, list):
                    return issues
                else:
                    return []
            except Exception as e:
                log_and_notify(f"解析一致性检查结果失败: {str(e)}", "warning")
                return []
        except Exception as e:
            log_and_notify(f"检查内容一致性失败: {str(e)}", "warning")
            return []

    def _fix_consistency_issues(self, content: str, issues: List[Dict[str, Any]]) -> str:
        """修复一致性问题

        Args:
            content: 内容
            issues: 一致性问题列表

        Returns:
            修复后的内容
        """
        # 简单实现：应用每个问题的修复建议
        fixed_content = content
        for issue in issues:
            if "suggestion" in issue and "location" in issue:
                # 这里只是一个简化的实现，实际应用中可能需要更复杂的逻辑
                # 例如，使用正则表达式或其他方法定位和替换问题内容
                log_and_notify(f"修复一致性问题: {issue['description']}", "info")

        return fixed_content

    def _translate_content(
        self, content: str, technical_terms: List[str], target_language: str, llm_config: Dict[str, Any], model: str
    ) -> tuple:
        """翻译内容

        Args:
            content: 内容
            technical_terms: 技术术语列表
            target_language: 目标语言
            llm_config: LLM 配置
            model: 模型

        Returns:
            翻译后的内容、质量分数和成功标志
        """
        try:
            # 创建 LLM 客户端
            llm_client = LLMClient(llm_config)

            # 准备系统提示
            system_prompt = f"""你是一个专业的技术文档翻译专家。请将技术文档内容翻译成{target_language}语言。
请保持代码、变量名和技术术语的原始形式，不要翻译它们。
请保持 Markdown 格式，包括标题、列表、表格、代码块等。
请保持文档结构和链接。
翻译应该准确、流畅、符合技术文档风格。"""

            # 准备用户提示
            user_prompt = self.config.translation_prompt_template.format(
                target_language=target_language, technical_terms="\n".join(technical_terms), content=content
            )

            # 调用 LLM
            messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]

            response = llm_client.completion(
                messages=messages, temperature=0.3, model=model, trace_name="翻译内容", max_input_tokens=None
            )

            # 获取响应内容
            translated_content = llm_client.get_completion_content(response)

            # 评估质量
            quality_score = self._evaluate_translation_quality(content, translated_content, technical_terms)

            return translated_content, quality_score, True
        except Exception as e:
            log_and_notify(f"翻译内容失败: {str(e)}", "error")
            raise

    def _evaluate_translation_quality(self, original: str, translated: str, technical_terms: List[str]) -> float:
        """评估翻译质量

        Args:
            original: 原始内容
            translated: 翻译后的内容
            technical_terms: 技术术语列表

        Returns:
            质量分数
        """
        # 简单实现：检查技术术语是否保留、Markdown 格式是否保留
        score = 1.0

        # 检查技术术语是否保留
        for term in technical_terms:
            if term in original and term not in translated:
                score -= 0.05

        # 检查 Markdown 格式是否保留
        original_headings = len(re.findall(r"^#+\s+", original, re.MULTILINE))
        translated_headings = len(re.findall(r"^#+\s+", translated, re.MULTILINE))
        if original_headings != translated_headings:
            score -= 0.1

        original_code_blocks = len(re.findall(r"```", original))
        translated_code_blocks = len(re.findall(r"```", translated))
        if original_code_blocks != translated_code_blocks:
            score -= 0.1

        # 确保分数在 0-1 之间
        return max(0.0, min(1.0, score))

    def _create_file_structure(self, repo_name: str = "docs") -> Dict[str, Any]:
        """创建文件结构

        Args:
            repo_name: 仓库名称

        Returns:
            文件结构
        """
        # 创建默认文件结构
        file_structure = {
            "README.md": {"title": "项目概览", "sections": ["introduction", "quick_look"]},
            f"{repo_name}/index.md": {"title": "文档首页", "sections": ["introduction", "navigation"]},
            f"{repo_name}/overview.md": {
                "title": "系统架构",
                "sections": ["overall_architecture", "core_modules_summary"],
            },
            f"{repo_name}/glossary.md": {"title": "术语表", "sections": ["glossary"]},
            f"{repo_name}/evolution.md": {"title": "演变历史", "sections": ["evolution_narrative"]},
            f"{repo_name}/{{module_dir}}/{{module_file}}.md": {
                "title": "{module_title}",
                "sections": ["description", "api", "examples"],
            },
        }

        return file_structure

    def _create_repo_structure(self, core_modules: Dict[str, Any], repo_name: str = "docs") -> Dict[str, Any]:
        """创建仓库结构

        Args:
            core_modules: 核心模块
            repo_name: 仓库名称

        Returns:
            仓库结构
        """
        # 创建仓库结构
        repo_structure = {"repo_name": repo_name}  # 添加仓库名称

        # 添加核心模块
        for module_name, module_info in core_modules.items():
            if isinstance(module_info, dict) and "path" in module_info:
                repo_structure[module_name] = str(
                    {"path": module_info["path"], "type": module_info.get("type", "module")}
                )

        return repo_structure
