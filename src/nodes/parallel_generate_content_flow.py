"""并行生成内容流程，使用AsyncParallelBatchNode模式实现并行协调各个内容生成节点。"""

import asyncio
from typing import Any, Dict, List, Optional

from pocketflow import AsyncFlow, AsyncNode

from ..utils.logger import log_and_notify
from .content_quality_check_node import ContentQualityCheckNode
from .generate_api_docs_node import AsyncGenerateApiDocsNode
from .generate_dependency_node import AsyncGenerateDependencyNode
from .generate_glossary_node import AsyncGenerateGlossaryNode
from .generate_module_details_node import AsyncGenerateModuleDetailsNode
from .generate_overall_architecture_node import AsyncGenerateOverallArchitectureNode
from .generate_quick_look_node import AsyncGenerateQuickLookNode
from .generate_timeline_node import AsyncGenerateTimelineNode
from .module_quality_check_node import ModuleQualityCheckNode


class ParallelDocGenerationNode(AsyncNode):
    """并行文档生成节点，实现手动并行"""

    def __init__(self, nodes_config: Dict[str, Dict[str, Any]]):
        """初始化并行文档生成节点

        Args:
            nodes_config: 节点配置字典，键为节点名称，值为节点配置
        """
        super().__init__()
        self.nodes: Dict[str, AsyncNode] = {}

        # 创建节点
        if "overall_architecture" in nodes_config:
            self.nodes["architecture"] = AsyncGenerateOverallArchitectureNode(nodes_config["overall_architecture"])

        if "api_docs" in nodes_config:
            self.nodes["api_docs"] = AsyncGenerateApiDocsNode(nodes_config["api_docs"])

        if "timeline" in nodes_config:
            self.nodes["timeline"] = AsyncGenerateTimelineNode(nodes_config["timeline"])

        if "dependency" in nodes_config:
            self.nodes["dependency"] = AsyncGenerateDependencyNode(nodes_config["dependency"])

        if "glossary" in nodes_config:
            self.nodes["glossary"] = AsyncGenerateGlossaryNode(nodes_config["glossary"])

        if "quick_look" in nodes_config:
            self.nodes["quick_look"] = AsyncGenerateQuickLookNode(nodes_config["quick_look"])

    async def prep_async(self, shared: Dict[str, Any]) -> List[Dict[str, Any]]:
        """准备阶段，创建任务描述列表。这些任务将在exec_async中并行执行。

        Args:
            shared: 共享存储

        Returns:
            任务描述列表
        """
        tasks_description = []
        for node_name, node in self.nodes.items():
            tasks_description.append(
                {
                    "node_name": node_name,
                    "node": node,
                    "shared": shared.copy(),  # 为每个子任务创建共享存储的副本
                }
            )
        return tasks_description

    async def _run_single_node_async(self, task_desc: Dict[str, Any]) -> Dict[str, Any]:
        """异步运行单个子节点的辅助方法。"""
        node_name = task_desc["node_name"]
        node: AsyncNode = task_desc["node"]  # node is an AsyncNode
        task_shared = task_desc["shared"]
        log_and_notify(f"ParallelDocGenerationNode: 开始执行节点 {node_name}", "info")
        try:
            # Manually run the AsyncNode lifecycle
            prep_result = await node.prep_async(task_shared)
            # Ensure prep_result doesn't indicate immediate failure before exec
            if isinstance(prep_result, dict) and prep_result.get("error"):
                raise Exception(f"Prep stage failed for node {node_name}: {prep_result['error']}")

            exec_result = await node.exec_async(prep_result)
            # task_shared might be modified by exec if prep_result was task_shared and modified in place,
            # but primarily modifications happen in post_async based on exec_result.
            await node.post_async(
                task_shared, prep_result, exec_result
            )  # task_shared is modified in place by post_async

            log_and_notify(f"ParallelDocGenerationNode: 节点 {node_name} 执行成功", "info")
            # 'task_shared' now contains the results from the node's post_async
            return {"node_name": node_name, "result": task_shared, "success": True}
        except Exception as e:
            error_msg = f"节点 {node_name} 执行出错: {str(e)}"
            log_and_notify(error_msg, "error")
            task_shared["error"] = error_msg  # Ensure error is in the shared dict for this task
            return {"node_name": node_name, "result": task_shared, "error": error_msg, "success": False}

    async def exec_async(self, tasks_description: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """执行阶段，使用 asyncio.gather 并行运行所有任务。

        Args:
            tasks_description: 从 prep_async 返回的任务描述列表。

        Returns:
            所有任务的执行结果列表。
        """
        if not tasks_description:
            return []

        coroutines = [self._run_single_node_async(task_desc) for task_desc in tasks_description]
        results = await asyncio.gather(*coroutines)  # gather 默认 return_exceptions=False
        return results

    def _check_for_errors(self, exec_res_list: List[Dict[str, Any]]) -> List[str]:
        """检查执行结果中是否有错误

        Args:
            exec_res_list: 执行结果列表

        Returns:
            错误列表
        """
        errors = []
        for result in exec_res_list:
            if not result.get("success", False):
                errors.append(result.get("error", f"节点 {result.get('node_name', '未知')} 执行失败"))
        return errors

    def _merge_node_results(self, shared: Dict[str, Any], exec_res_list: List[Dict[str, Any]]) -> None:
        """合并节点结果到共享存储

        Args:
            shared: 共享存储
            exec_res_list: 执行结果列表
        """
        # 定义节点名称到共享存储键的映射
        node_to_shared_key = {
            "architecture": "architecture_doc",
            "api_docs": "api_docs",
            "timeline": "timeline_doc",
            "dependency": "dependency_doc",
            "glossary": "glossary_doc",
            "quick_look": "quick_look_doc",
        }

        for result in exec_res_list:
            node_name = result["node_name"]
            node_result = result["result"]

            # 如果节点名称在映射中，并且对应的键在节点结果中存在
            shared_key = node_to_shared_key.get(node_name)
            if shared_key and shared_key in node_result:
                shared[shared_key] = node_result[shared_key]

    async def post_async(
        self, shared: Dict[str, Any], prep_res: List[Dict[str, Any]], exec_res_list: List[Dict[str, Any]]
    ) -> str:
        """后处理阶段，合并所有节点结果

        Args:
            shared: 共享存储
            prep_res: 准备阶段返回的任务列表
            exec_res_list: 所有任务的执行结果列表

        Returns:
            后续动作
        """
        # 检查是否有节点执行出错
        errors = self._check_for_errors(exec_res_list)

        if errors:
            error_msg = "; ".join(errors)
            log_and_notify(f"ParallelDocGenerationNode: 部分节点执行出错: {error_msg}", "error")
            shared["error"] = error_msg
            return "error"

        # 合并所有节点结果到共享存储
        self._merge_node_results(shared, exec_res_list)

        return "default"


class ParallelGenerateContentFlow:
    """并行生成内容流程，使用AsyncParallelBatchNode模式实现"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化并行生成内容流程

        Args:
            config: 流程配置
        """
        # 从配置文件获取默认配置
        from ..utils.env_manager import get_node_config

        # 获取各节点配置
        nodes_config = {
            "overall_architecture": get_node_config("generate_overall_architecture"),
            "api_docs": get_node_config("generate_api_docs"),
            "timeline": get_node_config("generate_timeline"),
            "dependency": get_node_config("generate_dependency"),
            "glossary": get_node_config("generate_glossary"),
            "quick_look": get_node_config("generate_quick_look"),
        }

        content_quality_config = get_node_config("content_quality_check")
        module_details_config = get_node_config("generate_module_details")
        module_quality_config = get_node_config("module_quality_check")

        # 合并配置
        if config:
            for node_name in nodes_config:
                if node_name in config:
                    nodes_config[node_name].update(config[node_name])

            if "content_quality_check" in config:
                content_quality_config.update(config["content_quality_check"])
            if "generate_module_details" in config:
                module_details_config.update(config["generate_module_details"])
            if "module_quality_check" in config:
                module_quality_config.update(config["module_quality_check"])

        # 创建节点
        self.parallel_doc_node = ParallelDocGenerationNode(nodes_config)
        self.content_quality_node = ContentQualityCheckNode(content_quality_config)
        self.module_details_node = AsyncGenerateModuleDetailsNode(module_details_config)
        self.module_quality_node = ModuleQualityCheckNode(module_quality_config)

        # 创建流程
        self.flow = self._create_flow()

        log_and_notify("初始化并行生成内容流程", "info")

    def _create_flow(self) -> AsyncFlow:
        """创建流程

        Returns:
            流程
        """
        # 创建流程
        # 第一阶段：并行生成基础文档
        # 第二阶段：质量检查
        self.parallel_doc_node >> self.content_quality_node
        self.parallel_doc_node - "error" >> None  # type: ignore[operator]

        # 第三阶段：模块详细内容生成
        self.content_quality_node >> self.module_details_node
        self.content_quality_node - "error" >> None  # type: ignore[operator]

        # 第四阶段：模块质量检查
        self.module_details_node >> self.module_quality_node
        self.module_details_node - "error" >> None  # type: ignore[operator]

        # 最后一个节点 module_quality_node 如果出错，也应该能优雅停止
        self.module_quality_node - "error" >> None  # type: ignore[operator]

        # 创建流程，使用并行文档生成节点作为启动节点
        return AsyncFlow(start=self.parallel_doc_node)

    async def run_async(self, shared: Dict[str, Any]) -> Dict[str, Any]:
        """异步运行流程

        Args:
            shared: 共享存储

        Returns:
            流程结果
        """
        log_and_notify("开始运行并行生成内容流程", "info")

        # 检查共享存储中是否有必要的数据
        if "code_structure" not in shared:
            error_msg = "共享存储中缺少代码结构"
            log_and_notify(error_msg, "error", notify=True)
            return {"error": error_msg, "success": False}

        if "core_modules" not in shared:
            error_msg = "共享存储中缺少核心模块"
            log_and_notify(error_msg, "error", notify=True)
            return {"error": error_msg, "success": False}

        # 运行流程
        await self.flow.run_async(shared)

        # 检查流程是否成功
        if "error" in shared:
            return {"error": shared["error"], "success": False}

        # 收集结果
        result = {
            "architecture_doc": shared.get("architecture_doc", {}),
            "api_docs": shared.get("api_docs", {}),
            "timeline_doc": shared.get("timeline_doc", {}),
            "dependency_doc": shared.get("dependency_doc", {}),
            "glossary_doc": shared.get("glossary_doc", {}),
            "quick_look_doc": shared.get("quick_look_doc", {}),
            "module_details": shared.get("module_details", {}),
            "success": True,
        }

        log_and_notify("并行生成内容流程完成", "info", notify=True)

        return result

    def run(self, shared: Dict[str, Any]) -> Dict[str, Any]:
        """运行流程

        Args:
            shared: 共享存储

        Returns:
            流程结果
        """
        # 使用asyncio运行异步流程
        return asyncio.run(self.run_async(shared))
