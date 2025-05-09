"""分析仓库流程，用于分析代码库。"""

import os  # Added for os.getenv
from typing import Any, Dict, Optional, cast

from pocketflow import AsyncFlow, AsyncNode  # Assuming pocketflow provides these

# Ensure AsyncParallelFlow is correctly imported if used.
# For now, this refactoring avoids direct use of a custom AsyncParallelFlow
# due to unclear semantics, opting for standard AsyncFlow capabilities.
from ..utils.logger import log_and_notify
from .ai_understand_core_modules_node import AsyncAIUnderstandCoreModulesNode  # Adjusted path
from .analyze_history_node import AsyncAnalyzeHistoryNode  # Adjusted path
from .parse_code_batch_node import AsyncParseCodeNode  # CORRECTED IMPORT NAME
from .prepare_rag_data_node import AsyncPrepareRAGDataNode  # Adjusted path


class ConditionalAfterParseNode(AsyncNode):
    """根据代码解析结果决定下一步操作的节点。"""

    async def prep_async(self, shared: Dict[str, Any]) -> Any:
        """准备阶段 (无特定操作)。"""
        # This node doesn't need much preparation, input is from shared.
        return None

    async def exec_async(self, prep_res: Any) -> Any:
        """执行阶段 (无特定操作)。"""
        # Execution logic is minimal, decision is in post_async based on shared.
        return None

    async def post_async(self, shared: Dict[str, Any], prep_res: Any, exec_res: Any) -> str:
        """根据共享存储中的代码解析结果决定后续动作。"""
        if shared.get("code_structure", {}).get("success"):
            log_and_notify("AnalyzeRepoFlow: 代码解析成功，继续AI理解和RAG准备。", "info")
            shared["_proceeded_with_ai_rag"] = True  # Mark that this path is taken
            return "proceed_with_ai_rag"
        else:
            error_msg = shared.get("code_structure", {}).get("error", "代码解析失败或结果无效。")
            log_and_notify(f"AnalyzeRepoFlow: {error_msg} 跳过AI理解和RAG准备。", "error")
            # Ensure the error is propagated if not already set or if this is a more specific one
            if not shared.get("error"):
                shared["error"] = error_msg
            shared["_proceeded_with_ai_rag"] = False
            return "skip_ai_rag"


class FinalSummaryNode(AsyncNode):
    """流程结束前的最终处理或总结节点。"""

    async def prep_async(self, shared: Dict[str, Any]) -> Any:
        """准备阶段，传递共享存储。"""
        log_and_notify("AnalyzeRepoFlow: 进入最终总结节点。", "info")
        # Pass relevant parts of shared to exec if needed, or exec can read shared directly
        return shared

    async def exec_async(self, prep_res: Dict[str, Any]) -> Dict[str, Any]:
        """执行阶段，设置结果占位符。"""
        # This node now primarily finalizes the 'analyze_repo_result' in shared.
        # The actual result calculation logic for the flow can be done here
        # or in the AnalyzeRepoFlow's post_async.
        # For now, it ensures a placeholder for the result.
        # The main result calculation will be in AnalyzeRepoFlow.post_async
        current_shared = prep_res
        current_shared.setdefault("analyze_repo_result", {"success": False, "error": "Result not finalized"})
        log_and_notify("AnalyzeRepoFlow: FinalSummaryNode executed.", "info")
        return cast(Dict[str, Any], current_shared["analyze_repo_result"])

    async def post_async(self, shared: Dict[str, Any], prep_res: Any, exec_res: Any) -> str:
        """后处理阶段 (无特定操作，标记流程结束)。"""
        # This node is the end of defined paths, so it returns None or "default".
        log_and_notify("AnalyzeRepoFlow: FinalSummaryNode post_async.", "info")
        return "default"


class AnalyzeRepoFlow(AsyncFlow):
    """分析仓库流程，用于分析代码库 (PocketFlow模式)"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化分析仓库流程

        Args:
            config: 流程配置
        """
        self.config = config or {}
        log_and_notify("初始化分析仓库流程 (PocketFlow模式)", "info")

        # 实例化业务逻辑节点
        parse_code_config = self.config.get("parse_code", {})
        ai_understand_config = self.config.get("ai_understand", {})
        analyze_history_config = self.config.get("analyze_history", {})
        prepare_rag_config = self.config.get("prepare_rag", {})

        # Example of conditional config modification (better driven by external config)
        if "retry_count" in ai_understand_config and os.getenv("CI_TEST_MODE") == "true":
            ai_understand_config["retry_count"] = 1
            log_and_notify("CI_TEST_MODE: AIUnderstandCoreModulesNode retry_count set to 1.", "info")

        self.parse_code_node = AsyncParseCodeNode(parse_code_config)
        self.ai_understand_node = AsyncAIUnderstandCoreModulesNode(ai_understand_config)
        self.analyze_history_node = AsyncAnalyzeHistoryNode(analyze_history_config)
        self.prepare_rag_node = AsyncPrepareRAGDataNode(prepare_rag_config)

        # 实例化辅助/流程控制节点
        self.conditional_node = ConditionalAfterParseNode()
        self.final_node = FinalSummaryNode()

        # 定义流程的起始节点
        # Stage 1: Parse Code, then Analyze History (serially in flow terms)
        # Each node is async, so I/O operations within them won't block progression.
        super().__init__(start=self.parse_code_node)

        # 连接节点
        # Path 1: Parse Code -> Analyze History -> Conditional Node
        self.parse_code_node >> self.analyze_history_node
        self.analyze_history_node >> self.conditional_node

        # Conditional node decides the next step based on its post_async return value ("action")
        action_proceed = "proceed_with_ai_rag"
        action_skip = "skip_ai_rag"

        # Using type: ignore to suppress linter errors for pocketflow's operator-based DSL,
        # assuming the syntax is correct at runtime as per pocketflow documentation.
        (self.conditional_node - action_proceed) >> self.ai_understand_node  # type: ignore[operator]
        (self.conditional_node - action_skip) >> self.final_node  # type: ignore[operator]

        # Path 2 (AI/RAG Path): AI Understand -> Prepare RAG -> Final Node
        self.ai_understand_node >> self.prepare_rag_node
        self.prepare_rag_node >> self.final_node

        # final_node is the convergence point for all paths.

    async def prep_async(self, shared: Dict[str, Any]) -> Any:
        """在 AnalyzeRepoFlow 开始前执行。"""
        log_and_notify("AnalyzeRepoFlow: Flow prep_async 开始", "info")
        if "repo_path" not in shared:
            error_msg = "共享存储中缺少仓库路径 (AnalyzeRepoFlow.prep_async)"
            log_and_notify(error_msg, "error", notify=True)
            shared["error"] = error_msg
            # Important: How a Flow's prep_async failure stops the flow
            # depends on PocketFlow's specific behavior.
            # Raising an exception here might be one way if PocketFlow handles it.
            # For now, setting shared['error'] and nodes should check this.
        shared["_proceeded_with_ai_rag"] = False  # Initialize a flag
        # It's generally good practice to call super().prep_async if the base class has one.
        # Assuming AsyncFlow's base Node class might have a prep_async.
        # If AsyncFlow itself doesn't inherit from Node directly, this might not be needed
        # or could refer to pocketflow.Node's prep_async if relevant.
        # Given PocketFlow structure, direct call to super might not be standard for Flows.
        # Let's assume prep_async for a Flow is about setting up 'shared' for its nodes.

        # If AsyncFlow's __init__ calls super().__init__ from Node, then Node's prep_async would be the base.
        # If AsyncFlow has its own prep_async or doesn't, this call might change.
        # For safety, if we are unsure of AsyncFlow's direct base or its prep_async,
        # just returning shared is a common pattern for Flow prep.
        # However, if AsyncFlow itself IS a Node or derives from one that has prep_async,
        # super call is appropriate. Let's assume it's Node-like.
        # return await super().prep_async(shared) # This line could be problematic if AsyncFlow base is not Node.
        # Let's simplify for now.
        return shared

    async def post_async(self, shared: Dict[str, Any], prep_res: Any, exec_res: Any) -> str:
        """在 AnalyzeRepoFlow 所有节点完成后执行。"""
        # For a Flow, exec_res is typically None or not directly used in post_async,
        # as results from constituent nodes are already in 'shared'.
        log_and_notify("AnalyzeRepoFlow: Flow post_async 开始评估最终结果", "info")

        # Calculate final overall_success and result structure
        # This logic was partially in FinalSummaryNode, consolidating here for clarity of Flow's output

        code_structure_success = shared.get("code_structure", {}).get("success", False)
        history_analysis_success = shared.get("history_analysis", {}).get("success", False)

        # Check if AI/RAG path was intended and if it succeeded
        proceeded_with_ai_rag = shared.get("_proceeded_with_ai_rag", False)
        ai_understand_success = True  # Assume success if skipped
        prepare_rag_success = True  # Assume success if skipped

        if proceeded_with_ai_rag:
            ai_understand_success = shared.get("core_modules", {}).get("success", False)
            prepare_rag_success = shared.get("rag_data", {}).get("success", False)

        current_final_error = shared.get("error")  # Capture any error set during the flow

        overall_success = (
            code_structure_success
            and history_analysis_success
            and ai_understand_success  # Takes into account if the path was skipped
            and prepare_rag_success  # Takes into account if the path was skipped
            and not current_final_error  # No overarching error was set
        )

        final_result = {
            "code_structure": shared.get("code_structure", {}),
            "core_modules": shared.get("core_modules", {}),  # Will be empty/default if skipped
            "history_analysis": shared.get("history_analysis", {}),
            "rag_data": shared.get("rag_data", {}),  # Will be empty/default if skipped
            "success": overall_success,
            "error": current_final_error,
        }
        shared["analyze_repo_result"] = final_result  # Ensure final result is in shared

        if overall_success:
            log_and_notify("AnalyzeRepoFlow 完成 (PocketFlow模式)", "info", notify=True)
        else:
            log_and_notify(
                f"AnalyzeRepoFlow 完成但有错误 (PocketFlow模式): {current_final_error}", "warning", notify=True
            )

        # Return an action for a parent flow, or None if this is a top-level flow end.
        if current_final_error:
            return "error"
        return "default"
