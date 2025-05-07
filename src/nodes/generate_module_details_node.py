"""生成模块详细文档节点，用于生成代码库中各模块的详细文档。"""

import json
import os
from typing import Any, Dict, List, Optional

from pocketflow import Node
from pydantic import BaseModel, Field

from ..utils.llm_wrapper.llm_client import LLMClient
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


class GenerateModuleDetailsNode(Node):
    """生成模块详细文档节点，用于生成代码库中各模块的详细文档"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化生成模块详细文档节点

        Args:
            config: 节点配置
        """
        super().__init__()

        # 从配置文件获取默认配置
        from ..utils.env_manager import get_node_config

        default_config = get_node_config("generate_module_details")

        # 合并配置
        merged_config = default_config.copy()
        if config:
            merged_config.update(config)

        self.config = GenerateModuleDetailsNodeConfig(**merged_config)
        log_and_notify("初始化生成模块详细文档节点", "info")

    def prep(self, shared: Dict[str, Any]) -> Dict[str, Any]:
        """准备阶段，从共享存储中获取核心模块和代码结构

        Args:
            shared: 共享存储

        Returns:
            包含核心模块和代码结构的字典
        """
        log_and_notify("GenerateModuleDetailsNode: 准备阶段开始", "info")

        # 从共享存储中获取核心模块
        core_modules = shared.get("core_modules")
        if not core_modules:
            error_msg = "共享存储中缺少核心模块"
            log_and_notify(error_msg, "error", notify=True)
            return {"error": error_msg}

        # 检查核心模块是否有效
        if not core_modules.get("success", False):
            error_msg = "核心模块无效"
            log_and_notify(error_msg, "error", notify=True)
            return {"error": error_msg}

        # 从共享存储中获取代码结构
        code_structure = shared.get("code_structure")
        if not code_structure:
            error_msg = "共享存储中缺少代码结构"
            log_and_notify(error_msg, "error", notify=True)
            return {"error": error_msg}

        # 检查代码结构是否有效
        if not code_structure.get("success", False):
            error_msg = "代码结构无效"
            log_and_notify(error_msg, "error", notify=True)
            return {"error": error_msg}

        # 从共享存储中获取 RAG 数据
        rag_data = shared.get("rag_data")
        if not rag_data:
            log_and_notify("共享存储中缺少 RAG 数据，将使用空数据", "warning")
            rag_data = {"files": [], "file_contents": {}, "chunks": [], "success": True}

        # 从共享存储中获取仓库路径
        repo_path = shared.get("repo_path")
        if not repo_path:
            error_msg = "共享存储中缺少仓库路径"
            log_and_notify(error_msg, "error", notify=True)
            return {"error": error_msg}

        # 获取 LLM 配置
        llm_config = shared.get("llm_config", {})

        # 获取目标语言
        target_language = shared.get("language", "zh")

        # 获取输出目录
        output_dir = shared.get("output_dir", "docs")

        return {
            "core_modules": core_modules,
            "code_structure": code_structure,
            "rag_data": rag_data,
            "repo_path": repo_path,
            "llm_config": llm_config,
            "target_language": target_language,
            "output_dir": output_dir,
            "retry_count": self.config.retry_count,
            "quality_threshold": self.config.quality_threshold,
            "model": self.config.model,
            "output_format": self.config.output_format,
            "max_modules_per_batch": self.config.max_modules_per_batch,
        }

    def exec(self, prep_res: Dict[str, Any]) -> Dict[str, Any]:
        """执行阶段，生成模块详细文档

        Args:
            prep_res: 准备阶段的结果

        Returns:
            生成结果
        """
        log_and_notify("GenerateModuleDetailsNode: 执行阶段开始", "info")

        # 检查准备阶段是否出错
        if "error" in prep_res:
            return {"error": prep_res["error"], "success": False}

        core_modules = prep_res["core_modules"]
        code_structure = prep_res["code_structure"]
        rag_data = prep_res["rag_data"]
        repo_path = prep_res["repo_path"]
        llm_config = prep_res["llm_config"]
        target_language = prep_res["target_language"]
        output_dir = prep_res["output_dir"]
        retry_count = prep_res["retry_count"]
        quality_threshold = prep_res["quality_threshold"]
        model = prep_res["model"]
        output_format = prep_res["output_format"]
        prep_res["max_modules_per_batch"]

        # 获取模块列表
        modules = core_modules.get("modules", [])
        if not modules:
            log_and_notify("没有找到核心模块", "warning")
            return {"modules": [], "success": True}

        # 创建模块文档目录
        modules_dir = os.path.join(output_dir, "modules")
        os.makedirs(modules_dir, exist_ok=True)
        log_and_notify(f"创建模块文档目录: {modules_dir}", "info")

        # 生成每个模块的详细文档
        module_docs = []

        for i, module in enumerate(modules):
            try:
                log_and_notify(
                    f"正在生成模块详细文档 ({i + 1}/{len(modules)}): {module.get('name', 'unknown')}", "info"
                )

                # 获取模块代码内容
                module_path = module.get("path", "")
                code_content = self._get_module_code(module_path, rag_data, code_structure, repo_path)

                # 准备提示
                prompt = self._create_prompt(module, code_content)

                # 尝试调用 LLM
                for attempt in range(retry_count):
                    try:
                        log_and_notify(f"尝试生成模块详细文档 (尝试 {attempt + 1}/{retry_count})", "info")

                        # 调用 LLM
                        content, quality_score, success = self._call_model(llm_config, prompt, target_language, model)

                        if success and quality_score["overall"] >= quality_threshold:
                            log_and_notify(f"成功生成模块详细文档 (质量分数: {quality_score['overall']})", "info")

                            # 保存文档
                            file_name = self._get_module_file_name(module)
                            file_path = os.path.join(modules_dir, file_name + "." + output_format)

                            with open(file_path, "w", encoding="utf-8") as f:
                                f.write(content)

                            log_and_notify(f"模块文档已保存到: {file_path}", "info")

                            module_docs.append(
                                {
                                    "name": module.get("name", ""),
                                    "path": module.get("path", ""),
                                    "file_path": file_path,
                                    "content": content,
                                    "quality_score": quality_score,
                                }
                            )

                            break
                        elif success:
                            log_and_notify(f"生成质量不佳 (分数: {quality_score['overall']}), 重试中...", "warning")
                    except Exception as e:
                        log_and_notify(f"LLM 调用失败: {str(e)}, 重试中...", "warning")
            except Exception as e:
                log_and_notify(f"生成模块 {module.get('name', 'unknown')} 的详细文档失败: {str(e)}", "error")

        # 生成模块索引文档
        index_content = self._generate_index(module_docs, target_language)
        index_path = os.path.join(output_dir, "modules.md")

        with open(index_path, "w", encoding="utf-8") as f:
            f.write(index_content)

        log_and_notify(f"模块索引文档已保存到: {index_path}", "info")

        log_and_notify(f"成功生成 {len(module_docs)} 个模块的详细文档", "info")

        return {"modules": module_docs, "index_path": index_path, "success": True}

    def post(self, shared: Dict[str, Any], prep_res: Dict[str, Any], exec_res: Dict[str, Any]) -> str:
        """后处理阶段，将生成结果存储到共享存储中

        Args:
            shared: 共享存储
            prep_res: 准备阶段的结果
            exec_res: 执行阶段的结果

        Returns:
            下一个节点的动作
        """
        log_and_notify("GenerateModuleDetailsNode: 后处理阶段开始", "info")

        # 检查执行阶段是否出错
        if not exec_res.get("success", False):
            error_msg = exec_res.get("error", "未知错误")
            log_and_notify(f"生成模块详细文档失败: {error_msg}", "error", notify=True)
            shared["module_details"] = {"error": error_msg, "success": False}
            return "error"

        # 将生成结果存储到共享存储中
        shared["module_details"] = {
            "modules": exec_res.get("modules", []),
            "index_path": exec_res.get("index_path", ""),
            "success": True,
        }

        log_and_notify(f"成功生成 {len(exec_res.get('modules', []))} 个模块的详细文档", "info", notify=True)

        return "default"

    def _get_module_code(
        self, module_path: str, rag_data: Dict[str, Any], code_structure: Dict[str, Any], repo_path: str
    ) -> str:
        """获取模块代码内容

        Args:
            module_path: 模块路径
            rag_data: RAG 数据
            code_structure: 代码结构
            repo_path: 仓库路径

        Returns:
            模块代码内容
        """
        # 尝试从 RAG 数据中获取
        file_contents = rag_data.get("file_contents", {})
        if module_path in file_contents:
            return file_contents[module_path]

        # 尝试从代码结构中获取
        files = code_structure.get("files", {})
        if module_path in files and "content" in files[module_path]:
            return files[module_path]["content"]

        # 尝试从文件系统中读取
        try:
            full_path = os.path.join(repo_path, module_path)
            if os.path.exists(full_path) and os.path.isfile(full_path):
                with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                    return f.read()
        except Exception as e:
            log_and_notify(f"读取模块代码失败: {str(e)}", "warning")

        # 如果是目录，尝试列出目录内容
        try:
            full_path = os.path.join(repo_path, module_path)
            if os.path.exists(full_path) and os.path.isdir(full_path):
                files = os.listdir(full_path)
                return f"目录 {module_path} 包含以下文件:\n" + "\n".join(files)
        except Exception as e:
            log_and_notify(f"列出目录内容失败: {str(e)}", "warning")

        return f"无法获取模块 {module_path} 的代码内容"

    def _create_prompt(self, module: Dict[str, Any], code_content: str) -> str:
        """创建提示

        Args:
            module: 模块信息
            code_content: 代码内容

        Returns:
            提示
        """
        # 格式化模块信息
        module_info = json.dumps(module, indent=2, ensure_ascii=False)

        # 格式化提示
        return self.config.module_details_prompt_template.format(module_info=module_info, code_content=code_content)

    def _call_model(self, llm_config: Dict[str, Any], prompt: str, target_language: str, model: str) -> tuple:
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
            system_prompt = f"""你是一个代码库文档专家，擅长分析代码并生成详细的模块文档。
请用{target_language}语言回答，但保持代码、变量名和技术术语的原始形式。
你的回答应该是格式良好的 Markdown，使用适当的标题、列表、表格和代码块。
使用表情符号使文档更加生动，例如在标题前使用适当的表情符号。
确保文档中的代码引用能够链接到源代码。"""

            # 调用 LLM
            messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}]

            response = llm_client.completion(
                messages=messages, temperature=0.3, model=model, trace_name="生成模块详细文档"
            , max_input_tokens=None)

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
        scores = {"completeness": 0.0, "structure": 0.0, "relevance": 0.0, "overall": 0.0}

        # 检查完整性
        required_sections = ["模块概述", "类和函数", "使用示例", "依赖关系", "注意事项"]

        found_sections = 0
        for section in required_sections:
            if section in content:
                found_sections += 1

        scores["completeness"] = found_sections / len(required_sections)

        # 检查结构
        has_headings = "# " in content
        has_lists = "- " in content or "* " in content
        has_code_blocks = "```" in content
        has_emojis = any(ord(c) > 0x1F000 for c in content)

        structure_score = 0.0
        if has_headings:
            structure_score += 0.4
        if has_lists:
            structure_score += 0.2
        if has_code_blocks:
            structure_score += 0.2
        if has_emojis:
            structure_score += 0.2

        scores["structure"] = structure_score

        # 检查相关性（简化处理，实际应该基于代码库内容评估）
        scores["relevance"] = 0.8  # 假设相关性较高

        # 计算总体分数
        scores["overall"] = (scores["completeness"] + scores["structure"] + scores["relevance"]) / 3

        return scores

    def _get_module_file_name(self, module: Dict[str, Any]) -> str:
        """获取模块文件名

        Args:
            module: 模块信息

        Returns:
            模块文件名
        """
        # 尝试使用模块名称
        name = module.get("name", "")
        if name:
            # 替换不允许的字符
            name = name.replace("/", "_").replace("\\", "_").replace(" ", "_").lower()
            return name

        # 如果没有名称，使用路径
        path = module.get("path", "unknown")
        # 移除扩展名
        path = os.path.splitext(path)[0]
        # 替换不允许的字符
        path = path.replace("/", "_").replace("\\", "_").replace(" ", "_").lower()

        return path

    def _generate_index(self, module_docs: List[Dict[str, Any]], target_language: str) -> str:
        """生成模块索引文档

        Args:
            module_docs: 模块文档列表
            target_language: 目标语言

        Returns:
            索引文档内容
        """
        # 确定标题
        title = "模块详细文档" if target_language == "zh" else "Module Details"

        # 生成索引内容
        content = f"# 📚 {title}\n\n"

        if not module_docs:
            content += "没有找到核心模块。\n" if target_language == "zh" else "No core modules found.\n"
            return content

        # 添加模块列表
        content += "## 模块列表\n\n" if target_language == "zh" else "## Module List\n\n"

        for doc in module_docs:
            name = doc.get("name", "")
            path = doc.get("path", "")
            file_path = doc.get("file_path", "")

            # 获取相对路径
            rel_path = os.path.relpath(file_path, os.path.dirname(os.path.dirname(file_path)))

            content += f"- [{name}]({rel_path}) - `{path}`\n"

        return content
