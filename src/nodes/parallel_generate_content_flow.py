"""并行生成内容流程，使用AsyncParallelBatchNode模式实现并行协调各个内容生成节点。"""

import asyncio
from typing import Any, Dict, List, Optional

from pocketflow import AsyncFlow, AsyncNode

from ..utils.logger import log_and_notify
from .content_quality_check_node import ContentQualityCheckNode
from .generate_api_docs_node import GenerateApiDocsNode
from .generate_dependency_node import GenerateDependencyNode
from .generate_glossary_node import GenerateGlossaryNode
from .generate_module_details_node import GenerateModuleDetailsNode
from .generate_overall_architecture_node import GenerateOverallArchitectureNode
from .generate_quick_look_node import GenerateQuickLookNode
from .generate_timeline_node import GenerateTimelineNode
from .module_quality_check_node import ModuleQualityCheckNode


class ParallelDocGenerationNode(AsyncNode):
    """并行文档生成节点，实现手动并行"""

    def __init__(self, nodes_config: Dict[str, Dict[str, Any]]):
        """初始化并行文档生成节点

        Args:
            nodes_config: 节点配置字典，键为节点名称，值为节点配置
        """
        super().__init__()
        self.nodes = {}

        # 创建节点
        if "overall_architecture" in nodes_config:
            self.nodes["architecture"] = GenerateOverallArchitectureNode(nodes_config["overall_architecture"])

        if "api_docs" in nodes_config:
            self.nodes["api_docs"] = GenerateApiDocsNode(nodes_config["api_docs"])

        if "timeline" in nodes_config:
            self.nodes["timeline"] = GenerateTimelineNode(nodes_config["timeline"])

        if "dependency" in nodes_config:
            self.nodes["dependency"] = GenerateDependencyNode(nodes_config["dependency"])

        if "glossary" in nodes_config:
            self.nodes["glossary"] = GenerateGlossaryNode(nodes_config["glossary"])

        if "quick_look" in nodes_config:
            self.nodes["quick_look"] = GenerateQuickLookNode(nodes_config["quick_look"])

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
        node = task_desc["node"]
        task_shared = task_desc["shared"]
        log_and_notify(f"ParallelDocGenerationNode: 开始执行节点 {node_name}", "info")
        try:
            # 假设所有子节点都是同步的 Node，其 run 方法是阻塞的。
            # 为了在异步的 exec_async 中非阻塞地运行它们，使用 asyncio.to_thread。
            # 如果子节点本身是 AsyncNode 并有 run_async, 则可以直接 await node.run_async(task_shared)
            # 当前子节点 (GenerateOverallArchitectureNode等) 都是普通 Node。
            await asyncio.to_thread(node.run, task_shared)
            log_and_notify(f"ParallelDocGenerationNode: 节点 {node_name} 执行成功", "info")
            return {"node_name": node_name, "result": task_shared, "success": True}
        except Exception as e:
            error_msg = f"节点 {node_name} 执行出错: {str(e)}"
            log_and_notify(error_msg, "error")
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
        errors = []
        for result in exec_res_list:
            if not result.get("success", False):
                errors.append(result.get("error", f"节点 {result.get('node_name', '未知')} 执行失败"))

        if errors:
            error_msg = "; ".join(errors)
            log_and_notify(f"ParallelDocGenerationNode: 部分节点执行出错: {error_msg}", "error")
            shared["error"] = error_msg
            return "error"

        # 合并所有节点结果到共享存储
        for result in exec_res_list:
            node_name = result["node_name"]
            node_result = result["result"]

            # 根据节点名称，将结果存储到共享存储中
            if node_name == "architecture" and "architecture_doc" in node_result:
                shared["architecture_doc"] = node_result["architecture_doc"]
            elif node_name == "api_docs" and "api_docs" in node_result:
                shared["api_docs"] = node_result["api_docs"]
            elif node_name == "timeline" and "timeline_doc" in node_result:
                shared["timeline_doc"] = node_result["timeline_doc"]
            elif node_name == "dependency" and "dependency_doc" in node_result:
                shared["dependency_doc"] = node_result["dependency_doc"]
            elif node_name == "glossary" and "glossary_doc" in node_result:
                shared["glossary_doc"] = node_result["glossary_doc"]
            elif node_name == "quick_look" and "quick_look_doc" in node_result:
                shared["quick_look_doc"] = node_result["quick_look_doc"]

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
        self.module_details_node = GenerateModuleDetailsNode(module_details_config)
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
        self.parallel_doc_node - "error" >> None

        # 第三阶段：模块详细内容生成
        self.content_quality_node >> self.module_details_node
        self.content_quality_node - "error" >> None

        # 第四阶段：模块质量检查
        self.module_details_node >> self.module_quality_node
        self.module_details_node - "error" >> None

        # 最后一个节点 module_quality_node 如果出错，也应该能优雅停止
        self.module_quality_node - "error" >> None

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
