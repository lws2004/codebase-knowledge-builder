"""
分析仓库流程，用于分析代码库。
"""
from typing import Dict, Any, Optional
from pocketflow import Flow

from ..utils.logger import log_and_notify
from .parse_code_batch_node import ParseCodeBatchNode
from .ai_understand_core_modules_node import AIUnderstandCoreModulesNode
from .analyze_history_node import AnalyzeHistoryNode
from .prepare_rag_data_node import PrepareRAGDataNode

class AnalyzeRepoFlow:
    """分析仓库流程，用于分析代码库"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化分析仓库流程

        Args:
            config: 流程配置
        """
        self.config = config or {}
        log_and_notify("初始化分析仓库流程", "info")

        # 创建节点
        parse_code_config = self.config.get("parse_code", {})
        ai_understand_config = self.config.get("ai_understand", {})
        analyze_history_config = self.config.get("analyze_history", {})
        prepare_rag_config = self.config.get("prepare_rag", {})

        # 测试时将重试次数设置为1
        if "retry_count" in ai_understand_config:
            ai_understand_config["retry_count"] = 1

        self.parse_code_node = ParseCodeBatchNode(parse_code_config)
        self.ai_understand_node = AIUnderstandCoreModulesNode(ai_understand_config)
        self.analyze_history_node = AnalyzeHistoryNode(analyze_history_config)
        self.prepare_rag_node = PrepareRAGDataNode(prepare_rag_config)

        # 创建流程
        self.flow = self._create_flow()

    def _create_flow(self) -> Flow:
        """创建流程

        Returns:
            流程
        """
        # 连接节点
        self.parse_code_node >> self.ai_understand_node
        self.parse_code_node >> self.prepare_rag_node
        self.parse_code_node >> self.analyze_history_node

        # 创建流程
        return Flow(start=self.parse_code_node)

    def run(self, shared: Dict[str, Any]) -> Dict[str, Any]:
        """运行流程

        Args:
            shared: 共享存储

        Returns:
            流程结果
        """
        log_and_notify("开始运行分析仓库流程", "info")

        # 检查共享存储中是否有必要的数据
        if "repo_path" not in shared:
            error_msg = "共享存储中缺少仓库路径"
            log_and_notify(error_msg, "error", notify=True)
            return {"error": error_msg, "success": False}

        # 运行流程
        self.flow.run(shared)

        # 检查流程是否成功
        if "error" in shared:
            return {"error": shared["error"], "success": False}

        # 收集结果
        result = {
            "code_structure": shared.get("code_structure", {}),
            "core_modules": shared.get("core_modules", {}),
            "history_analysis": shared.get("history_analysis", {}),
            "rag_data": shared.get("rag_data", {}),
            "success": True
        }

        log_and_notify("分析仓库流程完成", "info", notify=True)

        return result
