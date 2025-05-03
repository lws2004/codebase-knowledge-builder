"""异步并行批处理节点，用于并行处理多个项目。"""

import asyncio
from typing import Any, Dict, List, Optional, TypeVar, Union

from pocketflow import AsyncNode

from ..utils.logger import log_and_notify

T = TypeVar("T")


class AsyncParallelBatchNode(AsyncNode):
    """异步并行批处理节点，用于并行处理多个项目"""

    def __init__(self, max_concurrency: Optional[int] = None):
        """初始化异步并行批处理节点

        Args:
            max_concurrency: 最大并发数，默认为None（不限制）
        """
        super().__init__()
        self.max_concurrency = max_concurrency

    async def prep_async(self, shared: Dict[str, Any]) -> List[T]:
        """准备阶段，获取要处理的项目列表

        子类应该重写此方法，返回一个项目列表

        Args:
            shared: 共享存储

        Returns:
            项目列表
        """
        # 默认实现，子类应该重写此方法
        return []

    async def exec_async(self, item: T) -> Any:
        """执行阶段，处理单个项目

        子类必须重写此方法，实现对单个项目的处理逻辑

        Args:
            item: 要处理的项目

        Returns:
            处理结果
        """
        # 默认实现，子类必须重写此方法
        raise NotImplementedError("子类必须实现exec_async方法")

    async def exec_fallback_async(self, item: T, error: Exception) -> Any:
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

    async def post_async(
        self, shared: Dict[str, Any], item_list: List[T], result_list: List[Any]
    ) -> str:
        """后处理阶段，处理所有项目的结果

        Args:
            shared: 共享存储
            item_list: 准备阶段返回的项目列表
            result_list: 所有项目的处理结果列表

        Returns:
            后续动作
        """
        # 默认实现，将结果保存到共享存储
        shared["batch_results"] = result_list
        return "default"

    async def run_async(self, shared: Dict[str, Any]) -> str:
        """运行节点

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

        # 创建信号量控制并发数
        if self.max_concurrency:
            semaphore = asyncio.Semaphore(self.max_concurrency)
        else:
            # 创建一个永远可用的信号量
            semaphore = asyncio.Semaphore(len(item_list))

        async def process_item(item, index):
            async with semaphore:
                try:
                    return await self.exec_async(item)
                except Exception as e:
                    log_and_notify(f"AsyncParallelBatchNode: 处理项目 {index} 时出错: {str(e)}", "error")
                    try:
                        return await self.exec_fallback_async(item, e)
                    except Exception as fallback_error:
                        log_and_notify(
                            f"AsyncParallelBatchNode: 回退处理项目 {index} 时出错: {str(fallback_error)}", 
                            "error"
                        )
                        return None

        # 创建所有任务
        tasks = [process_item(item, i) for i, item in enumerate(item_list)]

        # 并行执行所有任务
        result_list = await asyncio.gather(*tasks)

        # 后处理阶段
        return await self.post_async(shared, item_list, result_list)
