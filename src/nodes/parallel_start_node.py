"""并行启动节点，用于并行启动多个节点。"""

from typing import Any, Dict, List

from pocketflow import Node


class ParallelStartNode(Node):
    """并行启动节点，用于并行启动多个节点"""

    def __init__(self, next_nodes: List[Node]):
        """初始化并行启动节点

        Args:
            next_nodes: 要并行启动的节点列表
        """
        super().__init__()
        self.next_nodes = next_nodes

    def prep(self, shared: Dict[str, Any]) -> Dict[str, Any]:
        """准备阶段，获取共享存储

        Args:
            shared: 共享存储

        Returns:
            准备结果
        """
        return shared

    def exec(self, prep_res: Dict[str, Any]) -> Dict[str, Any]:
        """执行阶段，准备并行执行

        Args:
            prep_res: 准备结果

        Returns:
            执行结果
        """
        return {"success": True}

    def post(self, shared: Dict[str, Any], prep_res: Dict[str, Any], exec_res: Dict[str, Any]) -> str:
        """后处理阶段，返回并行动作

        Args:
            shared: 共享存储
            prep_res: 准备阶段的结果
            exec_res: 执行结果

        Returns:
            后续动作
        """
        # 返回"parallel"动作，表示并行执行多个节点
        return "parallel"
