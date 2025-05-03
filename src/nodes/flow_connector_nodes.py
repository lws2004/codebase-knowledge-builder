"""流程连接器节点，用于连接不同的流程。"""

from typing import Any, Dict

from pocketflow import Node


class FlowConnectorNode(Node):
    """流程连接器节点，用于连接不同的流程"""

    def __init__(self, flow):
        """初始化流程连接器节点

        Args:
            flow: 要连接的流程
        """
        super().__init__()
        self.flow = flow

    def prep(self, shared: Dict[str, Any]) -> Dict[str, Any]:
        """准备阶段，获取共享存储

        Args:
            shared: 共享存储

        Returns:
            准备结果
        """
        return shared

    def exec(self, prep_res: Dict[str, Any]) -> Dict[str, Any]:
        """执行阶段，运行流程

        Args:
            prep_res: 准备结果

        Returns:
            执行结果
        """
        return self.flow.run(prep_res)

    def post(self, shared: Dict[str, Any], prep_res: Dict[str, Any], exec_res: Dict[str, Any]) -> str:
        """后处理阶段，更新共享存储

        Args:
            shared: 共享存储
            prep_res: 准备阶段的结果
            exec_res: 执行结果

        Returns:
            后续动作
        """
        # 将流程结果合并到共享存储中
        shared.update(exec_res)
        return "default"


class AnalyzeRepoConnector(FlowConnectorNode):
    """分析仓库流程连接器节点"""

    def __init__(self, analyze_repo_flow):
        """初始化分析仓库流程连接器节点

        Args:
            analyze_repo_flow: 分析仓库流程
        """
        super().__init__(analyze_repo_flow)


class GenerateContentConnector(FlowConnectorNode):
    """生成内容流程连接器节点"""

    def __init__(self, generate_content_flow):
        """初始化生成内容流程连接器节点

        Args:
            generate_content_flow: 生成内容流程
        """
        super().__init__(generate_content_flow)
