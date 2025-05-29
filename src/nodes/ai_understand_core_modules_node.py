"""AI 理解核心模块节点，用于使用 AI 理解代码库的核心模块。"""

import asyncio
import json
import os
import re
from typing import Any, Dict, Optional, Tuple, cast

from pocketflow import AsyncNode
from pydantic import BaseModel, Field

from ..utils.llm_wrapper import LLMClient
from ..utils.logger import log_and_notify


class AIUnderstandCoreModulesNodeConfig(BaseModel):
    """AIUnderstandCoreModulesNode 配置"""

    retry_count: int = Field(3, ge=1, le=10, description="重试次数")
    quality_threshold: float = Field(0.7, ge=0, le=1.0, description="质量阈值")
    model: str = Field("", description="LLM 模型，从配置中获取，不应设置默认值")
    language_detection: bool = Field(True, description="是否检测语言")
    terminology_extraction: bool = Field(True, description="是否提取术语")
    core_modules_prompt_template: str = Field(
        "{code_structure}\n{dependencies}\n{repo_name}",  # 简单的占位符，实际模板将从配置文件中加载
        description="核心模块提示模板，从配置文件中加载",
    )


class AsyncAIUnderstandCoreModulesNode(AsyncNode):
    """AI 理解核心模块节点（异步），用于使用 AI 理解代码库的核心模块"""

    llm_client: Optional[LLMClient] = None

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化 AI 理解核心模块节点 (异步)

        Args:
            config: 节点配置
        """
        super().__init__()
        from ..utils.env_manager import get_node_config

        default_config = get_node_config("ai_understand_core_modules")
        merged_config = default_config.copy()
        if config:
            merged_config.update(config)

        # 记录配置加载信息
        log_and_notify("从配置文件加载AI理解核心模块节点配置", "debug")
        log_and_notify(f"提示模板长度: {len(merged_config.get('core_modules_prompt_template', ''))}", "debug")

        self.config = AIUnderstandCoreModulesNodeConfig(**merged_config)
        log_and_notify("初始化 AsyncAIUnderstandCoreModulesNode", "info")

    async def prep_async(self, shared: Dict[str, Any]) -> Dict[str, Any]:
        """准备阶段，从共享存储中获取代码结构

        Args:
            shared: 共享存储

        Returns:
            包含代码结构的字典
        """
        log_and_notify("AsyncAIUnderstandCoreModulesNode: 准备阶段开始", "info")

        code_structure = shared.get("code_structure")
        if not code_structure:
            error_msg = "共享存储中缺少代码结构 (AsyncAIUnderstandCoreModulesNode)"
            log_and_notify(error_msg, "error", notify=True)
            return {"error": error_msg}
        if not code_structure.get("success", False):
            error_msg = "代码结构无效 (AsyncAIUnderstandCoreModulesNode)"
            log_and_notify(error_msg, "error", notify=True)
            return {"error": error_msg}

        llm_config_shared = shared.get("llm_config")
        if llm_config_shared:
            try:
                log_and_notify(
                    f"DEBUG: llm_config_shared in AsyncAIUnderstandCoreModulesNode: {llm_config_shared}", "debug"
                )
                if not self.llm_client:
                    self.llm_client = LLMClient(config=llm_config_shared)
                log_and_notify("AsyncAIUnderstandCoreModulesNode: LLMClient initialized.", "info")
            except Exception as e:
                log_and_notify(
                    f"AsyncAIUnderstandCoreModulesNode: LLMClient initialization failed: {e}. "
                    f"Node will proceed without LLM features if possible or fail in exec.",
                    "warning",
                )
                self.llm_client = None
        else:
            log_and_notify(
                "AsyncAIUnderstandCoreModulesNode: No LLM config in shared state. "
                "LLM-dependent features will fail if not handled.",
                "warning",
            )
            self.llm_client = None

        repo_name = shared.get("repo_name", "docs")
        log_and_notify(f"AsyncAIUnderstandCoreModulesNode.prep_async: 从共享存储中获取仓库名称 {repo_name}", "info")

        if isinstance(code_structure, dict) and "repo_name" not in code_structure:
            code_structure["repo_name"] = repo_name

        return {
            "code_structure": code_structure,
            "target_language": shared.get("language", "zh"),
            "retry_count": self.config.retry_count,
            "quality_threshold": self.config.quality_threshold,
            "model": self.config.model,
            "repo_name": repo_name,
        }

    async def exec_async(self, prep_res: Dict[str, Any]) -> Dict[str, Any]:
        """执行阶段，异步使用 AI 理解代码库的核心模块

        Args:
            prep_res: 准备阶段的结果

        Returns:
            理解结果
        """
        log_and_notify("AsyncAIUnderstandCoreModulesNode: 执行阶段开始", "info")

        if "error" in prep_res:
            return {"error": prep_res["error"], "success": False}

        # 使用解构赋值简化代码
        code_structure = prep_res["code_structure"]
        target_language, retry_count = prep_res["target_language"], prep_res["retry_count"]
        quality_threshold, model_name = prep_res["quality_threshold"], prep_res["model"]
        repo_name = prep_res.get("repo_name", "docs")
        log_and_notify(f"AsyncAIUnderstandCoreModulesNode.exec_async: 使用仓库名称 {repo_name}", "info")

        if not self.llm_client:
            error_msg = "AsyncAIUnderstandCoreModulesNode: LLMClient 未初始化，无法执行核心模块理解。"
            log_and_notify(error_msg, "error", notify=True)
            return {"error": error_msg, "success": False}

        dependencies = "暂无依赖关系信息"
        prompt_str = self._create_prompt(code_structure, dependencies)

        for attempt in range(retry_count):
            try:
                log_and_notify(
                    f"AsyncAIUnderstandCoreModulesNode: 尝试理解核心模块 (尝试 {attempt + 1}/{retry_count})", "info"
                )
                parsed_result, quality_score, success = await self._call_model_async(
                    prompt_str, target_language, model_name, repo_name
                )

                if success and quality_score["overall"] >= quality_threshold:
                    log_and_notify(
                        f"AsyncAIUnderstandCoreModulesNode: 成功理解核心模块 (质量分数: {quality_score['overall']})",
                        "info",
                    )
                    return {
                        "core_modules": parsed_result.get("core_modules", []),
                        "architecture": parsed_result.get("architecture", ""),
                        "module_relationships": parsed_result.get("module_relationships", []),
                        "quality_score": quality_score,
                        "success": True,
                    }
                elif success:
                    log_and_notify(
                        f"AsyncAIUnderstandCoreModulesNode: 理解质量不佳 (分数: {quality_score['overall']}), 重试中...",
                        "warning",
                    )
                else:
                    log_and_notify("AsyncAIUnderstandCoreModulesNode: _call_model_async 指示失败, 重试中...", "warning")

            except Exception as e:
                log_and_notify(f"AsyncAIUnderstandCoreModulesNode: LLM 调用或处理失败: {str(e)}, 重试中...", "warning")

            if attempt < retry_count - 1:
                await asyncio.sleep(2**attempt)

        error_msg = f"AsyncAIUnderstandCoreModulesNode: 无法理解核心模块，{retry_count} 次尝试后失败"
        log_and_notify(error_msg, "error", notify=True)
        return {"error": error_msg, "success": False}

    async def post_async(self, shared: Dict[str, Any], _: Dict[str, Any], exec_res: Dict[str, Any]) -> str:
        """后处理阶段，将理解结果存储到共享存储中

        Args:
            shared: 共享存储
            _: 准备阶段的结果（未使用）
            exec_res: 执行阶段的结果

        Returns:
            下一个节点的动作
        """
        log_and_notify("AsyncAIUnderstandCoreModulesNode: 后处理阶段开始", "info")

        if not exec_res.get("success", False):
            error_msg = exec_res.get("error", "AsyncAIUnderstandCoreModulesNode: 未知执行错误")
            log_and_notify(f"理解核心模块失败: {error_msg}", "error", notify=True)
            shared["core_modules"] = {"error": error_msg, "success": False}
            return "error"

        shared["core_modules"] = {
            "details": exec_res.get("core_modules", {}),
            "modules": exec_res.get("core_modules", []),
            "architecture": exec_res.get("architecture", ""),
            "module_relationships": exec_res.get("module_relationships", ""),
            "raw_output": exec_res.get("raw_output", ""),
            "quality_score": exec_res.get("quality_score", {}),
            "success": True,
        }

        log_and_notify(
            f"AsyncAIUnderstandCoreModulesNode: 核心模块理解完成并存入共享存储. "
            f"模块数: {len(exec_res.get('core_modules', []))}",
            "info",
            notify=True,
        )
        return "default"

    def _create_prompt(self, code_structure: Dict[str, Any], dependencies: str) -> str:
        """创建提示

        Args:
            code_structure: 代码结构 (应包含 repo_name)
            dependencies: 依赖关系字符串

        Returns:
            提示字符串
        """
        simplified_structure = {
            "file_count": code_structure.get("file_count", 0),
            "directory_count": code_structure.get("directory_count", 0),
            "language_stats": code_structure.get("language_stats", {}),
            "file_types": code_structure.get("file_types", {}),
            "directories": self._simplify_directories(code_structure.get("directories", {})),
        }
        repo_name = code_structure.get("repo_name", "docs")
        dumped_code_structure = json.dumps(simplified_structure, indent=2, ensure_ascii=False)
        template_str = str(self.config.core_modules_prompt_template)
        return template_str.format(
            repo_name=repo_name,
            code_structure=dumped_code_structure,
            dependencies=dependencies,
        )

    def _simplify_directories(self, directories: Dict[str, Any]) -> Dict[str, Any]:
        """简化目录结构以便放入提示，仅保留顶层目录。

        Args:
            directories: 完整的目录结构字典

        Returns:
            仅包含顶层目录键的字典
        """
        simplified: Dict[str, Any] = {}
        for path, _ in directories.items():
            normalized_path = path.strip(os.path.sep)
            if os.path.sep not in normalized_path:
                simplified[path] = {}
        return simplified

    async def _call_model_async(
        self, prompt_str: str, target_language: str, model_name: str, repo_name: str
    ) -> Tuple[Dict[str, Any], Dict[str, float], bool]:
        """调用 LLM (异步)

        Args:
            prompt_str: 提示
            target_language: 目标语言
            model_name: 模型名称
            repo_name: 仓库名称 (for system prompt)

        Returns:
            (解析后的结果字典, 质量分数, 成功标志)
        """
        assert self.llm_client is not None, "LLMClient not initialized!"

        system_prompt = (
            f"你是一个代码库分析专家，请为 {repo_name} 代码库识别核心模块和关系。"
            f"请用{target_language}语言回答。以JSON格式返回结果，包含三个键: 'core_modules', 'architecture', "
            f"'module_relationships'。"
            f"'core_modules' 的值应该是一个列表，每个元素是一个包含 'name', 'path', 'description', "
            f"'importance', 'dependencies' 键的字典。"
            f"确保使用 {repo_name} 中的实际模块名和路径。"
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt_str},
        ]

        raw_content = ""
        try:
            raw_response = await self.llm_client.acompletion(messages=messages, model=model_name)
            if not raw_response:
                log_and_notify("AsyncAIUnderstandCoreModulesNode: LLM 返回空响应", "error")
                return {"raw_output": raw_content}, {}, False

            raw_content = self.llm_client.get_completion_content(raw_response)
            if not raw_content:
                log_and_notify("AsyncAIUnderstandCoreModulesNode: 从 LLM 响应中提取内容失败", "error")
                return {"raw_output": raw_content}, {}, False

            parsed_result = self._extract_json(raw_content)
            if not parsed_result:
                log_and_notify("AsyncAIUnderstandCoreModulesNode: 解析LLM JSON响应失败", "error")
                return {"raw_output": raw_content, "parsed_result_error": "JSON parsing failed"}, {}, False

            try:
                parsed_result = self._validate_llm_output(parsed_result)
            except ValueError as ve:
                log_and_notify(f"AsyncAIUnderstandCoreModulesNode: LLM output validation error: {ve}", "error")
                return {"raw_output": raw_content, "parsed_result_error": f"Validation error: {ve}"}, {}, False

            if "core_modules" not in parsed_result:
                log_and_notify(
                    "AsyncAIUnderstandCoreModulesNode: 'core_modules' missing after validation, critical failure.",
                    "error",
                )
                return (
                    {"raw_output": raw_content, "parsed_result_error": "'core_modules' missing post-validation"},
                    {},
                    False,
                )

            parsed_result["raw_output"] = raw_content
            quality_score = self._evaluate_quality(parsed_result)
            return parsed_result, quality_score, True

        except Exception as e:
            log_and_notify(f"AsyncAIUnderstandCoreModulesNode: _call_model_async 异常: {str(e)}", "error")
            return {"raw_output": raw_content, "error": str(e)}, {}, False

    def _extract_json(self, content: str) -> Dict[str, Any]:
        """从可能包含代码块标记的字符串中提取 JSON 内容。

        Args:
            content: LLM 返回的原始字符串

        Returns:
            解析后的 JSON 字典，如果失败则返回空字典。
        """
        try:
            match = re.search(r"```(?:json)?\s*({.*?})\s*```", content, re.DOTALL)
            if match:
                json_str = match.group(1)
            else:
                first_brace = content.find("{")
                last_brace = content.rfind("}")
                if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                    json_str = content[first_brace : last_brace + 1]
                else:
                    log_and_notify(
                        "AsyncAIUnderstandCoreModulesNode: No JSON code block or clear JSON structure found. Content: "
                        + content[:200]
                        + "...",
                        "warning",
                    )
                    return {}

            json_str_cleaned = re.sub(r",[\s]*([}\]])", r"\1", json_str)
            return cast(Dict[str, Any], json.loads(json_str_cleaned))

        except json.JSONDecodeError as e:
            log_and_notify(
                f"AsyncAIUnderstandCoreModulesNode: JSON 解析错误: {e}. "
                f"Original JSON string part: {json_str[:200] if 'json_str' in locals() else content[:200]}...",
                "error",
            )
        except Exception as e_re:
            log_and_notify(f"AsyncAIUnderstandCoreModulesNode: 提取 JSON 时发生一般错误: {e_re}", "error")
        return {}

    def _evaluate_quality(self, result: Dict[str, Any]) -> Dict[str, float]:
        """评估理解结果的质量。

        Args:
            result: 解析后的 LLM 结果字典。

        Returns:
            质量分数字典。
        """
        score = {"overall": 0.0, "completeness": 0.0, "structure": 0.0, "relevance": 0.0}

        required_keys = ["core_modules", "architecture", "module_relationships"]
        found_keys_count = 0
        for k in required_keys:
            if k in result and result[k]:
                found_keys_count += 1
        score["completeness"] = found_keys_count / len(required_keys)

        structure_score = 0.0
        if "core_modules" in result and isinstance(result["core_modules"], list) and result["core_modules"]:
            module_keys_present = 0
            required_module_keys = ["name", "path", "description", "importance"]
            first_module = result["core_modules"][0]
            if isinstance(first_module, dict):
                module_keys_present = sum(1 for mk in required_module_keys if mk in first_module and first_module[mk])
            structure_score = module_keys_present / len(required_module_keys)
        elif "core_modules" in result and isinstance(result["core_modules"], list):
            structure_score = 0.5
        score["structure"] = structure_score

        score["relevance"] = 0.5
        if score["completeness"] > 0.8 and score["structure"] > 0.5:
            score["relevance"] = 0.8
        if result.get("architecture") and isinstance(result["architecture"], str) and len(result["architecture"]) > 50:
            score["relevance"] = min(1.0, score["relevance"] + 0.2)

        score["overall"] = score["completeness"] * 0.4 + score["structure"] * 0.3 + score["relevance"] * 0.3
        score["overall"] = min(1.0, score["overall"])

        log_and_notify(f"核心模块理解质量评估完成: {score}", "debug")
        return score

    def _validate_llm_output(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """验证 LLM 输出的结构和完整性。尝试修复或填充缺失的可选部分。"""
        log_and_notify("开始验证 LLM 输出结构...", "debug")

        # 验证基本结构
        result = self._validate_base_structure(result)

        # 验证核心模块
        if isinstance(result["core_modules"], list):
            result["core_modules"] = self._validate_core_modules(result["core_modules"])

        log_and_notify("LLM 输出结构验证完成。", "debug")
        return result

    def _validate_base_structure(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """验证LLM输出的基本结构。

        Args:
            result: LLM输出结果

        Returns:
            验证后的结果

        Raises:
            ValueError: 如果结果不是字典
        """
        if not isinstance(result, dict):
            log_and_notify(f"LLM output is not a dictionary: {type(result)}. Content: {str(result)[:200]}", "error")
            raise ValueError("LLM output is not a dictionary.")

        if "core_modules" not in result or not isinstance(result["core_modules"], list):
            log_and_notify("'core_modules' 键缺失或不是列表。将设置为空列表，但这可能表示严重问题。", "warning")
            result["core_modules"] = []

        if "architecture" not in result or not isinstance(result["architecture"], str):
            log_and_notify("'architecture' 键缺失或类型不正确，将设置为空字符串。", "warning")
            result["architecture"] = ""

        if "module_relationships" not in result or not isinstance(result["module_relationships"], str):
            log_and_notify("'module_relationships' 键缺失或类型不正确，将设置为空字符串。", "warning")
            result["module_relationships"] = ""

        return result

    def _validate_core_modules(self, core_modules: list) -> list:
        """验证核心模块列表。

        Args:
            core_modules: 核心模块列表

        Returns:
            验证后的核心模块列表
        """
        module_template_keys = ["name", "path", "description", "importance", "dependencies"]
        validated_modules = []

        for i, module_item in enumerate(core_modules):
            if not isinstance(module_item, dict):
                log_and_notify(f"core_modules[{i}] 不是字典，已跳过: {str(module_item)[:100]}", "warning")
                continue

            # 验证并修复模块中的键
            module_item = self._validate_module_keys(module_item, module_template_keys, i)

            # 验证并修复特定类型的字段
            module_item = self._validate_module_field_types(module_item, i)

            validated_modules.append(module_item)

        return validated_modules

    def _validate_module_keys(self, module_item: Dict[str, Any], required_keys: list, index: int) -> Dict[str, Any]:
        """验证模块中的键是否存在，如果不存在则添加默认值。

        Args:
            module_item: 模块项
            required_keys: 必需的键列表
            index: 模块在列表中的索引

        Returns:
            验证后的模块项
        """
        for key in required_keys:
            if key not in module_item:
                log_and_notify(
                    f"core_modules[{index}] (name: {module_item.get('name', 'Unknown')}) 缺少键 '{key}'。使用默认值。",
                    "debug",
                )
                if key == "dependencies":
                    module_item[key] = []
                elif key == "importance":
                    module_item[key] = 0
                else:
                    module_item[key] = f"Missing {key}"

        return module_item

    def _validate_module_field_types(self, module_item: Dict[str, Any], index: int) -> Dict[str, Any]:
        """验证模块中特定字段的类型，如果类型不正确则修复。

        Args:
            module_item: 模块项
            index: 模块在列表中的索引

        Returns:
            验证后的模块项
        """
        if not isinstance(module_item.get("importance"), (int, float)):
            log_and_notify(
                f"core_modules[{index}] (name: {module_item.get('name')}) 'importance' 类型不正确。"
                f"应该是数字。收到: {module_item.get('importance')}",
                "warning",
            )
            module_item["importance"] = 0

        if not isinstance(module_item.get("dependencies"), list):
            log_and_notify(
                f"core_modules[{index}] (name: {module_item.get('name')}) 'dependencies' 类型不正确。"
                f"应该是列表。收到: {module_item.get('dependencies')}",
                "warning",
            )
            module_item["dependencies"] = []

        return module_item
