"""生成模块详细文档节点，用于生成代码库中各模块的详细文档。"""

import asyncio
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, cast

from pocketflow import AsyncNode
from pydantic import BaseModel, Field

from ..utils.llm_wrapper import LLMClient
from ..utils.logger import log_and_notify
from ..utils.mermaid_regenerator import validate_and_fix_file_mermaid
from ..utils.performance_monitor import TaskMonitoringContext
from .async_parallel_batch_node import AsyncParallelBatchNode


class GenerateModuleDetailsNodeConfig(BaseModel):
    """GenerateModuleDetailsNode 配置"""

    retry_count: int = Field(3, ge=1, le=10, description="重试次数")
    quality_threshold: float = Field(0.7, ge=0, le=1.0, description="质量阈值")
    model: str = Field("", description="LLM 模型，从配置中获取，不应设置默认值")
    output_format: str = Field("``", description="输出格式")
    max_modules_per_batch: int = Field(8, description="每批最大模块数（提升并发）")
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

        请以 ```` 格式输出，使用适当的标题、列表、表格和代码块。
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

    # 移除 _process_single_module 方法，因为它已被 ModuleProcessor 类替代

    class ModuleProcessor(AsyncNode):
        """处理单个模块文档生成的内部流程类"""

        def __init__(self, parent: "AsyncGenerateModuleDetailsNode"):
            # 初始化 AsyncNode 类
            super().__init__()
            # 初始化其他属性
            self.parent = parent

        async def prep_async(self, shared: Dict[str, Any]) -> Dict[str, Any]:
            """准备阶段，获取模块信息

            Args:
                shared: 包含模块信息和准备数据的字典

            Returns:
                准备结果
            """
            return shared

        async def exec_async(self, shared: Dict[str, Any]) -> Dict[str, Any]:
            """执行阶段，生成模块文档

            Args:
                shared: 包含模块信息和准备数据的字典

            Returns:
                执行结果
            """
            module_info = shared.get("module_info", {})
            prep_data = shared.get("prep_data", {})

            module_name = module_info.get("name", "unknown_module")
            module_path_in_repo = module_info.get("path", "")
            repo_name = prep_data["repo_name"]
            output_dir = prep_data["output_dir"]
            target_language = prep_data["target_language"]
            model = prep_data["model"]
            retry_count = prep_data["retry_count"]
            quality_threshold = prep_data["quality_threshold"]

            log_and_notify(f"AsyncGenerateModuleDetailsNode: 开始处理模块 {module_name}", "debug")

            # 开始性能监控
            task_id = f"module_{module_name}_{int(time.time())}"
            with TaskMonitoringContext(task_id):
                if not self.parent.llm_client:
                    log_and_notify(
                        f"AsyncGenerateModuleDetailsNode: Skipping module {module_name} due to missing LLM client.",
                        "error",
                    )
                    return {
                        "name": module_name,
                        "path": module_path_in_repo,
                        "success": False,
                        "error": f"LLMClientNotAvailableInModule: {module_name}",
                    }

            try:
                # 添加详细日志，记录模块处理开始
                log_and_notify(f"ModuleProcessor: 开始处理模块 {module_name}，获取代码内容", "info")

                code_content = self.parent._get_module_code(
                    module_path_in_repo, prep_data["rag_data"], prep_data["code_structure"], prep_data["repo_path"]
                )

                # 检查代码内容是否为空或过短
                if not code_content or len(code_content.strip()) < 10:
                    log_and_notify(f"ModuleProcessor: 模块 {module_name} 的代码内容为空或过短", "warning")
                    # 使用模拟内容
                    code_content = self.parent._generate_mock_module_content(module_path_in_repo)

                log_and_notify(f"ModuleProcessor: 为模块 {module_name} 创建提示", "info")
                prompt = self.parent._create_prompt(module_info, code_content)

                log_and_notify(
                    f"ModuleProcessor: 开始为模块 {module_name} 调用LLM，最大重试次数: {retry_count}", "info"
                )
                for attempt in range(retry_count):
                    try:
                        generated_content, quality_score, success = await self.parent._call_model_async(
                            prompt, target_language, model
                        )

                        if success and quality_score["overall"] >= quality_threshold:
                            # Ensure modules_dir is created (might be called concurrently)
                            repo_specific_output_dir = os.path.join(output_dir, repo_name or "default_repo")
                            modules_dir = os.path.join(repo_specific_output_dir, "modules")
                            os.makedirs(modules_dir, exist_ok=True)

                            file_name_stem = self.parent._get_module_file_name(module_info)
                            # 确保使用 .md 扩展名
                            file_path = os.path.join(modules_dir, f"{file_name_stem}.md")

                            # 处理生成的内容，确保内容完整
                            processed_content = self.parent._process_module_content(
                                generated_content, module_name, repo_name
                            )

                            # Asynchronous file write
                            await asyncio.to_thread(self.parent._save_module_file, file_path, processed_content)

                            return {
                                "name": module_name,
                                "path": module_path_in_repo,
                                "file_path": file_path,
                                "content": processed_content,
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
                return {
                    "name": module_name,
                    "path": module_path_in_repo,
                    "success": False,
                    "error": f"MaxRetriesReachedInModule: {module_name}",
                }

            except Exception as e_process:
                import traceback

                error_details = traceback.format_exc()
                detailed_error_msg = f"ModuleProcessorException: {type(e_process).__name__} - {str(e_process)}"
                log_and_notify(
                    f"AsyncGenerateModuleDetailsNode: Error processing module {module_name}: {detailed_error_msg}",
                    "error",
                )
                log_and_notify(f"详细错误信息: {error_details}", "error")
                return {
                    "name": module_name,
                    "path": module_path_in_repo,
                    "success": False,
                    "error": detailed_error_msg,
                }

        async def post_async(self, shared: Dict[str, Any], prep_res: Dict[str, Any], exec_res: Dict[str, Any]) -> str:
            """后处理阶段，返回执行结果

            Args:
                shared: 共享存储
                prep_res: 准备阶段的结果
                exec_res: 执行阶段的结果

            Returns:
                下一个节点的动作
            """
            # 将执行结果更新到共享存储
            shared.update(exec_res)
            # prep_res 参数在此方法中未使用，但需要保留以符合接口要求
            _ = prep_res
            return "default"

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

        # 创建批处理参数列表
        batch_params = []
        for module_info in modules_to_process:
            batch_params.append({"module_info": module_info, "prep_data": prep_res})

        log_and_notify(f"AsyncGenerateModuleDetailsNode: 创建 {len(batch_params)} 个模块处理任务", "info")

        # 创建一个自定义的 AsyncParallelBatchNode 子类，用于处理模块
        class ModuleBatchNode(AsyncParallelBatchNode):
            def __init__(self, parent: "AsyncGenerateModuleDetailsNode", max_concurrency: int):
                super().__init__(max_concurrency=max_concurrency)
                self.parent = parent

            async def prep_async(self, shared: Dict[str, Any]) -> List[Dict[str, Any]]:
                # shared 参数在此方法中未使用，但需要保留以符合接口要求
                _ = shared
                # 直接返回传入的批处理参数
                return batch_params

            async def exec_async(self, item: Dict[str, Any]) -> Dict[str, Any]:
                # 使用 ModuleProcessor 处理单个模块
                processor = self.parent.ModuleProcessor(self.parent)
                # 执行处理流程
                await processor.prep_async(item)
                return await processor.exec_async(item)

        # 创建批处理节点
        batch_node = ModuleBatchNode(self, self.config.max_modules_per_batch)

        # 执行批处理
        shared_copy = {"batch_params": batch_params}
        await batch_node.run_async(shared_copy)

        # 获取结果
        results_or_exceptions = shared_copy.get("batch_results", [])

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
                err_msg = f"AsyncGenerateModuleDetailsNode: 模块 {module_name} 处理失败: {res_or_exc.get('error', 'Unknown error')}"
                log_and_notify(err_msg, "error")
                errors_encountered.append({"module": module_name, "error": res_or_exc.get("error", "Unknown error")})
            elif res_or_exc is None:
                # 处理None结果，这通常是由于异常导致的回退结果
                err_msg = f"AsyncGenerateModuleDetailsNode: 模块 {module_name} 处理失败，返回了None结果，将重试"
                log_and_notify(err_msg, "warning")
                # 对于None结果，我们尝试重新处理这个模块
                try:
                    log_and_notify(f"AsyncGenerateModuleDetailsNode: 开始重试处理模块 {module_name}", "info")
                    module_info = modules_to_process[i]
                    processor = self.ModuleProcessor(self)
                    retry_item = {"module_info": module_info, "prep_data": prep_res}
                    await processor.prep_async(retry_item)
                    retry_result = await processor.exec_async(retry_item)

                    if isinstance(retry_result, dict) and retry_result.get("success"):
                        log_and_notify(f"AsyncGenerateModuleDetailsNode: 模块 {module_name} 重试成功", "info")
                        processed_module_docs.append(retry_result)
                    else:
                        log_and_notify(f"AsyncGenerateModuleDetailsNode: 模块 {module_name} 重试仍然失败", "error")
                        errors_encountered.append({"module": module_name, "error": "Retry failed after None result"})
                except Exception as retry_error:
                    log_and_notify(
                        f"AsyncGenerateModuleDetailsNode: 模块 {module_name} 重试时发生异常: {retry_error}", "error"
                    )
                    errors_encountered.append({"module": module_name, "error": f"Retry exception: {str(retry_error)}"})
            else:  # Should not happen if ModuleProcessor always returns a dict or raises
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

        # 即使所有模块处理都失败，也返回成功状态，但包含错误信息
        # 这样可以让流程继续执行，而不会因为模块处理失败而中断整个流程
        return {
            "module_docs": processed_module_docs,  # List of dicts for successfully processed modules
            "index_file_path": index_file_path,
            "errors": errors_encountered,  # List of errors encountered
            "success": True,  # 总是返回成功，让流程继续
            "has_errors": bool(errors_encountered),  # 标记是否有错误
            "error_count": len(errors_encountered),  # 错误数量
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
            "success": True,  # 总是标记为成功，让流程继续
            "partial_errors": exec_res.get("errors", []),  # Errors for specific modules or index
            "has_errors": exec_res.get("has_errors", False),  # 是否有错误
            "error_count": exec_res.get("error_count", 0),  # 错误数量
        }

        num_successful = len(exec_res.get("module_docs", []))
        num_errors = exec_res.get("error_count", len(exec_res.get("errors", [])))

        log_message = (
            f"AsyncGenerateModuleDetailsNode: 模块详细文档处理完成。成功: {num_successful}, 失败/错误: {num_errors}."
        )
        if num_errors > 0:
            log_and_notify(log_message + f" 详细错误: {exec_res.get('errors')}", "warning")
        else:
            log_and_notify(log_message, "info")

        if exec_res.get("has_errors", False) and num_errors == len(exec_res.get("modules_to_process", [])):
            # 如果所有模块都失败，返回"partial_error"
            log_and_notify(
                "AsyncGenerateModuleDetailsNode: 所有模块处理都失败，返回'partial_error'",
                "warning",
            )
            return "partial_error"

        return "default"

    def _get_module_code(
        self, module_path_in_repo: str, rag_data: Dict[str, Any], code_structure: Dict[str, Any], repo_path: str
    ) -> str:
        """获取模块的代码内容。

        优先从 RAG 数据的 file_contents 中获取。
        如果找不到，则尝试从本地文件系统中读取。
        如果仍然找不到，尝试智能匹配模块名称。

        Args:
            module_path_in_repo (str): 模块在仓库中的相对路径。
            rag_data (Dict[str, Any]): RAG 数据。
            code_structure (Dict[str, Any]): 代码结构。
            repo_path (str): 本地仓库的绝对路径。

        Returns:
            str: 模块代码内容，如果找不到则返回错误信息字符串。
        """
        # code_structure 参数在此方法中未使用，但需要保留以符合接口要求
        _ = code_structure

        try:
            # 处理模块路径
            log_and_notify(f"_get_module_code: 开始处理模块路径 {module_path_in_repo}", "info")
            module_path_in_repo = self._normalize_module_path(module_path_in_repo)
            log_and_notify(f"_get_module_code: 标准化后的模块路径 {module_path_in_repo}", "info")

            # 尝试从不同来源获取代码内容
            log_and_notify("_get_module_code: 尝试从RAG数据中精确匹配获取代码", "info")
            code_content = self._get_code_from_rag_exact_match(module_path_in_repo, rag_data)
            if code_content:
                log_and_notify(f"_get_module_code: 从RAG数据中精确匹配获取代码成功，长度: {len(code_content)}", "info")
                return code_content

            log_and_notify("_get_module_code: 尝试从RAG数据中部分匹配获取代码", "info")
            code_content = self._get_code_from_rag_partial_match(module_path_in_repo, rag_data)
            if code_content:
                log_and_notify(f"_get_module_code: 从RAG数据中部分匹配获取代码成功，长度: {len(code_content)}", "info")
                return code_content

            log_and_notify("_get_module_code: 尝试从文件系统中精确匹配获取代码", "info")
            code_content = self._get_code_from_filesystem_exact_match(module_path_in_repo, repo_path)
            if code_content:
                log_and_notify(f"_get_module_code: 从文件系统中精确匹配获取代码成功，长度: {len(code_content)}", "info")
                return code_content

            log_and_notify("_get_module_code: 尝试从文件系统中模糊匹配获取代码", "info")
            code_content = self._get_code_from_filesystem_fuzzy_match(module_path_in_repo, repo_path)
            if code_content:
                log_and_notify(f"_get_module_code: 从文件系统中模糊匹配获取代码成功，长度: {len(code_content)}", "info")
                return code_content

            # 如果所有方法都失败，生成模拟内容
            log_and_notify("_get_module_code: 所有获取代码方法都失败，生成模拟内容", "warning")
            return self._generate_mock_module_content(module_path_in_repo)
        except Exception as e:
            import traceback

            error_details = traceback.format_exc()
            log_and_notify(f"_get_module_code: 获取模块代码时出错: {str(e)}", "error")
            log_and_notify(f"_get_module_code: 详细错误信息: {error_details}", "error")
            # 出错时也返回模拟内容，而不是抛出异常
            return self._generate_mock_module_content(module_path_in_repo)

    def _normalize_module_path(self, module_path: str) -> str:
        """将模块名称标准化为文件路径

        Args:
            module_path: 原始模块路径或名称

        Returns:
            标准化后的模块路径
        """
        if not module_path.endswith((".py", ".js", ".java", ".c", ".cpp", ".go", ".rb")):
            # 尝试将模块名转换为文件路径
            module_parts = module_path.split(".")
            possible_path = "/".join(module_parts) + ".py"
            log_and_notify(f"尝试将模块名 {module_path} 转换为文件路径: {possible_path}", "info")
            return possible_path
        return module_path

    def _get_code_from_rag_exact_match(self, module_path: str, rag_data: Dict[str, Any]) -> Optional[str]:
        """从RAG数据中精确匹配获取代码

        Args:
            module_path: 模块路径
            rag_data: RAG数据

        Returns:
            匹配到的代码内容或None
        """
        if module_path in rag_data.get("file_contents", {}):
            log_and_notify(f"在RAG数据中找到精确匹配的模块: {module_path}", "info")
            return cast(str, rag_data["file_contents"][module_path])
        return None

    def _get_code_from_rag_partial_match(self, module_path: str, rag_data: Dict[str, Any]) -> Optional[str]:
        """从RAG数据中部分匹配获取代码

        Args:
            module_path: 模块路径
            rag_data: RAG数据

        Returns:
            匹配到的代码内容或None
        """
        module_name = os.path.basename(module_path)
        module_name = os.path.splitext(module_name)[0]  # 移除扩展名

        for file_path, content_from_rag in rag_data.get("file_contents", {}).items():
            if module_name in file_path:
                log_and_notify(f"在RAG数据中找到部分匹配的模块: {file_path}", "info")
                return cast(str, content_from_rag)
        return None

    def _get_code_from_filesystem_exact_match(self, module_path: str, repo_path: str) -> Optional[str]:
        """从文件系统中精确匹配获取代码

        Args:
            module_path: 模块路径
            repo_path: 仓库路径

        Returns:
            匹配到的代码内容或None
        """
        full_module_path = os.path.join(repo_path, module_path)
        try:
            with open(full_module_path, "r", encoding="utf-8") as f:
                log_and_notify(f"在文件系统中找到精确匹配的模块: {full_module_path}", "info")
                return f.read()
        except FileNotFoundError:
            log_and_notify(f"模块文件未找到: {full_module_path}，尝试智能匹配", "warning")
            return None
        except Exception as e:
            log_and_notify(f"读取模块文件 {full_module_path} 时出错: {e}", "error")
            return f"Error reading file {module_path}: {e}"

    def _get_code_from_filesystem_fuzzy_match(self, module_path: str, repo_path: str) -> Optional[str]:
        """从文件系统中模糊匹配获取代码

        Args:
            module_path: 模块路径
            repo_path: 仓库路径

        Returns:
            匹配到的代码内容或None
        """
        module_name = os.path.basename(module_path)
        module_name = os.path.splitext(module_name)[0]  # 移除扩展名

        best_match_info = self._find_best_matching_file(module_path, module_name, repo_path)
        if not best_match_info:
            return None

        best_match, best_match_score = best_match_info

        # 如果找到最佳匹配，读取文件
        if best_match and best_match_score > 5:  # 设置一个最低匹配分数阈值
            try:
                with open(best_match, "r", encoding="utf-8") as f:
                    rel_path = os.path.relpath(best_match, repo_path)
                    log_and_notify(f"在文件系统中找到最佳匹配的模块: {rel_path} (分数: {best_match_score})", "info")
                    return f.read()
            except Exception as e:
                log_and_notify(f"读取匹配的模块文件时出错: {e}", "error")
                return None
        return None

    def _find_best_matching_file(self, module_path: str, module_name: str, repo_path: str) -> Optional[Tuple[str, int]]:
        """查找最佳匹配的文件

        Args:
            module_path: 模块路径
            module_name: 模块名称
            repo_path: 仓库路径

        Returns:
            (最佳匹配文件路径, 匹配分数)元组或None
        """
        best_match = None
        best_match_score = 0

        for root, _, files in os.walk(repo_path):
            for file in files:
                if file.endswith((".py", ".js", ".java", ".c", ".cpp", ".go", ".rb")):
                    score = self._calculate_match_score(file, module_name, module_path, root, repo_path)
                    if score > best_match_score:
                        best_match = os.path.join(root, file)
                        best_match_score = score

        if best_match and best_match_score > 5:
            return (best_match, best_match_score)
        return None

    def _calculate_match_score(self, file: str, module_name: str, module_path: str, root: str, repo_path: str) -> int:
        """计算文件与模块的匹配分数

        Args:
            file: 文件名
            module_name: 模块名称
            module_path: 模块路径
            root: 当前目录
            repo_path: 仓库根目录

        Returns:
            匹配分数
        """
        score = 0
        # 文件名匹配
        if module_name in file:
            score += 5  # 文件名包含模块名
        if module_name == os.path.splitext(file)[0]:
            score += 10  # 文件名完全匹配模块名

        # 路径匹配
        rel_path = os.path.relpath(os.path.join(root, file), repo_path)
        path_parts = os.path.dirname(rel_path).split(os.sep)
        module_parts = os.path.dirname(module_path).split(os.sep)

        # 计算路径部分匹配数
        for part in module_parts:
            if part and part in path_parts:
                score += 3

        return score

    def _generate_mock_module_content(self, module_path: str) -> str:
        """生成模拟的模块内容

        Args:
            module_path: 模块路径

        Returns:
            模拟的模块内容
        """
        module_name = os.path.basename(module_path)
        module_name = os.path.splitext(module_name)[0]  # 移除扩展名

        log_and_notify(f"无法找到模块 {module_name} 的任何匹配文件，将生成模拟内容", "warning")
        return f"""
# 模拟的 {module_name} 模块
# 注意: 此内容是自动生成的，因为无法找到实际的模块文件

\"\"\"
{module_name} 模块

此模块的实际内容无法找到，这是一个自动生成的模拟内容。
文档将基于模块名称和上下文信息进行生成。
\"\"\"

# 模拟的类和函数
class {module_name.capitalize()}:
    \"\"\"
    {module_name.capitalize()} 类的模拟实现
    \"\"\"
    def __init__(self):
        \"\"\"初始化函数\"\"\"
        pass

    def process(self, data):
        \"\"\"处理数据的模拟方法\"\"\"
        return data

def main():
    \"\"\"模块主函数\"\"\"
    pass

if __name__ == "__main__":
    main()
"""

    def _create_prompt(self, module_info: Dict[str, Any], code_content: str) -> str:
        """创建单个模块的提示

        Args:
            module_info: 模块信息字典
            code_content: 模块代码内容

        Returns:
            提示字符串
        """
        # 获取模板
        template = self.config.module_details_prompt_template

        # 替换模板中的变量，同时保留Mermaid图表中的大括号
        # 使用安全的方式替换变量，避免格式化字符串中的问题
        template = template.replace("{module_info}", json.dumps(module_info, indent=2, ensure_ascii=False))
        template = template.replace("{code_content}", code_content)

        return template

    def _prepare_module_document(
        self,
        module_path_in_repo: str,
        rag_data: Dict[str, Any],
        code_structure: Dict[str, Any],
        repo_path: str,
        prep_data: Dict[str, Any],
    ) -> str:
        """准备模块文档内容

        Args:
            module_path_in_repo: 模块路径
            rag_data: RAG数据
            code_structure: 代码结构
            repo_path: 仓库路径
            prep_data: 准备阶段数据

        Returns:
            模块文档内容
        """
        # prep_data 参数在此方法中未使用，但需要保留以符合接口要求
        _ = prep_data

        # 获取模块名称
        module_name = Path(module_path_in_repo).stem

        # 获取模块代码
        module_code = self._get_module_code(module_path_in_repo, rag_data, code_structure, repo_path)

        # 构建文档内容
        content_parts = []
        content_parts.append(f"# 📦 {module_name} 模块")

        # 分析模块内容
        content_parts.append("## 🧠 分析结果")
        content_parts.append(f"- **模块名称**: {module_name}")
        content_parts.append(f"- **文件路径**: {module_path_in_repo}")
        content_parts.append(f"- **代码行数**: {len(module_code.splitlines())}")

        # 添加模块分析
        if "module_analysis" in rag_data:
            content_parts.append("\n## 📊 模块分析")
            content_parts.append(rag_data["module_analysis"])

        # 添加使用示例
        if "examples" in rag_data:
            content_parts.append("\n## 💡 使用示例")
            content_parts.append(rag_data["examples"])

        # 添加最佳实践
        if "best_practices" in rag_data:
            content_parts.append("\n## ✅ 最佳实践")
            content_parts.append(rag_data["best_practices"])

        # 添加注意事项
        if "notes" in rag_data:
            content_parts.append("\n## ⚠️ 注意事项")
            content_parts.append(rag_data["notes"])

        # 构建完整内容
        return "\n".join(content_parts)

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
            f"请详细分析代码，提供完整的模块概述、类和函数详解、使用示例、依赖关系以及注意事项和最佳实践。"
            f"生成的文档应该包含丰富的代码示例和详细的API说明，以帮助开发者理解和使用该模块。"
        )
        messages = [
            {"role": "system", "content": system_prompt_content},
            {"role": "user", "content": prompt},
        ]

        try:
            # 添加超时处理，防止LLM调用卡住
            import asyncio

            # 设置300秒超时（5分钟），因为模块文档生成可能需要更长时间
            timeout = 300
            try:
                # 使用asyncio.wait_for添加超时
                raw_response = await asyncio.wait_for(
                    self.llm_client.acompletion(messages=messages, model=model), timeout=timeout
                )
            except asyncio.TimeoutError:
                log_and_notify(f"AsyncGenerateModuleDetailsNode: LLM调用超时 ({timeout}秒)", "error")
                return "LLM调用超时，请稍后重试或检查网络连接。", {"overall": 0.0}, False

            if not raw_response:
                log_and_notify("AsyncGenerateModuleDetailsNode: LLM 返回空响应", "error")
                return "LLM返回空响应，请稍后重试。", {"overall": 0.0}, False

            content = self.llm_client.get_completion_content(raw_response)
            if not content:
                log_and_notify("AsyncGenerateModuleDetailsNode: 从 LLM 响应中提取内容失败", "error")
                return "从LLM响应中提取内容失败，请稍后重试。", {"overall": 0.0}, False

            quality_score = self._evaluate_quality(content)
            return content, quality_score, True

        except Exception as e:
            import traceback

            error_details = traceback.format_exc()
            error_msg = f"AsyncGenerateModuleDetailsNode: _call_model_async 异常: {str(e)}"
            log_and_notify(error_msg, "error")
            log_and_notify(f"详细错误信息: {error_details}", "error")
            # 返回更有用的错误信息，而不是空字符串
            return f"生成文档时出错: {str(e)}", {"overall": 0.0}, False

    def _evaluate_quality(self, content: str) -> Dict[str, float]:
        """评估生成内容的质量。

        Args:
            content (str): 生成的内容。

        Returns:
            Dict[str, float]: 包含整体、完整性、相关性和结构分数的字典。
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
        """获取模块文档的文件名 (不含扩展名)。

        Args:
            module (Dict[str, Any]): 模块信息字典。

        Returns:
            str: 文件名字符串。
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
            module_docs (List[Dict[str, Any]]): 成功生成的模块文档列表。
                                              每个字典应包含 "name", "path", "file_path"。
            target_language (str): 目标语言 (当前未使用，但可以用于本地化标题)。

        Returns:
            str: Markdown 格式的索引内容。
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

    def _process_module_content(self, content: str, module_name: str, repo_name: str) -> str:
        # 检查内容是否包含必要的部分
        has_title = bool(re.search(r"^#\s+.*", content, re.MULTILINE))
        has_overview = "概述" in content or "模块概述" in content
        has_api = "API" in content or "函数" in content or "类" in content
        has_examples = "示例" in content or "使用示例" in content

        result_parts = []

        # 添加元数据和标题
        result_parts.extend(self._prepare_metadata_and_title(content, module_name))
        content = re.sub(r"^#\s+.*\n", "", content, 1, re.MULTILINE) if has_title else content

        # 保留原内容或生成默认内容
        if content.strip() and (has_overview or has_api or has_examples):
            result_parts.append(content)
        else:
            result_parts.extend(self._generate_default_content(module_name, repo_name))

        return "".join(result_parts)

    def _prepare_metadata_and_title(self, content: str, module_name: str) -> List[str]:
        """准备元数据和标题部分"""
        parts = []
        # 添加元数据
        parts.append(f"---\ntitle: {module_name.replace('_', '.').title()}\ncategory: Modules\n---\n\n")
        # 添加标题
        title_match = re.search(r"^#\s+(.*)", content, re.MULTILINE)
        if title_match:
            parts.append(f"# 📦 {title_match.group(1)}\n\n")
        else:
            parts.append(f"# 📦 {module_name.replace('_', '.').title()}\n\n")
        return parts

    def _generate_default_content(self, module_name: str, repo_name: str) -> List[str]:
        """生成默认内容部分"""
        parts = []
        parts.extend(self._generate_default_overview(module_name, repo_name))
        parts.extend(self._generate_default_api(module_name))
        parts.extend(self._generate_default_examples(module_name))
        parts.extend(self._generate_default_dependencies(module_name, repo_name))
        parts.extend(self._generate_best_practices(module_name))
        return parts

    def _generate_default_overview(self, module_name: str, repo_name: str) -> List[str]:
        """生成默认的模块概述"""
        return [
            "## 📋 模块概述\n\n",
            "### 📝 模块名称和路径\n",
            f"- **模块名称**: `{module_name}`\n",
            f"- **模块路径**: 在{repo_name}代码库中\n\n",
        ]

    def _generate_default_api(self, module_name: str) -> List[str]:
        """生成默认的API部分"""
        return [
            "## 🔧 类和函数详解\n\n",
            "### 📦 主要类\n\n",
            f"- `{module_name.split('.')[-1].capitalize()}`: 主要类\n\n",
            "### 📦 主要函数\n\n",
            "- `main()`: 主要函数\n\n",
        ]

    def _generate_default_examples(self, module_name: str) -> List[str]:
        """生成默认的使用示例"""
        return [
            "## 💻 使用示例\n\n",
            "``python\n",
            f"# {module_name} 使用示例\n",
            f"import {module_name.split('.')[0]}\n\n",
            "# 示例代码\n",
            "```\n\n",
        ]

    def _generate_default_dependencies(self, module_name: str, repo_name: str) -> List[str]:
        """生成默认的依赖关系

        Args:
            module_name: 模块名称
            repo_name: 仓库名称

        Returns:
            依赖关系文本列表
        """
        # 确保使用module_name参数，避免IDE警告
        module_display_name = module_name.split(".")[-1]

        return [
            "## 🔄 依赖关系\n\n",
            "### 📌 该模块依赖的其他模块\n\n",
            f"- {module_display_name}模块依赖于其他{repo_name}模块\n\n",
            "### 📌 依赖该模块的其他模块\n\n",
            f"- 其他{repo_name}模块可能依赖于{module_display_name}模块\n\n",
        ]

    def _generate_best_practices(self, module_name: str) -> List[str]:
        """生成注意事项和最佳实践"""
        return [
            "## 🚀 注意事项和最佳实践\n\n",
            "### 🚩 注意事项\n\n",
            f"使用{module_name}模块时的注意事项。\n\n",
            "### 🌟 最佳实践\n\n",
            f"使用{module_name}模块的最佳实践。\n\n",
        ]

    def _save_module_file(self, file_path: str, content: str) -> None:
        """將內容保存到文件（設計為在線程中運行）。

        Args:
            file_path (str): 要保存到的文件路徑。
            content (str): 要保存的內容。
        """
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            # 立即修复文件中的 Mermaid 语法错误
            try:
                was_fixed = validate_and_fix_file_mermaid(
                    file_path, self.llm_client, f"模块文档 - {os.path.basename(file_path)}"
                )
                if was_fixed:
                    log_and_notify(f"已修复模块文件中的 Mermaid 语法错误: {file_path}", "info")
            except Exception as mermaid_error:
                log_and_notify(f"修复模块文件 Mermaid 语法错误时出错: {mermaid_error}", "warning")

        except Exception as e:
            # Log error, but don't crash the whole process, error is reported per-module
            log_and_notify(f"AsyncGenerateModuleDetailsNode: Failed to save module file {file_path}: {e}", "error")
            # Re-raise might be too disruptive if called via to_thread, let gather report it.
            # Consider how to propagate this specific file save error if needed.

    def _save_index_file(self, file_path: str, content: str) -> None:
        """將索引內容保存到文件（設計為在線程中運行）。

        Args:
            file_path (str): 要保存到的文件路徑。
            content (str): 要保存的索引內容。
        """
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            # 立即修复文件中的 Mermaid 语法错误
            try:
                was_fixed = validate_and_fix_file_mermaid(
                    file_path, self.llm_client, f"模块索引文档 - {os.path.basename(file_path)}"
                )
                if was_fixed:
                    log_and_notify(f"已修复索引文件中的 Mermaid 语法错误: {file_path}", "info")
            except Exception as mermaid_error:
                log_and_notify(f"修复索引文件 Mermaid 语法错误时出错: {mermaid_error}", "warning")

        except Exception as e:
            log_and_notify(f"AsyncGenerateModuleDetailsNode: Failed to save index file {file_path}: {e}", "error")
            # Raise error here, as index saving failure might be more critical than a single module file?
            # Or handle it within the caller (_exec_async) based on gather results.
            raise  # Re-raising allows gather to catch it
