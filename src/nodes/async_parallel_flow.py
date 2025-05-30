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
            def __init__(self, sync_node: Union[Node, Flow]):
                super().__init__()
                self.sync_node = sync_node

            async def prep_async(self, shared: Dict[str, Any]) -> Dict[str, Any]:
                return shared

            async def exec_async(self, prep_res: Dict[str, Any]) -> Dict[str, Any]:
                # 在异步环境中执行同步节点
                if isinstance(self.sync_node, Flow):
                    # 如果是流程，执行整个流程
                    result_shared = prep_res.copy()
                    self.sync_node.run(result_shared)
                    return result_shared
                else:
                    # 如果是节点，执行节点的run方法
                    # Node.run can return Optional[str], but here we are interested in side effects on prep_res
                    # and returning the (potentially modified) prep_res.
                    self.sync_node.run(prep_res)  # Assuming prep_res is modified in place or result is not used
                    return prep_res

            async def post_async(
                self, shared: Dict[str, Any], prep_res: Dict[str, Any], exec_res: Dict[str, Any]
            ) -> str:
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
        if shared.get("error"):
            error_msg = f"AsyncParallelFlow: Error already in shared state: {shared['error']}. Aborting prep."
            log_and_notify(error_msg, "warning")
            return {"error": error_msg, "_async_parallel_flow_prep_failed": True}
        return shared

    async def exec_async(self, prep_res: Dict[str, Any]) -> List[Dict[str, Any]]:
        """执行阶段，并行执行所有节点

        Args:
            prep_res: 准备结果

        Returns:
            执行结果列表
        """
        if prep_res.get("_async_parallel_flow_prep_failed"):
            error_msg = prep_res.get("error", "AsyncParallelFlow: prep_async indicated failure.")
            log_and_notify(f"AsyncParallelFlow: exec_async skipped due to error from prep_async: {error_msg}", "error")
            # Return a list of dicts, each indicating the error, to match post_async's expected exec_res format.
            # This helps post_async correctly set shared['error'] for the entire stage.
            # If there are no nodes (e.g. self.async_nodes is empty), return a single error dict.
            return [{"error": error_msg} for _ in self.async_nodes] if self.async_nodes else [{"error": error_msg}]

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
            exec_res: 所有并行节点执行结果的列表

        Returns:
            下一个节点的动作 ("default" 或 "error")
        """
        log_and_notify("AsyncParallelFlow: 后处理阶段开始", "info")

        # 检查是否有节点执行出错
        errors = []
        # If exec_res itself is a single dict with an error (from prep failure propagation), handle it.
        # However, current exec_async modification ensures exec_res is a list of error dicts.
        for i, node_shared_result in enumerate(exec_res):
            if isinstance(node_shared_result, dict) and "error" in node_shared_result:
                node_identifier = f"节点 {self.nodes[i].__class__.__name__ if i < len(self.nodes) else i}"
                errors.append(f"{node_identifier} 执行出错: {node_shared_result['error']}")

        if errors:
            error_msg = "; ".join(errors)
            log_and_notify(f"AsyncParallelFlow: 部分或全部并行节点执行出错: {error_msg}", "error")
            # Append to existing shared error if any, to avoid overwriting upstream errors
            existing_error = shared.get("error")
            if existing_error:
                shared["error"] = f"{existing_error}; AsyncParallelFlow errors: {error_msg}"
            else:
                shared["error"] = f"AsyncParallelFlow errors: {error_msg}"
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
            def __init__(self, sync_flow: Flow):
                super().__init__()
                self.sync_flow = sync_flow

            async def prep_async(self, shared: Dict[str, Any]) -> Dict[str, Any]:
                return shared

            async def exec_async(self, prep_res: Dict[str, Any]) -> Dict[str, Any]:
                # 在异步环境中执行同步流程
                result_shared = prep_res.copy()
                self.sync_flow.run(result_shared)
                return result_shared

            async def post_async(
                self, shared: Dict[str, Any], prep_res: Dict[str, Any], exec_res: Dict[str, Any]
            ) -> str:
                # 合并执行结果到共享存储
                if isinstance(exec_res, dict):
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

    async def exec_async(self, prep_res: List[Dict[str, Any]]) -> List[Union[Dict[str, Any], BaseException]]:
        """执行阶段，并行执行所有批处理任务

        Args:
            prep_res: 批处理参数列表

        Returns:
            执行结果列表，包含成功的结果或异常对象
        """
        if not prep_res:
            log_and_notify("AsyncParallelBatchFlow: 没有批处理任务可执行", "info")
            return []

        log_and_notify(f"AsyncParallelBatchFlow: 开始并行执行 {len(prep_res)} 个批处理任务", "info")

        # 创建信号量控制并发数
        if self.max_concurrency:
            semaphore = asyncio.Semaphore(self.max_concurrency)
        else:
            semaphore_value = len(prep_res) if prep_res else 1
            semaphore = asyncio.Semaphore(semaphore_value)

        async def run_flow_with_params(params: Dict[str, Any]) -> Dict[str, Any]:
            async with semaphore:
                flow_shared = params.copy()
                try:
                    await self.async_flow.run_async(flow_shared)  # Assuming run_async returns the modified shared
                    return flow_shared
                except Exception as e:
                    log_and_notify(f"AsyncParallelBatchFlow: 子流程执行出错: {e} with params {params}", "error")
                    # Return a dict with error, or re-raise to be caught by gather
                    # For simplicity with gather(return_exceptions=True), we can let it be caught
                    raise  # This will make asyncio.gather return the exception object

        tasks = [run_flow_with_params(params) for params in prep_res]

        # Store results or exceptions
        results_with_errors: List[Union[Dict[str, Any], BaseException]] = []  # Modified type

        # 并行执行所有任务，并收集结果或异常
        # return_exceptions=True 会让gather在任务抛出异常时不打断其他任务，而是将异常作为结果返回
        gathered_results = await asyncio.gather(*tasks, return_exceptions=True)

        for result_or_error in gathered_results:
            if isinstance(result_or_error, BaseException):
                log_and_notify(f"AsyncParallelBatchFlow: 批处理任务执行出错: {result_or_error}", "error")
                results_with_errors.append(result_or_error)
            elif isinstance(result_or_error, dict):
                results_with_errors.append(result_or_error)
            else:
                # This case should ideally not happen if run_flow_with_params always returns a dict or raises
                log_and_notify(f"AsyncParallelBatchFlow: 批处理任务返回了意外类型: {type(result_or_error)}", "error")
                # Append an error dict to maintain structure for post_async if it expects dicts or exceptions
                results_with_errors.append(
                    {"error": "Unexpected result type from batch task", "type": str(type(result_or_error))}
                )

        return results_with_errors

    async def post_async(
        self,
        shared: Dict[str, Any],
        prep_res: List[Dict[str, Any]],
        exec_res: List[Union[Dict[str, Any], BaseException]],  # Modified exec_res type
    ) -> str:
        """后处理阶段，合并所有批处理任务的结果

        Args:
            shared: 共享存储
            prep_res: 准备阶段的结果
            exec_res: 所有批处理任务执行结果（或异常）的列表

        Returns:
            下一个节点的动作 ("default" 或 "error")
        """
        log_and_notify("AsyncParallelBatchFlow: 后处理阶段开始", "info")

        # 检查是否有任务执行出错
        errors = []
        for i, result in enumerate(exec_res):
            if isinstance(result, BaseException):
                errors.append(f"任务 {i} 执行出错: {result}")

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
