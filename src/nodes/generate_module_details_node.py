"""生成模块详细文档节点，用于生成代码库中各模块的详细文档。"""

import asyncio
import json
import os
from typing import Any, Dict, List, Optional, Tuple

from pocketflow import AsyncNode
from pydantic import BaseModel, Field

from ..utils.llm_wrapper import LLMClient
from ..utils.logger import log_and_notify


class GenerateModuleDetailsNodeConfig(BaseModel):
    """GenerateModuleDetailsNode 配置"""

    retry_count: int = Field(3, ge=1, le=10, description="重试次数")
    quality_threshold: float = Field(0.7, ge=0, le=1.0, description="质量阈值")
    model: str = Field("", description="LLM 模型，从配置中获取，不应设置默认值")
    output_format: str = Field("markdown", description="输出格式")
    max_modules_per_batch: int = Field(5, description="每批最大模块数")
    module_details_prompt_template: str = Field(
        """
        你是一个代码库文档专家。请为以下模块生成详细的文档。

        模块信息:
        {module_info}

        代码内容:
        {code_content}

        请提供以下内容:
        1. 模块概述
           - 模块名称和路径
           - 模块的主要功能和用途
           - 模块在整个代码库中的角色
        2. 类和函数详解
           - 每个类的功能、属性和方法
           - 每个函数的功能、参数和返回值
           - 重要的代码片段解释
        3. 使用示例
           - 如何使用该模块的主要功能
           - 常见用例和模式
        4. 依赖关系
           - 该模块依赖的其他模块
           - 依赖该模块的其他模块
        5. 注意事项和最佳实践
           - 使用该模块时需要注意的事项
           - 推荐的最佳实践

        请以 Markdown 格式输出，使用适当的标题、列表、表格和代码块。
        使用表情符号使文档更加生动，例如在标题前使用适当的表情符号。
        确保文档中的代码引用能够链接到源代码。
        """,
        description="模块详细文档提示模板",
    )


class AsyncGenerateModuleDetailsNode(AsyncNode):
    """生成模块详细文档节点（异步），用于并行生成代码库中各模块的详细文档"""

    llm_client: Optional[LLMClient] = None

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化生成模块详细文档节点 (异步)

        Args:
            config: 节点配置
        """
        super().__init__()
        from ..utils.env_manager import get_node_config

        default_config = get_node_config("generate_module_details")
        merged_config = default_config.copy()
        if config:
            merged_config.update(config)
        self.config = GenerateModuleDetailsNodeConfig(**merged_config)
        log_and_notify("初始化 AsyncGenerateModuleDetailsNode", "info")

    async def prep_async(self, shared: Dict[str, Any]) -> Dict[str, Any]:
        """准备阶段，从共享存储中获取核心模块和代码结构

        Args:
            shared: 共享存储

        Returns:
            包含核心模块和代码结构的字典
        """
        log_and_notify("AsyncGenerateModuleDetailsNode: 准备阶段开始", "info")

        core_modules_data = shared.get("core_modules")
        if not core_modules_data or not core_modules_data.get("success", False):
            error_msg = "共享存储中缺少有效核心模块数据"
            log_and_notify(error_msg, "error", notify=True)
            return {"error": error_msg}

        code_structure = shared.get("code_structure")
        if not code_structure or not code_structure.get("success", False):
            error_msg = "共享存储中缺少有效代码结构"
            log_and_notify(error_msg, "error", notify=True)
            return {"error": error_msg}

        rag_data = shared.get("rag_data")  # Optional, provide default if missing
        if not rag_data:
            log_and_notify("共享存储中缺少 RAG 数据，将使用空数据", "warning")
            rag_data = {"files": [], "file_contents": {}, "chunks": [], "success": True}

        repo_path = shared.get("repo_path")
        if not repo_path:
            error_msg = "共享存储中缺少仓库路径"
            log_and_notify(error_msg, "error", notify=True)
            return {"error": error_msg}

        repo_name = shared.get("repo_name", "default_repo")

        llm_config_shared = shared.get("llm_config")
        if llm_config_shared:
            try:
                if not self.llm_client:
                    self.llm_client = LLMClient(config=llm_config_shared)
                log_and_notify("AsyncGenerateModuleDetailsNode: LLMClient initialized.", "info")
            except Exception as e:
                log_and_notify(
                    f"AsyncGenerateModuleDetailsNode: LLMClient initialization failed: {e}. "
                    f"Node will proceed without LLM if possible, or fail.",
                    "warning",
                )
                self.llm_client = None
        else:
            log_and_notify(
                "AsyncGenerateModuleDetailsNode: No LLM config found. Proceeding without LLM client.", "warning"
            )
            self.llm_client = None

        return {
            "modules_to_process": core_modules_data.get("modules", []),
            "code_structure": code_structure,
            "rag_data": rag_data,
            "repo_path": repo_path,
            "repo_name": repo_name,
            "target_language": shared.get("language", "zh"),
            "output_dir": shared.get("output_dir", "docs"),
            "retry_count": self.config.retry_count,
            "quality_threshold": self.config.quality_threshold,
            "model": self.config.model,
            "output_format": self.config.output_format,
        }

    async def _process_single_module(
        self, module_info: Dict[str, Any], prep_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """异步处理单个模块的文档生成。"""
        module_name = module_info.get("name", "unknown_module")
        module_path_in_repo = module_info.get("path", "")
        repo_name = prep_data["repo_name"]
        output_dir = prep_data["output_dir"]
        output_format = prep_data["output_format"]
        target_language = prep_data["target_language"]
        model = prep_data["model"]
        retry_count = prep_data["retry_count"]
        quality_threshold = prep_data["quality_threshold"]

        log_and_notify(f"AsyncGenerateModuleDetailsNode: 开始处理模块 {module_name}", "debug")

        if not self.llm_client:
            log_and_notify(
                f"AsyncGenerateModuleDetailsNode: Skipping module {module_name} due to missing LLM client.", "error"
            )
            return {
                "name": module_name,
                "path": module_path_in_repo,
                "success": False,
                "error": "LLM client not available",
            }

        try:
            code_content = self._get_module_code(
                module_path_in_repo, prep_data["rag_data"], prep_data["code_structure"], prep_data["repo_path"]
            )
            prompt = self._create_prompt(module_info, code_content)

            for attempt in range(retry_count):
                try:
                    generated_content, quality_score, success = await self._call_model_async(
                        prompt, target_language, model
                    )

                    if success and quality_score["overall"] >= quality_threshold:
                        # Ensure modules_dir is created (might be called concurrently)
                        repo_specific_output_dir = os.path.join(output_dir, repo_name or "default_repo")
                        modules_dir = os.path.join(repo_specific_output_dir, "modules")
                        os.makedirs(modules_dir, exist_ok=True)

                        file_name_stem = self._get_module_file_name(module_info)
                        # 确保使用 .md 扩展名
                        file_path = os.path.join(modules_dir, f"{file_name_stem}.md")

                        # Asynchronous file write
                        await asyncio.to_thread(self._save_module_file, file_path, generated_content)

                        return {
                            "name": module_name,
                            "path": module_path_in_repo,
                            "file_path": file_path,
                            "content": generated_content,
                            "quality_score": quality_score,
                            "success": True,
                        }
                    elif success:
                        log_and_notify(
                            f"AsyncGenerateModuleDetailsNode: 模块 {module_name} 生成质量不佳 "
                            f"(分数: {quality_score['overall']}), 重试 {attempt + 1}",
                            "warning",
                        )
                    else:
                        log_and_notify(
                            f"AsyncGenerateModuleDetailsNode: 模块 {module_name} _call_model_async 指示失败, "
                            f"重试 {attempt + 1}",
                            "warning",
                        )

                except Exception as e_call:
                    log_and_notify(
                        f"AsyncGenerateModuleDetailsNode: 模块 {module_name} LLM调用失败 "
                        f"(尝试 {attempt + 1}): {e_call}",
                        "warning",
                    )

                if attempt < retry_count - 1:
                    await asyncio.sleep(2**attempt)

            log_and_notify(f"AsyncGenerateModuleDetailsNode: 模块 {module_name} 所有重试均失败", "error")
            return {"name": module_name, "path": module_path_in_repo, "success": False, "error": "Max retries reached"}

        except Exception as e_process:
            log_and_notify(
                f"AsyncGenerateModuleDetailsNode: 处理模块 {module_name} 时发生意外错误: {e_process}", "error"
            )
            return {"name": module_name, "path": module_path_in_repo, "success": False, "error": str(e_process)}

    async def exec_async(self, prep_res: Dict[str, Any]) -> Dict[str, Any]:
        """执行阶段，并行生成所有模块的详细文档

        Args:
            prep_res: 准备阶段的结果

        Returns:
            包含所有成功生成的模块文档信息和任何错误的字典
        """
        log_and_notify("AsyncGenerateModuleDetailsNode: 执行阶段开始 - 并行处理模块", "info")

        if "error" in prep_res:
            return {"error": prep_res["error"], "success": False, "module_docs": []}

        modules_to_process = prep_res.get("modules_to_process", [])
        if not modules_to_process:
            log_and_notify("AsyncGenerateModuleDetailsNode: 没有找到核心模块进行处理", "warning")
            return {
                "module_docs": [],
                "success": True,
                "index_file_path": None,
            }  # No modules, but not an error state for the node itself

        # Create tasks for each module to be processed by _process_single_module
        tasks = [self._process_single_module(module_info, prep_res) for module_info in modules_to_process]

        log_and_notify(f"AsyncGenerateModuleDetailsNode: 创建 {len(tasks)} 个模块处理任务", "info")

        # Run all module processing tasks concurrently
        # gather will return a list of results (dicts from _process_single_module)
        # or exceptions if a task raised one directly (though _process_single_module tries to catch)
        results_or_exceptions = await asyncio.gather(*tasks, return_exceptions=True)

        log_and_notify("AsyncGenerateModuleDetailsNode: 所有模块处理任务完成", "info")

        processed_module_docs = []
        errors_encountered = []

        for i, res_or_exc in enumerate(results_or_exceptions):
            module_name = modules_to_process[i].get("name", f"Module_{i + 1}")
            if isinstance(res_or_exc, Exception):
                err_msg = f"AsyncGenerateModuleDetailsNode: 任务处理模块 {module_name} 时发生未捕获异常: {res_or_exc}"
                log_and_notify(err_msg, "error")
                errors_encountered.append({"module": module_name, "error": str(res_or_exc)})
            elif isinstance(res_or_exc, dict) and res_or_exc.get("success"):
                processed_module_docs.append(res_or_exc)
            elif isinstance(res_or_exc, dict) and not res_or_exc.get("success"):
                err_msg = f"AsyncGenerateModuleDetailsNode: 模块 {module_name} 处理失败: "
                f"{res_or_exc.get('error', 'Unknown error')}"
                log_and_notify(err_msg, "error")
                errors_encountered.append({"module": module_name, "error": res_or_exc.get("error", "Unknown error")})
            else:  # Should not happen if _process_single_module always returns a dict or raises
                err_msg = f"AsyncGenerateModuleDetailsNode: 模块 {module_name} 返回了意外结果: {res_or_exc}"
                log_and_notify(err_msg, "error")
                errors_encountered.append({"module": module_name, "error": "Unexpected result type"})

        # Generate index file for successfully processed modules
        index_content = ""
        index_file_path = None
        if processed_module_docs:
            try:
                index_content = self._generate_index(processed_module_docs, prep_res["target_language"])
                # Save index file (inside repo_name/modules directory)
                repo_specific_output_dir = os.path.join(prep_res["output_dir"], prep_res["repo_name"] or "default_repo")
                modules_dir = os.path.join(repo_specific_output_dir, "modules")
                os.makedirs(modules_dir, exist_ok=True)  # Ensure dir exists

                # 确保使用 .md 扩展名
                index_file_path = os.path.join(modules_dir, "index.md")
                await asyncio.to_thread(self._save_index_file, index_file_path, index_content)
                log_and_notify(f"AsyncGenerateModuleDetailsNode: 模块索引文件已保存到: {index_file_path}", "info")
            except Exception as e_index:
                log_and_notify(f"AsyncGenerateModuleDetailsNode: 生成或保存模块索引文件失败: {e_index}", "error")
                errors_encountered.append({"module": "index_generation", "error": str(e_index)})
                index_file_path = None  # Ensure it's None if saving failed

        return {
            "module_docs": processed_module_docs,  # List of dicts for successfully processed modules
            "index_file_path": index_file_path,
            "errors": errors_encountered,  # List of errors encountered
            "success": not errors_encountered,  # Overall success if no errors
        }

    async def post_async(self, shared: Dict[str, Any], _: Dict[str, Any], exec_res: Dict[str, Any]) -> str:
        """后处理阶段，将模块详细文档信息存储到共享存储中

        Args:
            shared: 共享存储
            _: 准备阶段的结果（未使用）
            exec_res: 执行阶段的结果

        Returns:
            下一个节点的动作
        """
        log_and_notify("AsyncGenerateModuleDetailsNode: 后处理阶段开始", "info")

        # Check for catastrophic failure (e.g., from prep_async, or if exec_async itself failed fundamentally)
        if not exec_res.get("success", False) and "module_docs" not in exec_res:
            error_msg = exec_res.get("error", "AsyncGenerateModuleDetailsNode: 执行阶段未知错误或无模块处理")
            log_and_notify(f"AsyncGenerateModuleDetailsNode: 生成模块详细文档失败: {error_msg}", "error", notify=True)
            shared["module_details"] = {
                "error": error_msg,
                "success": False,
                "docs": [],
                "index_file_path": None,
                "partial_errors": [],
            }
            return "error"

        # Store results, including potential partial errors
        shared["module_details"] = {
            "docs": exec_res.get("module_docs", []),  # Successfully generated module docs
            "index_file_path": exec_res.get("index_file_path"),
            "success": exec_res.get("success", True),  # Overall success of the node
            "partial_errors": exec_res.get("errors", []),  # Errors for specific modules or index
        }

        num_successful = len(exec_res.get("module_docs", []))
        num_errors = len(exec_res.get("errors", []))

        log_message = (
            f"AsyncGenerateModuleDetailsNode: 模块详细文档处理完成。成功: {num_successful}, 失败/错误: {num_errors}."
        )
        if num_errors > 0:
            log_and_notify(log_message + f" 详细错误: {exec_res.get('errors')}", "warning")
        else:
            log_and_notify(log_message, "info")

        if not exec_res.get("success", True):
            # If exec overall failed (likely due to partial errors), return "partial_error"
            log_and_notify(
                "AsyncGenerateModuleDetailsNode: Returning 'partial_error' due to exec_res success flag being False.",
                "warning",
            )
            return "partial_error"

        return "default"

    def _get_module_code(
        self, module_path_in_repo: str, rag_data: Dict[str, Any], code_structure: Dict[str, Any], repo_path: str
    ) -> str:
        """获取模块代码内容

        优先从 RAG 数据的 file_contents 中获取。
        如果找不到，则尝试从本地文件系统中读取。
        如果仍然找不到，尝试智能匹配模块名称。

        Args:
            module_path_in_repo: 模块在仓库中的相对路径
            rag_data: RAG 数据
            code_structure: 代码结构
            repo_path: 本地仓库的绝对路径

        Returns:
            模块代码内容，如果找不到则返回错误信息字符串
        """
        # Try to get from rag_data first
        if module_path_in_repo in rag_data.get("file_contents", {}):
            return rag_data["file_contents"][module_path_in_repo]

        # Fallback to reading from file system
        full_module_path = os.path.join(repo_path, module_path_in_repo)
        try:
            with open(full_module_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            log_and_notify(f"模块文件未找到: {full_module_path}，尝试智能匹配", "warning")

            # 尝试智能匹配模块名称
            module_name = os.path.basename(module_path_in_repo)
            module_name = os.path.splitext(module_name)[0]  # 移除扩展名

            # 1. 尝试在 RAG 数据中查找包含模块名的文件
            for file_path, content in rag_data.get("file_contents", {}).items():
                if module_name in file_path:
                    log_and_notify(f"在 RAG 数据中找到匹配的模块: {file_path}", "info")
                    return content

            # 2. 尝试在文件系统中查找
            for root, _, files in os.walk(repo_path):
                for file in files:
                    if module_name in file and file.endswith((".py", ".js", ".java", ".c", ".cpp", ".go", ".rb")):
                        rel_path = os.path.relpath(os.path.join(root, file), repo_path)
                        log_and_notify(f"在文件系统中找到匹配的模块: {rel_path}", "info")
                        try:
                            with open(os.path.join(root, file), "r", encoding="utf-8") as f:
                                return f.read()
                        except Exception as e:
                            log_and_notify(f"读取匹配的模块文件时出错: {e}", "error")

            # 如果仍然找不到，返回错误信息
            log_and_notify(f"无法找到模块 {module_name} 的任何匹配文件", "error")
            return f"Error: File not found at {module_path_in_repo} and no matching files found"
        except Exception as e:
            log_and_notify(f"读取模块文件 {full_module_path} 时出错: {e}", "error")
            return f"Error reading file {module_path_in_repo}: {e}"

    def _create_prompt(self, module_info: Dict[str, Any], code_content: str) -> str:
        """创建单个模块的提示

        Args:
            module_info: 模块信息字典
            code_content: 模块代码内容

        Returns:
            提示字符串
        """
        return self.config.module_details_prompt_template.format(
            module_info=json.dumps(module_info, indent=2, ensure_ascii=False), code_content=code_content
        )

    async def _call_model_async(
        self, prompt: str, target_language: str, model: str
    ) -> Tuple[str, Dict[str, float], bool]:
        """调用 LLM 生成模块详细文档 (异步)

        Args:
            prompt: 主提示内容
            target_language: 目标语言
            model: 要使用的模型名称

        Returns:
            (生成的文档内容, 质量评估分数, 是否成功)
        """
        assert self.llm_client is not None, "LLMClient has not been initialized!"

        system_prompt_content = (
            f"你是一个代码库文档专家，请按照用户要求为指定模块生成详细文档。目标语言: {target_language}。"
            f"请确保你的分析是基于实际提供的模块信息和代码内容。"
        )
        messages = [
            {"role": "system", "content": system_prompt_content},
            {"role": "user", "content": prompt},
        ]

        try:
            raw_response = await self.llm_client.acompletion(messages=messages, model=model)
            if not raw_response:
                log_and_notify("AsyncGenerateModuleDetailsNode: LLM 返回空响应", "error")
                return "", {}, False

            content = self.llm_client.get_completion_content(raw_response)
            if not content:
                log_and_notify("AsyncGenerateModuleDetailsNode: 从 LLM 响应中提取内容失败", "error")
                return "", {}, False

            quality_score = self._evaluate_quality(content)
            return content, quality_score, True

        except Exception as e:
            log_and_notify(f"AsyncGenerateModuleDetailsNode: _call_model_async 异常: {str(e)}", "error")
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
        expected_sections = ["模块概述", "类和函数详解", "使用示例", "依赖关系", "注意事项"]
        found_sections = sum(1 for section in expected_sections if section in content)
        score["completeness"] = found_sections / len(expected_sections)

        # Structure based on markdown elements
        if "##" in content:
            score["structure"] += 0.2  # Headers
        if "###" in content:
            score["structure"] += 0.2
        if "- " in content or "* " in content:
            score["structure"] += 0.2  # Lists
        if "```" in content:
            score["structure"] += 0.2  # Code blocks
        if any(table_marker in content for table_marker in ["| ---", "|:---"]):
            score["structure"] += 0.2  # Tables
        score["structure"] = min(1.0, score["structure"])

        # Relevance (simple checks for now)
        # A more advanced check could parse module_info_for_eval (e.g., module name, key functions)
        # and see if they are mentioned in the content.
        relevance_score = 0.0
        if "模块" in content and "功能" in content:
            relevance_score += 0.5
        if len(content) > 200:
            relevance_score += 0.3  # Very basic length check
        if len(content) > 500:
            relevance_score += 0.2
        score["relevance"] = min(1.0, relevance_score)

        score["overall"] = score["completeness"] * 0.4 + score["structure"] * 0.3 + score["relevance"] * 0.3
        score["overall"] = min(1.0, score["overall"])

        log_and_notify(f"质量评估完成: {score}", "debug")
        return score

    def _get_module_file_name(self, module: Dict[str, Any]) -> str:
        """获取模块文档的文件名 (不含扩展名)

        Args:
            module: 模块信息字典

        Returns:
            文件名字符串
        """
        module_name = module.get("name", "unknown_module")
        # Sanitize module name for use as a filename
        # Replace path separators and other problematic characters
        file_name = module_name.replace(os.path.sep, "_").replace("/", "_").replace("\\\\", "_")
        # Remove or replace other invalid filename characters (simplified example)
        file_name = "".join(c if c.isalnum() or c in ["_", "-"] else "_" for c in file_name)
        return file_name if file_name else "module"

    def _generate_index(self, module_docs: List[Dict[str, Any]], target_language: str) -> str:
        """为生成的模块文档创建索引文件内容。

        Args:
            module_docs: 成功生成的模块文档列表。
                          每个字典应包含 "name", "path", "file_path"。
            target_language: 目标语言 (当前未使用，但可以用于本地化标题)。

        Returns:
            Markdown 格式的索引内容。
        """
        if not module_docs:
            return "模块文档为空。\n"

        title = "📚 模块文档索引"
        if target_language == "en":
            title = "📚 Module Documentation Index"

        lines = [f"# {title}\n\n"]
        lines.append("## 📋 概述\n\n")
        lines.append(
            "本文档包含对代码库中各个模块的详细说明。通过这些文档，您可以了解每个模块的功能、API和使用方法。\n\n"
        )

        lines.append("## 📦 模块列表\n\n")
        lines.append("下表列出了所有可用的模块文档：\n\n")
        lines.append("| 模块名称 | 模块路径 | 文档链接 |")
        lines.append("|---|---|---|")

        for doc in sorted(module_docs, key=lambda x: x.get("name", "")):
            name = doc.get("name", "N/A")
            module_repo_path = doc.get("path", "N/A")  # Original path in repo
            # file_path is absolute, need relative path from modules/index.md to modules/module_file.md
            # Assuming index.md is in "modules" dir, and module files are also in "modules" dir.
            doc_file_name = os.path.basename(doc.get("file_path", ""))
            # 确保链接使用 .md 扩展名
            doc_file_name_md = os.path.splitext(doc_file_name)[0] + ".md"
            relative_link = f"./{doc_file_name_md}"  # Link from modules/index.md to modules/xxxx.md

            # 使用不带扩展名的文件名作为显示名称
            display_name = os.path.splitext(doc_file_name)[0]
            lines.append(f"| {name} | `{module_repo_path}` | [{display_name}]({relative_link}) |")

        lines.append("\n")
        return "\n".join(lines)

    def _save_module_file(self, file_path: str, content: str) -> None:
        """Saves content to a file (designed to be run in a thread)."""
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            # Log error, but don't crash the whole process, error is reported per-module
            log_and_notify(f"AsyncGenerateModuleDetailsNode: Failed to save module file {file_path}: {e}", "error")
            # Re-raise might be too disruptive if called via to_thread, let gather report it.
            # Consider how to propagate this specific file save error if needed.

    def _save_index_file(self, file_path: str, content: str) -> None:
        """Saves index content to a file (designed to be run in a thread)."""
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            log_and_notify(f"AsyncGenerateModuleDetailsNode: Failed to save index file {file_path}: {e}", "error")
            # Raise error here, as index saving failure might be more critical than a single module file?
            # Or handle it within the caller (_exec_async) based on gather results.
            raise  # Re-raising allows gather to catch it
