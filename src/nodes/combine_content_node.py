"""组合内容节点，用于组合生成的内容并进行一致性检查。"""

import hashlib
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from typing import Any, Dict, List, Optional

from pocketflow import Node
from pydantic import BaseModel, Field

from ..utils.llm_wrapper.llm_client import LLMClient
from ..utils.logger import log_and_notify


class CombineContentNodeConfig(BaseModel):
    """CombineContentNode 配置"""

    retry_count: int = Field(3, ge=1, le=10, description="重试次数")
    quality_threshold: float = Field(0.7, ge=0, le=1.0, description="质量阈值")
    model: str = Field("", description="LLM 模型，从配置中获取，不应设置默认值")
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


class CombineContentNode(Node):
    """组合内容节点，用于组合生成的内容并进行一致性检查"""

    # 缓存目录
    CACHE_DIR = ".cache/combine_content"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化组合内容节点

        Args:
            config: 节点配置
        """
        super().__init__()
        config_model = CombineContentNodeConfig(**(config or {}))
        self.config = config_model

        # 创建缓存目录
        os.makedirs(self.CACHE_DIR, exist_ok=True)

        log_and_notify("初始化组合内容节点", "info")

    @staticmethod
    @lru_cache(maxsize=128)
    def _get_cache_key(content: str, model: str) -> str:
        """生成缓存键

        Args:
            content: 内容
            model: 模型

        Returns:
            缓存键
        """
        # 使用内容和模型的哈希值作为缓存键
        content_hash = hashlib.md5(content.encode()).hexdigest()
        model_hash = hashlib.md5(model.encode()).hexdigest()
        return f"{content_hash}_{model_hash}"

    @lru_cache(maxsize=128)
    def _get_cache_path(self, cache_key: str) -> str:
        """获取缓存文件路径

        Args:
            cache_key: 缓存键

        Returns:
            缓存文件路径
        """
        return os.path.join(self.CACHE_DIR, f"{cache_key}.json")

    def _save_to_cache(self, cache_key: str, data: Any) -> None:
        """保存数据到缓存

        Args:
            cache_key: 缓存键
            data: 数据
        """
        try:
            cache_path = self._get_cache_path(cache_key)
            # 使用线程池执行 I/O 操作，避免阻塞主线程
            with ThreadPoolExecutor(max_workers=1) as executor:
                executor.submit(self._write_to_file, cache_path, data)
            log_and_notify(f"已保存到缓存: {cache_path}", "debug")
        except Exception as e:
            log_and_notify(f"保存缓存失败: {str(e)}", "warning")

    def _write_to_file(self, file_path: str, data: Any) -> None:
        """写入数据到文件

        Args:
            file_path: 文件路径
            data: 数据
        """
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load_from_cache(self, cache_key: str) -> Optional[Any]:
        """从缓存加载数据

        Args:
            cache_key: 缓存键

        Returns:
            缓存的数据，如果缓存不存在则返回 None
        """
        try:
            cache_path = self._get_cache_path(cache_key)
            if os.path.exists(cache_path):
                # 使用线程池执行 I/O 操作，避免阻塞主线程
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(self._read_from_file, cache_path)
                    data = future.result()
                log_and_notify(f"已从缓存加载: {cache_path}", "debug")
                return data
        except Exception as e:
            log_and_notify(f"加载缓存失败: {str(e)}", "warning")
        return None

    def _read_from_file(self, file_path: str) -> Any:
        """从文件读取数据

        Args:
            file_path: 文件路径

        Returns:
            文件中的数据
        """
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def prep(self, shared: Dict[str, Any]) -> Dict[str, Any]:
        """准备阶段，收集所有生成的内容

        Args:
            shared: 共享存储

        Returns:
            准备结果
        """
        # 添加性能监控 - 记录开始时间
        start_time = time.time()

        log_and_notify("开始组合内容", "info")

        # 收集所有生成的内容 - 定义要收集的内容键
        content_keys = [
            "architecture_doc",
            "api_docs",
            "timeline_doc",
            "dependency_doc",
            "glossary_doc",
            "quick_look_doc",
            "module_details",
        ]

        # 使用字典推导式优化内容收集
        content_dict = {}
        content_sizes = {}

        # 收集内容并记录大小
        for key in content_keys:
            if key in shared and shared[key].get("success", False):
                if key == "module_details":
                    # 处理模块详细文档
                    module_docs = shared[key].get("docs", [])
                    if module_docs:
                        # 使用列表推导式优化模块内容收集
                        modules_content = [
                            module_doc["content"] for module_doc in module_docs if "content" in module_doc
                        ]

                        if modules_content:
                            content_dict["modules"] = module_docs
                            combined_modules = "\n\n---\n\n".join(modules_content)
                            content_dict[key] = combined_modules
                            content_sizes[key] = len(combined_modules)
                else:
                    content = shared[key].get("content", "")
                    content_dict[key] = content
                    content_sizes[key] = len(content)

        # 记录收集到的内容数量和大小
        if content_dict:
            total_size = sum(content_sizes.values())
            log_and_notify(f"收集到 {len(content_dict)} 个内容，总大小: {total_size / 1024:.2f}KB", "info")

            # 记录每个内容的大小
            for key, size in content_sizes.items():
                log_and_notify(f"- {key}: {size / 1024:.2f}KB", "debug")
        else:
            error_msg = "没有找到生成的内容"
            log_and_notify(error_msg, "error", notify=True)

            # 记录结束时间和耗时（即使出错）
            end_time = time.time()
            log_and_notify(f"准备阶段耗时(失败): {end_time - start_time:.2f}秒", "info")

            return {"error": error_msg}

        # 获取配置信息 - 使用更简洁的方式
        config_info = {
            "llm_config": shared.get("llm_config", {}),
            "target_language": shared.get("language", "zh"),
            "output_dir": shared.get("output_dir", "docs_output"),
            "repo_url": shared.get("repo_url", ""),
            "repo_branch": shared.get("branch", "main"),
            "repo_name": shared.get("repo_name", "docs"),
            "core_modules": shared.get("core_modules", {}),
        }

        # 记录结束时间和耗时
        end_time = time.time()
        prep_time = end_time - start_time
        log_and_notify(f"准备阶段耗时: {prep_time:.2f}秒", "info")

        # 返回结果 - 合并配置信息和内容字典
        return {
            "content_dict": content_dict,
            **config_info,
            "retry_count": self.config.retry_count,
            "quality_threshold": self.config.quality_threshold,
            "model": self.config.model,
            "prep_time": prep_time,
            "content_sizes": content_sizes,
        }

    def exec(self, prep_res: Dict[str, Any]) -> Dict[str, Any]:
        """执行阶段，组合内容并进行一致性检查

        Args:
            prep_res: 准备阶段的结果

        Returns:
            执行结果
        """
        # 添加性能监控 - 记录开始时间
        start_time = time.time()

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
        repo_name = prep_res.get("repo_name", "docs")
        core_modules = prep_res["core_modules"]
        model = prep_res["model"]

        try:
            # 组合内容
            log_and_notify("开始组合内容", "info")
            combined_content = self._combine_content(content_dict)

            # 检查是否需要进行一致性检查
            should_check_consistency = True

            # 如果没有有效的 LLM 配置或模型，跳过一致性检查
            if not llm_config or not model:
                log_and_notify("缺少 LLM 配置或模型，跳过一致性检查", "warning")
                should_check_consistency = False

            # 如果内容太短，跳过一致性检查
            if len(combined_content) < 1000:
                log_and_notify("内容太短，跳过一致性检查", "info")
                should_check_consistency = False

            # 检查一致性
            consistency_issues = []
            if should_check_consistency:
                log_and_notify("开始检查内容一致性", "info")
                consistency_issues = self._check_consistency(combined_content, llm_config, model)

            # 如果有一致性问题，修复内容
            if consistency_issues:
                log_and_notify(f"发现 {len(consistency_issues)} 个一致性问题，开始修复", "info")
                combined_content = self._fix_consistency_issues(combined_content, consistency_issues)
            else:
                log_and_notify("未发现一致性问题，跳过修复", "info")

            # 创建文件结构
            file_structure = self._create_file_structure(repo_name)

            # 创建仓库结构
            repo_structure = self._create_repo_structure(core_modules, repo_name)

            # 记录结束时间和耗时
            end_time = time.time()
            total_time = end_time - start_time
            log_and_notify(f"组合内容节点执行总耗时: {total_time:.2f}秒", "info")

            return {
                "combined_content": combined_content,
                "file_structure": file_structure,
                "repo_structure": repo_structure,
                "output_dir": output_dir,
                "repo_url": repo_url,
                "repo_branch": repo_branch,
                "repo_name": repo_name,
                "target_language": target_language,
                "success": True,
                "performance_metrics": {
                    "total_time": total_time,
                    "content_size": len(combined_content),
                    "consistency_issues_count": len(consistency_issues),
                },
            }
        except Exception as e:
            error_msg = f"组合内容失败: {str(e)}"
            log_and_notify(error_msg, "error", notify=True)

            # 记录结束时间和耗时（即使出错）
            end_time = time.time()
            log_and_notify(f"组合内容节点执行总耗时(失败): {end_time - start_time:.2f}秒", "info")

            return {"success": False, "error": error_msg}

    def post(self, shared: Dict[str, Any], _: Dict[str, Any], exec_res: Dict[str, Any]) -> str:
        """后处理阶段，更新共享存储

        Args:
            shared: 共享存储
            _: 准备阶段的结果（未使用）
            exec_res: 执行结果

        Returns:
            下一个节点的名称
        """
        # 添加性能监控 - 记录开始时间
        start_time = time.time()

        if exec_res.get("success", False):
            # 更新共享存储
            shared["combined_content"] = exec_res["combined_content"]
            shared["file_structure"] = exec_res["file_structure"]
            shared["repo_structure"] = exec_res["repo_structure"]

            # 添加性能指标
            if "performance_metrics" in exec_res:
                shared["combine_content_metrics"] = exec_res["performance_metrics"]

                # 记录性能指标
                metrics = exec_res["performance_metrics"]
                log_and_notify(
                    f"性能指标: 总耗时={metrics.get('total_time', 0):.2f}秒, "
                    f"内容大小={metrics.get('content_size', 0) / 1024:.2f}KB, "
                    f"一致性问题数={metrics.get('consistency_issues_count', 0)}",
                    "info",
                )

            log_and_notify("组合内容完成", "info", notify=True)

            # 记录结束时间和耗时
            end_time = time.time()
            log_and_notify(f"后处理阶段耗时: {end_time - start_time:.2f}秒", "info")

            return "default"
        elif "error" in exec_res:
            shared["error"] = exec_res["error"]
            log_and_notify(f"组合内容失败: {exec_res['error']}", "error", notify=True)

            # 记录结束时间和耗时（即使出错）
            end_time = time.time()
            log_and_notify(f"后处理阶段耗时(失败): {end_time - start_time:.2f}秒", "info")

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
        # 定义文档顺序和标题
        doc_order = [
            ("architecture_doc", "# 系统架构"),
            ("api_docs", "# API 文档"),
            ("timeline_doc", "# 演变历史"),
            ("dependency_doc", "# 依赖关系"),
            ("glossary_doc", "# 术语表"),
            ("quick_look_doc", "# 快速浏览"),
            ("module_details", "# 模块详情"),
        ]

        # 添加性能监控 - 记录开始时间
        start_time = time.time()

        # 创建组合内容 - 使用列表推导式提高效率
        combined_parts = [
            f"{title}\n\n{content_dict[key]}" for key, title in doc_order if key in content_dict and content_dict[key]
        ]

        # 组合内容 - 使用分隔符
        combined_content = "\n\n---\n\n".join(combined_parts)

        # 记录结束时间和耗时
        end_time = time.time()
        log_and_notify(f"内容组合耗时: {end_time - start_time:.2f}秒", "info")

        return combined_content

    def _check_consistency(self, content: str, llm_config: Dict[str, Any], model: str) -> List[Dict[str, Any]]:
        """检查内容一致性

        Args:
            content: 内容
            llm_config: LLM 配置
            model: 模型

        Returns:
            一致性问题列表
        """
        # 生成缓存键
        cache_key = self._get_cache_key(content[:10000], model)  # 只使用前 10000 个字符生成缓存键

        # 尝试从缓存加载
        cached_result = self._load_from_cache(cache_key)
        if cached_result is not None:
            log_and_notify("使用缓存的一致性检查结果", "info")
            return cached_result

        try:
            # 创建 LLM 客户端
            llm_client = LLMClient(llm_config)

            # 准备系统提示 - 简化系统提示，减少 token 使用量
            system_prompt = "你是一个技术文档质量检查专家。检查文档一致性问题并以JSON格式返回结果。"

            # 准备用户提示 - 使用配置中的提示模板
            # 限制内容长度，只检查前 10000 个字符，减少 token 使用量
            content_sample = content[:10000] + ("..." if len(content) > 10000 else "")
            user_prompt = self.config.consistency_check_prompt_template.format(content=content_sample)

            # 调用 LLM - 使用较低的温度值以获得更一致的结果
            messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]

            # 添加性能监控 - 记录开始时间
            start_time = time.time()

            response = llm_client.completion(
                messages=messages,
                temperature=0.2,  # 降低温度值，提高一致性
                model=model,
                trace_name="检查内容一致性",
                max_input_tokens=4000,  # 限制输入 token 数量
            )

            # 记录结束时间和耗时
            end_time = time.time()
            log_and_notify(f"一致性检查耗时: {end_time - start_time:.2f}秒", "info")

            # 获取响应内容
            response_content = llm_client.get_completion_content(response)

            # 解析 JSON 响应 - 简化解析逻辑
            try:
                # 提取 JSON 部分 - 使用更健壮的正则表达式
                json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", response_content)
                if json_match:
                    json_str = json_match.group(1).strip()
                else:
                    # 尝试直接解析整个响应
                    json_str = response_content.strip()

                # 解析 JSON - 添加错误处理
                try:
                    issues = json.loads(json_str)
                except json.JSONDecodeError:
                    # 如果解析失败，尝试修复常见的 JSON 格式问题
                    fixed_json_str = re.sub(r"'([^']*)':", r'"\1":', json_str)  # 将单引号替换为双引号
                    issues = json.loads(fixed_json_str)

                # 确保返回的是列表
                result = []
                if isinstance(issues, dict) and "issues" in issues:
                    result = issues["issues"]
                elif isinstance(issues, list):
                    result = issues
                else:
                    log_and_notify("一致性检查返回的结果格式不正确", "warning")

                # 保存结果到缓存
                self._save_to_cache(cache_key, result)

                return result
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
        if not issues:
            return content

        # 添加性能监控 - 记录开始时间
        start_time = time.time()

        # 创建修复日志
        fix_log = []
        fixed_content = content

        # 按位置排序问题，从后向前修复，避免位置偏移
        sorted_issues = sorted(
            [issue for issue in issues if "suggestion" in issue and "location" in issue],
            key=lambda x: x.get("location", ""),
            reverse=True,
        )

        # 应用修复
        for issue in sorted_issues:
            description = issue.get("description", "未知问题")
            location = issue.get("location", "")
            suggestion = issue.get("suggestion", "")

            # 记录修复信息
            fix_log.append(f"- 修复问题: {description}")
            fix_log.append(f"  位置: {location}")
            fix_log.append(f"  建议: {suggestion}")

            # 尝试应用修复
            try:
                # 这里使用简单的字符串替换，实际应用中可能需要更复杂的逻辑
                # 例如，使用正则表达式或其他方法定位和替换问题内容
                if location and suggestion and location in fixed_content:
                    # 使用上下文来确保替换正确的内容
                    context_before = (
                        fixed_content.split(location)[0][-50:]
                        if len(fixed_content.split(location)[0]) > 50
                        else fixed_content.split(location)[0]
                    )
                    context_after = (
                        fixed_content.split(location)[1][:50]
                        if len(fixed_content.split(location)[1]) > 50
                        else fixed_content.split(location)[1]
                    )

                    # 构建替换模式
                    pattern = re.escape(context_before + location + context_after)
                    replacement = context_before + suggestion + context_after

                    # 执行替换
                    fixed_content = re.sub(pattern, replacement, fixed_content)
                    fix_log.append("  状态: 已修复")
                else:
                    fix_log.append("  状态: 无法定位问题位置")
            except Exception as e:
                fix_log.append(f"  状态: 修复失败 - {str(e)}")

        # 记录修复日志
        if fix_log:
            log_and_notify("一致性问题修复日志:\n" + "\n".join(fix_log), "info")

        # 记录结束时间和耗时
        end_time = time.time()
        log_and_notify(f"一致性问题修复耗时: {end_time - start_time:.2f}秒", "info")

        return fixed_content

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
            f"{repo_name}/index.md": {
                "title": f"{repo_name.capitalize()} 文档首页",
                "sections": ["introduction", "quick_look", "navigation"],
            },
            f"{repo_name}/overview.md": {
                "title": "系统架构",
                "sections": ["overall_architecture", "architecture", "core_modules_summary"],
            },
            f"{repo_name}/glossary.md": {"title": "术语表", "sections": ["glossary"]},
            f"{repo_name}/evolution.md": {"title": "演变历史", "sections": ["evolution_narrative"]},
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
        repo_structure = {"repo_name": repo_name}

        # 添加核心模块
        for module_name, module_info in core_modules.items():
            if isinstance(module_info, dict) and "path" in module_info:
                repo_structure[module_name] = str(
                    {"path": module_info["path"], "type": module_info.get("type", "module")}
                )

        return repo_structure
