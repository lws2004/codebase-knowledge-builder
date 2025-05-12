"""异步并行批处理节点，用于并行处理多个项目。"""

from typing import Any, Dict, List, Optional

from pocketflow import AsyncNode

from ..utils.logger import log_and_notify
from .async_parallel_flow import AsyncParallelBatchFlow


class AsyncParallelBatchNode(AsyncNode):
    """异步并行批处理节点，用于并行处理多个项目"""

    def __init__(self, max_concurrency: Optional[int] = None):
        """初始化异步并行批处理节点

        Args:
            max_concurrency: 最大并发数，默认为None（不限制）
        """
        super().__init__()
        self.max_concurrency = max_concurrency

    async def prep_async(self, shared: Dict[str, Any]) -> List[Any]:
        """准备阶段，获取要处理的项目列表

        子类应该重写此方法，返回一个项目列表

        Args:
            shared: 共享存储

        Returns:
            项目列表
        """
        # 默认实现，子类应该重写此方法
        return []

    async def exec_async(self, prep_res: Any) -> Any:
        """执行阶段，处理单个项目

        子类必须重写此方法，实现对单个项目的处理逻辑

        Args:
            prep_res: 准备阶段返回的项目

        Returns:
            处理结果
        """
        # 默认实现，子类必须重写此方法
        raise NotImplementedError("子类必须实现exec_async方法")

    async def exec_fallback_async(self, item: Any, error: Exception) -> Any:
        """执行失败时的回退处理

        当exec_async抛出异常时调用此方法

        Args:
            item: 要处理的项目
            error: 执行过程中抛出的异常

        Returns:
            回退处理结果
        """
        # 默认实现，记录错误并返回None
        log_and_notify(f"AsyncParallelBatchNode: 项目处理失败，错误: {str(error)}", "error")
        return None

    async def post_async(self, shared: Dict[str, Any], prep_res: List[Any], exec_res: List[Any]) -> str:
        """后处理阶段，处理所有项目的结果

        Args:
            shared: 共享存储
            prep_res: 准备阶段返回的项目列表
            exec_res: 执行阶段返回的结果列表

        Returns:
            后续动作
        """
        # 默认实现，将结果保存到共享存储
        shared["batch_results"] = exec_res
        return "default"

    class ItemProcessor(AsyncNode):
        """处理单个项目的内部异步节点类"""

        def __init__(self, parent_node: "AsyncParallelBatchNode"):
            """初始化项目处理器

            Args:
                parent_node: 父节点实例，用于调用其exec_async和exec_fallback_async方法
            """
            super().__init__()
            self.parent_node = parent_node

        async def prep_async(self, shared: Dict[str, Any]) -> Dict[str, Any]:
            """准备阶段，从 shared 中获取项目

            Args:
                shared: 共享存储

            Returns:
                准备结果
            """
            return shared

        async def exec_async(self, prep_res: Dict[str, Any]) -> Dict[str, Any]:
            """执行阶段，处理单个项目

            Args:
                prep_res: 准备结果

            Returns:
                执行结果
            """
            item = prep_res.get("_item")
            try:
                result = await self.parent_node.exec_async(item)
                return {"_result": result, "_success": True}
            except Exception as e:
                log_and_notify(f"AsyncParallelBatchNode: 处理项目时出错: {str(e)}", "error")
                try:
                    fallback_result = await self.parent_node.exec_fallback_async(item, e)
                    return {"_result": fallback_result, "_success": False, "_error": str(e)}
                except Exception as fallback_error:
                    log_and_notify(f"AsyncParallelBatchNode: 回退处理项目时出错: {str(fallback_error)}", "error")
                    return {
                        "_result": None,
                        "_success": False,
                        "_error": str(e),
                        "_fallback_error": str(fallback_error),
                    }

        async def post_async(self, shared: Dict[str, Any], prep_res: Dict[str, Any], exec_res: Dict[str, Any]) -> str:
            """后处理阶段

            Args:
                shared: 共享存储
                prep_res: 准备结果
                exec_res: 执行结果

            Returns:
                后续动作
            """
            return "default"

    def _process_batch_results(self, batch_results: List[Any]) -> List[Any]:
        """处理批处理结果

        Args:
            batch_results: 批处理结果列表

        Returns:
            处理后的结果列表
        """
        result_list = []
        for result in batch_results:
            if isinstance(result, dict) and "_result" in result:
                result_list.append(result["_result"])
            elif isinstance(result, BaseException):
                # 如果是异常，添加 None
                log_and_notify(f"AsyncParallelBatchNode: 批处理任务抛出异常: {result}", "error")
                result_list.append(None)
            else:
                # 其他情况，添加 None
                log_and_notify(f"AsyncParallelBatchNode: 批处理任务返回了意外结果: {result}", "error")
                result_list.append(None)
        return result_list

    async def run_async(self, shared: Dict[str, Any]) -> str:
        """运行节点

        使用 Pocket Flow 的 AsyncParallelBatchFlow 实现并发批处理

        Args:
            shared: 共享存储

        Returns:
            后续动作
        """
        # 准备阶段
        item_list = await self.prep_async(shared)

        if not item_list:
            log_and_notify("AsyncParallelBatchNode: 没有要处理的项目", "warning")
            return await self.post_async(shared, [], [])

        log_and_notify(f"AsyncParallelBatchNode: 开始并行处理 {len(item_list)} 个项目", "info")

        # 为每个项目创建参数字典
        batch_params = [{"_item": item} for item in item_list]

        # 创建并行批处理流程
        batch_flow = AsyncParallelBatchFlow(flow=self.ItemProcessor(self), max_concurrency=self.max_concurrency)

        # 执行批处理
        batch_results = await batch_flow.exec_async(batch_params)

        # 处理批处理结果
        result_list = self._process_batch_results(batch_results)

        # 后处理阶段
        return await self.post_async(shared, item_list, result_list)
