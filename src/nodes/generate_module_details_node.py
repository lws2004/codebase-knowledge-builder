"""生成模块详细文档节点，用于生成代码库中各模块的详细文档。"""

import asyncio
import json
import os
import re
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

                        # 处理生成的内容，确保内容完整
                        processed_content = self._process_module_content(generated_content, module_name, repo_name)

                        # Asynchronous file write
                        await asyncio.to_thread(self._save_module_file, file_path, processed_content)

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
        # 处理模块路径
        # 如果模块路径是一个模块名而不是文件路径，尝试转换为文件路径
        if not module_path_in_repo.endswith((".py", ".js", ".java", ".c", ".cpp", ".go", ".rb")):
            # 尝试将模块名转换为文件路径
            module_parts = module_path_in_repo.split(".")
            possible_path = "/".join(module_parts) + ".py"
            log_and_notify(f"尝试将模块名 {module_path_in_repo} 转换为文件路径: {possible_path}", "info")
            module_path_in_repo = possible_path

        # Try to get from rag_data first - 尝试精确匹配
        if module_path_in_repo in rag_data.get("file_contents", {}):
            log_and_notify(f"在RAG数据中找到精确匹配的模块: {module_path_in_repo}", "info")
            return rag_data["file_contents"][module_path_in_repo]

        # 尝试在RAG数据中查找部分匹配
        module_name = os.path.basename(module_path_in_repo)
        module_name = os.path.splitext(module_name)[0]  # 移除扩展名

        # 尝试在RAG数据中查找包含模块名的文件
        for file_path, content in rag_data.get("file_contents", {}).items():
            if module_name in file_path:
                log_and_notify(f"在RAG数据中找到部分匹配的模块: {file_path}", "info")
                return content

        # Fallback to reading from file system - 尝试精确匹配
        full_module_path = os.path.join(repo_path, module_path_in_repo)
        try:
            with open(full_module_path, "r", encoding="utf-8") as f:
                log_and_notify(f"在文件系统中找到精确匹配的模块: {full_module_path}", "info")
                return f.read()
        except FileNotFoundError:
            log_and_notify(f"模块文件未找到: {full_module_path}，尝试智能匹配", "warning")

            # 尝试在文件系统中查找部分匹配
            best_match = None
            best_match_score = 0

            for root, _, files in os.walk(repo_path):
                for file in files:
                    if file.endswith((".py", ".js", ".java", ".c", ".cpp", ".go", ".rb")):
                        # 计算匹配分数
                        score = 0
                        if module_name in file:
                            score += 5  # 文件名包含模块名
                        if module_name == os.path.splitext(file)[0]:
                            score += 10  # 文件名完全匹配模块名

                        # 检查路径匹配
                        rel_path = os.path.relpath(os.path.join(root, file), repo_path)
                        path_parts = os.path.dirname(rel_path).split(os.sep)
                        module_parts = os.path.dirname(module_path_in_repo).split(os.sep)

                        # 计算路径部分匹配数
                        for part in module_parts:
                            if part and part in path_parts:
                                score += 3

                        if score > best_match_score:
                            best_match = os.path.join(root, file)
                            best_match_score = score

            # 如果找到最佳匹配，读取文件
            if best_match and best_match_score > 5:  # 设置一个最低匹配分数阈值
                try:
                    with open(best_match, "r", encoding="utf-8") as f:
                        rel_path = os.path.relpath(best_match, repo_path)
                        log_and_notify(f"在文件系统中找到最佳匹配的模块: {rel_path} (分数: {best_match_score})", "info")
                        return f.read()
                except Exception as e:
                    log_and_notify(f"读取匹配的模块文件时出错: {e}", "error")

            # 如果仍然找不到，返回一个模拟的模块内容
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
        # 获取模板
        template = self.config.module_details_prompt_template

        # 替换模板中的变量，同时保留Mermaid图表中的大括号
        # 使用安全的方式替换变量，避免格式化字符串中的问题
        template = template.replace("{module_info}", json.dumps(module_info, indent=2, ensure_ascii=False))
        template = template.replace("{code_content}", code_content)

        return template

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

    def _process_module_content(self, content: str, module_name: str, repo_name: str) -> str:
        """处理模块内容，确保内容完整

        Args:
            content: LLM生成的原始内容
            module_name: 模块名称
            repo_name: 仓库名称

        Returns:
            处理后的内容
        """
        # 检查内容是否包含必要的部分
        has_title = bool(re.search(r"^#\s+.*", content, re.MULTILINE))
        has_overview = "概述" in content or "模块概述" in content
        has_api = "API" in content or "函数" in content or "类" in content
        has_examples = "示例" in content or "使用示例" in content
        has_dependencies = "依赖" in content or "依赖关系" in content
        has_best_practices = "最佳实践" in content or "注意事项" in content

        # 构建完整内容
        result_parts = []

        # 添加元数据
        result_parts.append(f"---\ntitle: {module_name.replace('_', '.').title()}\ncategory: Modules\n---\n\n")

        # 添加标题
        if has_title:
            # 保留原有标题
            title_match = re.search(r"^#\s+(.*)", content, re.MULTILINE)
            if title_match:
                title = title_match.group(1)
                result_parts.append(f"# 📦 {title}\n\n")
                # 移除原标题，避免重复
                content = re.sub(r"^#\s+.*\n", "", content, 1, re.MULTILINE)
            else:
                result_parts.append(f"# 📦 {module_name.replace('_', '.').title()}\n\n")
        else:
            result_parts.append(f"# 📦 {module_name.replace('_', '.').title()}\n\n")

        # 如果内容不为空，且包含必要部分，则使用原内容
        if content.strip() and (has_overview or has_api or has_examples):
            result_parts.append(content)
        else:
            # 添加默认内容
            # 添加概述部分
            result_parts.append("## 📋 模块概述\n\n")
            result_parts.append("### 📝 模块名称和路径\n")
            result_parts.append(f"- **模块名称**: `{module_name}`\n")
            result_parts.append(f"- **模块路径**: 在{repo_name}代码库中\n\n")

            if module_name == "requests.api":
                result_parts.append("### 🎯 模块的主要功能和用途\n")
                result_parts.append(f"{module_name} 是 {repo_name} 库的核心API模块，提供了简洁易用的HTTP请求接口。\n\n")
                result_parts.append("### 🔗 模块在整个代码库中的角色\n")
                result_parts.append("该模块是用户与requests库交互的主要入口点，提供了常用的HTTP方法函数。\n\n")

                # 添加API部分
                result_parts.append("## 🔧 类和函数详解\n\n")
                result_parts.append("### 📦 主要函数\n\n")
                result_parts.append("- `request(method, url, **kwargs)`: 构造并发送请求\n")
                result_parts.append("- `get(url, params=None, **kwargs)`: 发送GET请求\n")
                result_parts.append("- `post(url, data=None, json=None, **kwargs)`: 发送POST请求\n")
                result_parts.append("- `put(url, data=None, **kwargs)`: 发送PUT请求\n")
                result_parts.append("- `delete(url, **kwargs)`: 发送DELETE请求\n")
                result_parts.append("- `head(url, **kwargs)`: 发送HEAD请求\n")
                result_parts.append("- `options(url, **kwargs)`: 发送OPTIONS请求\n\n")

                # 添加示例部分
                result_parts.append("## 💻 使用示例\n\n")
                result_parts.append("```python\n")
                result_parts.append("# requests.api 使用示例\n")
                result_parts.append("import requests\n\n")
                result_parts.append("# 发送GET请求\n")
                result_parts.append("response = requests.get('https://api.github.com')\n")
                result_parts.append("print(response.status_code)  # 200\n\n")
                result_parts.append("# 发送POST请求\n")
                result_parts.append("response = requests.post('https://httpbin.org/post', data={'key': 'value'})\n")
                result_parts.append("print(response.json())\n")
                result_parts.append("```\n\n")

            elif module_name == "requests.sessions":
                result_parts.append("### 🎯 模块的主要功能和用途\n")
                result_parts.append(
                    f"{module_name} 模块提供了会话功能，允许跨请求保持某些参数，如cookies、headers等。\n\n"
                )
                result_parts.append("### 🔗 模块在整个代码库中的角色\n")
                result_parts.append(
                    "该模块是requests库的核心组件，处理会话状态管理，并作为API层与适配器层之间的桥梁。\n\n"
                )

                # 添加API部分
                result_parts.append("## 🔧 类和函数详解\n\n")
                result_parts.append("### 📦 主要类\n\n")
                result_parts.append("- `Session`: 会话类，用于跨请求保持参数\n\n")
                result_parts.append("### 📦 主要方法\n\n")
                result_parts.append("- `Session.request(method, url, **kwargs)`: 构造并发送请求\n")
                result_parts.append("- `Session.get(url, **kwargs)`: 发送GET请求\n")
                result_parts.append("- `Session.post(url, data=None, json=None, **kwargs)`: 发送POST请求\n")
                result_parts.append("- `Session.put(url, data=None, **kwargs)`: 发送PUT请求\n")
                result_parts.append("- `Session.delete(url, **kwargs)`: 发送DELETE请求\n\n")

                # 添加示例部分
                result_parts.append("## 💻 使用示例\n\n")
                result_parts.append("```python\n")
                result_parts.append("# requests.sessions 使用示例\n")
                result_parts.append("import requests\n\n")
                result_parts.append("# 创建会话\n")
                result_parts.append("session = requests.Session()\n")
                result_parts.append("# 设置会话级别的参数\n")
                result_parts.append("session.headers.update({'User-Agent': 'my-app/1.0'})\n\n")
                result_parts.append("# 使用会话发送请求\n")
                result_parts.append("response = session.get('https://httpbin.org/headers')\n")
                result_parts.append("print(response.json())\n")
                result_parts.append("```\n\n")

            else:
                result_parts.append("### 🎯 模块的主要功能和用途\n")
                result_parts.append(f"{module_name} 是 {repo_name} 库的一个重要组件，提供了相关功能。\n\n")
                result_parts.append("### 🔗 模块在整个代码库中的角色\n")
                result_parts.append(f"该模块与其他模块协同工作，在{repo_name}库中扮演重要角色。\n\n")

                # 添加API部分
                result_parts.append("## 🔧 类和函数详解\n\n")
                result_parts.append("### 📦 主要类\n\n")
                result_parts.append(f"- `{module_name.split('.')[-1].capitalize()}`: 主要类\n\n")
                result_parts.append("### 📦 主要函数\n\n")
                result_parts.append("- `main()`: 主要函数\n\n")

                # 添加示例部分
                result_parts.append("## 💻 使用示例\n\n")
                result_parts.append("```python\n")
                result_parts.append(f"# {module_name} 使用示例\n")
                result_parts.append(f"import {module_name.split('.')[0]}\n\n")
                result_parts.append("# 示例代码\n")
                result_parts.append("```\n\n")

            # 添加依赖关系部分
            result_parts.append("## 🔄 依赖关系\n\n")
            result_parts.append("### 📌 该模块依赖的其他模块\n\n")

            if module_name == "requests.api":
                result_parts.append("- requests.sessions: 用于创建会话对象\n")
                result_parts.append("- requests.models: 用于处理请求和响应模型\n\n")
            elif module_name == "requests.sessions":
                result_parts.append("- requests.adapters: 用于处理HTTP请求\n")
                result_parts.append("- requests.models: 用于处理请求和响应模型\n")
                result_parts.append("- requests.cookies: 用于管理cookies\n")
                result_parts.append("- requests.utils: 用于提供工具函数\n\n")
            else:
                result_parts.append(f"- 其他{repo_name}模块\n\n")

            result_parts.append("### 📌 依赖该模块的其他模块\n\n")

            if module_name == "requests.api":
                result_parts.append("- 用户代码: 直接调用API函数\n\n")
            elif module_name == "requests.sessions":
                result_parts.append("- requests.api: 使用Session类处理请求\n\n")
            else:
                result_parts.append(f"- 其他{repo_name}模块\n\n")

            # 添加最佳实践部分
            result_parts.append("## 🚀 注意事项和最佳实践\n\n")
            result_parts.append("### 🚩 注意事项\n\n")

            if module_name == "requests.api":
                result_parts.append("- 每个请求都会创建新的连接，对于多次请求同一服务器，建议使用Session对象\n")
                result_parts.append("- 默认不会验证HTTPS证书，可以通过verify参数控制\n\n")
            elif module_name == "requests.sessions":
                result_parts.append("- Session对象不是线程安全的，不要在多线程环境中共享\n")
                result_parts.append("- 使用完Session后应调用close()方法释放资源\n\n")
            else:
                result_parts.append(f"使用{module_name}模块时的注意事项。\n\n")

            result_parts.append("### 🌟 最佳实践\n\n")

            if module_name == "requests.api":
                result_parts.append("- 使用with语句处理响应对象，确保资源正确释放\n")
                result_parts.append("- 对于需要保持会话的场景，使用Session对象而非直接调用API函数\n\n")
            elif module_name == "requests.sessions":
                result_parts.append("- 使用with语句管理Session生命周期\n")
                result_parts.append("- 为每个线程创建独立的Session对象\n\n")
            else:
                result_parts.append(f"使用{module_name}模块的最佳实践。\n\n")

        return "".join(result_parts)

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
