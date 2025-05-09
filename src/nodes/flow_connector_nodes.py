"""流程连接器节点，用于连接不同的流程。"""

from typing import Any, Dict

from pocketflow import AsyncFlow, AsyncNode


class FlowConnectorNode(AsyncNode):
    """流程连接器节点，用于连接不同的流程"""

    def __init__(self, flow: AsyncFlow) -> None:
        """初始化流程连接器节点

        Args:
            flow: 要连接的流程
        """
        super().__init__()
        self.flow = flow

    async def prep_async(self, shared: Dict[str, Any]) -> Dict[str, Any]:
        """准备阶段，获取共享存储

        Args:
            shared: 共享存储

        Returns:
            准备结果
        """
        return shared

    async def exec_async(self, prep_res: Dict[str, Any]) -> Dict[str, Any]:
        """执行阶段，运行流程

        Args:
            prep_res: 准备结果

        Returns:
            执行结果
        """
        # prep_res is the shared dictionary for the sub-flow to run with.
        # The sub-flow (self.flow) will modify prep_res in place.
        await self.flow.run_async(prep_res)  # Assuming self.flow is an AsyncFlow
        # The result of an AsyncFlow's run_async is usually None or an action string,
        # with modifications happening in the 'shared' dict (prep_res here).
        # We need to return the modified shared state.
        return prep_res

    async def post_async(self, shared: Dict[str, Any], prep_res: Dict[str, Any], exec_res: Dict[str, Any]) -> str:
        """后处理阶段，更新共享存储

        Args:
            shared: 共享存储
            prep_res: 准备阶段的结果
            exec_res: 执行结果

        Returns:
            后续动作
        """
        # 将流程结果合并到共享存储中
        if isinstance(exec_res, dict):
            shared.update(exec_res)
        return "default"


class AnalyzeRepoConnector(FlowConnectorNode):
    """分析仓库流程连接器节点"""

    def __init__(self, analyze_repo_flow: AsyncFlow) -> None:
        """初始化分析仓库流程连接器节点

        Args:
            analyze_repo_flow: 分析仓库流程
        """
        super().__init__(analyze_repo_flow)


class GenerateContentConnector(FlowConnectorNode):
    """生成内容流程连接器节点"""

    def __init__(self, generate_content_flow: AsyncFlow) -> None:
        """初始化生成内容流程连接器节点

        Args:
            generate_content_flow: 生成内容流程
        """
        super().__init__(generate_content_flow)
