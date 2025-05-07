"""异步并行流程，用于并行执行多个节点。"""

import asyncio
from typing import Any, Dict, List, Optional, Union

from pocketflow import AsyncFlow, AsyncNode, Flow, Node

from ..utils.logger import log_and_notify


class AsyncParallelFlow(AsyncNode):
    """异步并行流程，用于并行执行多个节点或流程"""

    def __init__(self, nodes: List[Union[Node, Flow, AsyncNode, AsyncFlow]]):
        """初始化异步并行流程

        Args:
            nodes: 要并行执行的节点或流程列表
        """
        super().__init__()
        self.nodes = nodes
        # 将普通节点包装为异步节点
        self.async_nodes = []
        for node in nodes:
            if isinstance(node, AsyncNode) or isinstance(node, AsyncFlow):
                self.async_nodes.append(node)
            else:
                # 将普通节点包装为异步节点
                self.async_nodes.append(self._wrap_sync_node(node))

    def _wrap_sync_node(self, node: Union[Node, Flow]) -> AsyncNode:
        """将同步节点包装为异步节点

        Args:
            node: 同步节点或流程

        Returns:
            包装后的异步节点
        """

        class SyncNodeWrapper(AsyncNode):
            def __init__(self, sync_node):
                super().__init__()
                self.sync_node = sync_node

            async def prep_async(self, shared):
                return shared

            async def exec_async(self, prep_res):
                # 在异步环境中执行同步节点
                if isinstance(self.sync_node, Flow):
                    # 如果是流程，执行整个流程
                    result_shared = prep_res.copy()
                    self.sync_node.run(result_shared)
                    return result_shared
                else:
                    # 如果是节点，执行节点的run方法
                    self.sync_node.run(prep_res)
                    return prep_res

            async def post_async(self, shared, prep_res, exec_res):
                # 合并执行结果到共享存储
                if isinstance(exec_res, dict):
                    shared.update(exec_res)
                return "default"

        return SyncNodeWrapper(node)

    async def prep_async(self, shared: Dict[str, Any]) -> Dict[str, Any]:
        """准备阶段，获取共享存储

        Args:
            shared: 共享存储

        Returns:
            准备结果
        """
        log_and_notify("AsyncParallelFlow: 准备阶段开始", "info")
        return shared

    async def exec_async(self, prep_res: Dict[str, Any]) -> List[Dict[str, Any]]:
        """执行阶段，并行执行所有节点

        Args:
            prep_res: 准备结果

        Returns:
            执行结果列表
        """
        log_and_notify(f"AsyncParallelFlow: 开始并行执行 {len(self.async_nodes)} 个节点", "info")

        # 创建每个节点的共享存储副本
        node_shared_list = [prep_res.copy() for _ in self.async_nodes]

        # 创建异步任务
        tasks = []
        for i, node in enumerate(self.async_nodes):
            if hasattr(node, "run_async"):
                # 如果是AsyncFlow，使用run_async方法
                tasks.append(node.run_async(node_shared_list[i]))
            else:
                # 如果是AsyncNode，手动执行prep_async->exec_async->post_async流程
                tasks.append(self._run_async_node(node, node_shared_list[i]))

        # 并行执行所有任务
        await asyncio.gather(*tasks)

        # 返回所有节点的共享存储
        return node_shared_list

    async def _run_async_node(self, node: AsyncNode, shared: Dict[str, Any]) -> None:
        """运行异步节点

        Args:
            node: 异步节点
            shared: 共享存储
        """
        try:
            # 执行prep_async
            prep_res = await node.prep_async(shared)

            # 执行exec_async
            exec_res = await node.exec_async(prep_res)

            # 执行post_async
            await node.post_async(shared, prep_res, exec_res)
        except Exception as e:
            log_and_notify(f"AsyncParallelFlow: 节点执行出错: {str(e)}", "error")
            shared["error"] = str(e)

    async def post_async(self, shared: Dict[str, Any], prep_res: Dict[str, Any], exec_res: List[Dict[str, Any]]) -> str:
        """后处理阶段，合并所有节点的结果

        Args:
            shared: 共享存储
            prep_res: 准备阶段的结果
            exec_res_list: 执行结果列表

        Returns:
            后续动作
        """
        log_and_notify("AsyncParallelFlow: 后处理阶段开始", "info")

        # 检查是否有节点执行出错
        errors = []
        for i, node_shared in enumerate(exec_res):
            if "error" in node_shared:
                errors.append(f"节点 {i} 执行出错: {node_shared['error']}")

        if errors:
            error_msg = "; ".join(errors)
            log_and_notify(f"AsyncParallelFlow: 部分节点执行出错: {error_msg}", "error")
            shared["error"] = error_msg
            return "error"

        # 合并所有节点的结果到共享存储
        # 注意：如果多个节点修改了相同的键，后面的节点会覆盖前面的节点的结果
        for node_shared in exec_res:
            # 只合并非共享存储原有的键，避免覆盖原始数据
            for key, value in node_shared.items():
                if key not in prep_res or prep_res[key] != value:
                    shared[key] = value

        log_and_notify("AsyncParallelFlow: 并行执行完成", "info")
        return "default"


class AsyncParallelBatchFlow(AsyncNode):
    """异步并行批处理流程，用于并行执行多个批处理任务"""

    def __init__(self, flow: Union[AsyncFlow, Flow], max_concurrency: Optional[int] = None):
        """初始化异步并行批处理流程

        Args:
            flow: 要并行执行的流程
            max_concurrency: 最大并发数，默认为None（不限制）
        """
        super().__init__()
        self.flow = flow
        self.max_concurrency = max_concurrency
        # 如果是同步流程，包装为异步流程
        if isinstance(flow, Flow):
            self.async_flow = self._wrap_sync_flow(flow)
        else:
            self.async_flow = flow

    def _wrap_sync_flow(self, flow: Flow) -> AsyncFlow:
        """将同步流程包装为异步流程

        Args:
            flow: 同步流程

        Returns:
            包装后的异步流程
        """

        # 创建一个包装节点
        class SyncFlowWrapper(AsyncNode):
            def __init__(self, sync_flow):
                super().__init__()
                self.sync_flow = sync_flow

            async def prep_async(self, shared):
                return shared

            async def exec_async(self, prep_res):
                # 在异步环境中执行同步流程
                result_shared = prep_res.copy()
                self.sync_flow.run(result_shared)
                return result_shared

            async def post_async(self, shared, prep_res, exec_res):
                # 合并执行结果到共享存储
                shared.update(exec_res)
                return "default"

        # 创建一个AsyncFlow，使用包装节点作为启动节点
        wrapper_node = SyncFlowWrapper(flow)
        return AsyncFlow(start=wrapper_node)

    async def prep_async(self, shared: Dict[str, Any]) -> List[Dict[str, Any]]:
        """准备阶段，获取批处理参数列表

        子类应该重写此方法，返回一个参数字典列表

        Args:
            shared: 共享存储

        Returns:
            参数字典列表
        """
        # 默认实现，子类应该重写此方法
        return [shared.copy()]

    async def exec_async(self, prep_res: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """执行阶段，并行执行流程

        Args:
            prep_res: 准备阶段返回的参数字典列表

        Returns:
            执行结果列表
        """
        log_and_notify(f"AsyncParallelBatchFlow: 开始并行执行 {len(prep_res)} 个批处理任务", "info")

        # 创建信号量控制并发数
        if self.max_concurrency:
            semaphore = asyncio.Semaphore(self.max_concurrency)
        else:
            # 创建一个永远可用的信号量
            semaphore = asyncio.Semaphore(len(prep_res))

        async def run_flow_with_params(params):
            async with semaphore:
                # 创建共享存储副本
                flow_shared = params.copy()
                # 运行流程
                await self.async_flow.run_async(flow_shared)
                return flow_shared

        # 创建所有任务
        tasks = [run_flow_with_params(params) for params in prep_res]

        # 并行执行所有任务
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理异常
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                log_and_notify(f"AsyncParallelBatchFlow: 任务 {i} 执行出错: {str(result)}", "error")
                # 创建一个包含错误信息的结果
                error_result = prep_res[i].copy()
                error_result["error"] = str(result)
                processed_results.append(error_result)
            else:
                processed_results.append(result)

        return processed_results

    async def post_async(
        self, shared: Dict[str, Any], prep_res: List[Dict[str, Any]], exec_res: List[Dict[str, Any]]
    ) -> str:
        """后处理阶段，处理执行结果

        Args:
            shared: 共享存储
            prep_res: 准备阶段的参数列表
            exec_res: 执行结果列表

        Returns:
            后续动作
        """
        log_and_notify("AsyncParallelBatchFlow: 后处理阶段开始", "info")

        # 检查是否有任务执行出错
        errors = []
        for i, result in enumerate(exec_res):
            if "error" in result:
                errors.append(f"任务 {i} 执行出错: {result['error']}")

        if errors:
            error_msg = "; ".join(errors)
            log_and_notify(f"AsyncParallelBatchFlow: 部分任务执行出错: {error_msg}", "error")
            shared["error"] = error_msg
            shared["batch_results"] = exec_res  # 保存所有结果，包括失败的
            return "error"

        # 将结果保存到共享存储
        shared["batch_results"] = exec_res

        log_and_notify("AsyncParallelBatchFlow: 并行批处理完成", "info")
        return "default"
