"""生成内容流程，用于协调各个内容生成节点。"""

import asyncio
from typing import Any, Dict, List, Optional, cast

from pocketflow import AsyncFlow as PocketAsyncFlow  # Alias to avoid confusion with custom flows
from pocketflow import AsyncNode

from ..utils.logger import log_and_notify
from .async_parallel_flow import AsyncParallelFlow  # Custom parallel execution node
from .content_quality_check_node import ContentQualityCheckNode
from .generate_api_docs_node import AsyncGenerateApiDocsNode
from .generate_dependency_node import AsyncGenerateDependencyNode
from .generate_glossary_node import AsyncGenerateGlossaryNode
from .generate_module_details_node import AsyncGenerateModuleDetailsNode
from .generate_overall_architecture_node import AsyncGenerateOverallArchitectureNode
from .generate_quick_look_node import AsyncGenerateQuickLookNode
from .generate_timeline_node import AsyncGenerateTimelineNode
from .module_quality_check_node import ModuleQualityCheckNode


class SyncNodeRunner(AsyncNode):  # type: ignore[misc]
    """
    A wrapper to run synchronous pocketflow.Node instances within an AsyncFlow.

    It executes the synchronous node's run() method in a separate thread.
    """

    def __init__(self, sync_node_instance: Any, node_name: str = "sync_node_runner"):
        """
        初始化同步节点运行器。

        Args:
            sync_node_instance: 同步节点实例
            node_name: 节点名称
        """
        super().__init__()
        self._sync_node = sync_node_instance
        self._node_name = node_name
        # Retries for the wrapped sync_node are handled by its own run() method if it's a pocketflow.Node
        log_and_notify(
            f"SyncNodeRunner ({self._node_name}): Initialized for node type {type(sync_node_instance).__name__}",
            "debug",
        )

    async def prep_async(self, shared: Dict[str, Any]) -> Any:
        """
        准备阶段，检查共享状态中是否有错误。

        Args:
            shared: 共享状态

        Returns:
            共享状态或包含错误信息的字典
        """
        log_and_notify(f"SyncNodeRunner ({self._node_name}): prep_async. Passing shared.", "debug")
        # The synchronous node's prep() will be called as part of its run() method.
        # We pass the shared dictionary to exec_async.
        if shared.get("error"):  # Check for upstream errors before running sync node
            error_msg = (
                f"SyncNodeRunner ({self._node_name}): Upstream error detected in shared: {shared['error']}. Aborting."
            )
            log_and_notify(error_msg, "warning")
            return {"error": error_msg, "_sync_node_runner_prep_failed": True}
        return shared

    async def exec_async(self, prep_res: Any) -> Dict[str, Optional[str]]:
        """
        执行阶段，在单独的线程中运行同步节点的run方法。

        Args:
            prep_res: 准备阶段的结果（共享状态）

        Returns:
            包含action和error_msg的字典
        """
        # prep_res is the 'shared' dict from this wrapper's prep_async
        log_and_notify(f"SyncNodeRunner ({self._node_name}): exec_async - preparing to run sync node.", "debug")

        if isinstance(prep_res, dict) and prep_res.get("_sync_node_runner_prep_failed"):
            error_msg = prep_res.get("error", f"SyncNodeRunner ({self._node_name}): prep_async indicated failure.")
            log_and_notify(error_msg, "error")
            # Return value needs to match the Dict[str, Optional[str]] type hint
            return {"action": "error", "error_msg": error_msg}

        action_result: Optional[str] = "default"  # Default action if run doesn't specify
        error_message: Optional[str] = None
        current_shared_state = prep_res  # This is the shared dict

        try:
            # pocketflow.Node.run(shared) modifies shared in-place and returns an action string.
            log_and_notify(f"SyncNodeRunner ({self._node_name}): Executing sync node run() in thread.", "info")
            action_result = await asyncio.to_thread(self._sync_node.run, current_shared_state)
            log_and_notify(
                f"SyncNodeRunner ({self._node_name}): Sync node run() completed. Action: '{action_result}'.", "info"
            )
        except Exception as e:
            error_message = f"SyncNodeRunner ({self._node_name}): Exception during sync node run(): {e}"
            log_and_notify(error_message, "error", notify=True)
            action_result = "error"  # Treat exception as an error action
            # Ensure shared["error"] is set if an exception occurs within the sync node's run
            if "error" not in current_shared_state or not current_shared_state["error"]:
                current_shared_state["error"] = error_message
            elif error_message not in current_shared_state["error"]:
                current_shared_state["error"] += f"; {error_message}"

        # The shared dict (current_shared_state) is modified in-place by the sync_node.run().
        # We return the action and any error message for post_async to use.
        # Ensure action_result is not None, defaulting to "default" if it is.
        final_action = action_result if action_result is not None else "default"
        return {"action": final_action, "error_msg": error_message}

    async def post_async(
        self, shared: Dict[str, Any], prep_res_wrapper: Any, exec_res_wrapper: Dict[str, Optional[str]]
    ) -> str:
        """
        后处理阶段，处理执行结果并更新共享状态。

        Args:
            shared: 共享状态，已被同步节点的run方法修改
            prep_res_wrapper: 准备阶段的结果，包含执行前的共享状态
            exec_res_wrapper: 执行阶段的结果，包含action和error_msg

        Returns:
            执行结果的action字符串
        """
        # 记录未使用的参数，避免IDE警告
        _ = prep_res_wrapper
        # shared is the global shared dict, which should reflect modifications from sync_node.run()
        # prep_res_wrapper was the shared state at the start of this wrapper's execution.
        # exec_res_wrapper contains {"action": ..., "error_msg": ...}

        action = exec_res_wrapper.get("action", "default")
        error_msg_from_exec: Optional[str] = exec_res_wrapper.get("error_msg")

        log_and_notify(
            f"SyncNodeRunner ({self._node_name}): post_async. "
            f"Action from exec: '{action}'. Error from exec: {error_msg_from_exec}",
            "debug",
        )

        # If exec_async caught an exception and set error_msg_from_exec, ensure it's in shared["error"]
        if error_msg_from_exec:
            if "error" not in shared or not shared["error"]:
                shared["error"] = error_msg_from_exec
            elif error_msg_from_exec not in shared["error"]:
                shared["error"] += f"; {error_msg_from_exec}"

        # The action returned by the synchronous node's run method is the critical part.
        # This action will determine the next step in the AsyncFlow.
        log_and_notify(f"SyncNodeRunner ({self._node_name}): Returning action '{action}' to flow.", "info")

        # Ensure we return a string, even if mypy incorrectly infers Optional[str]
        return cast(str, action) if action is not None else "default"


class GenerateContentFlow(PocketAsyncFlow):  # type: ignore[misc]
    """
    生成内容流程 (PocketFlow.AsyncFlow模式)。

    用于协调各个内容生成节点。核心内容生成并行执行，质量检查串行执行。
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化生成内容流程

        Args:
            config: 整体流程配置 (可选,节点配置应由节点自行加载)
        """
        log_and_notify("GenerateContentFlow (PocketAsyncFlow): Initializing...", "info")
        self.flow_config = config or {}  # Store flow-level config if any

        from ..utils.env_manager import get_node_config

        # 1. Instantiate all individual ASYNC content generation nodes
        self.overall_architecture_node = AsyncGenerateOverallArchitectureNode(
            get_node_config("generate_overall_architecture")
        )
        self.glossary_node = AsyncGenerateGlossaryNode(get_node_config("generate_glossary"))
        self.timeline_node = AsyncGenerateTimelineNode(get_node_config("generate_timeline"))
        self.quick_look_node = AsyncGenerateQuickLookNode(get_node_config("generate_quick_look"))
        self.dependency_node = AsyncGenerateDependencyNode(get_node_config("generate_dependency"))
        self.api_docs_node = AsyncGenerateApiDocsNode(get_node_config("generate_api_docs"))
        self.module_details_node = AsyncGenerateModuleDetailsNode(get_node_config("generate_module_details"))

        # 2. Create the parallel stage using the custom AsyncParallelFlow
        parallel_content_nodes: List[AsyncNode] = [  # Ensure type hint for clarity
            self.overall_architecture_node,
            self.glossary_node,
            self.timeline_node,
            self.quick_look_node,
            self.dependency_node,
            self.api_docs_node,
            self.module_details_node,
        ]
        self.parallel_generation_stage = AsyncParallelFlow(nodes=parallel_content_nodes)  # type: ignore[arg-type]

        # 3. Instantiate SYNC Quality Check nodes
        self.content_quality_node_sync = ContentQualityCheckNode(get_node_config("content_quality_check"))
        self.module_quality_node_sync = ModuleQualityCheckNode(get_node_config("module_quality_check"))

        # 4. Wrap sync QC nodes to be used in AsyncFlow
        self.wrapped_content_quality_node = SyncNodeRunner(self.content_quality_node_sync, "ContentQualityCheck")
        self.wrapped_module_quality_node = SyncNodeRunner(self.module_quality_node_sync, "ModuleQualityCheck")

        # 5. Define flow connections and initialize PocketAsyncFlow
        super().__init__(start=self.parallel_generation_stage)

        # Standard path
        self.parallel_generation_stage >> self.wrapped_content_quality_node
        # The ContentQualityCheckNode might return "fix" or "default" or "error"
        # If "fix", it implies manual intervention or a subsequent auto-fix flow (not defined here)
        # For now, "default" and "fix" proceed to module quality check. "error" should halt.

        (self.wrapped_content_quality_node - "default") >> self.wrapped_module_quality_node  # type: ignore[operator]
        (self.wrapped_content_quality_node - "fix") >> self.wrapped_module_quality_node  # type: ignore[operator]

        # Error handling: If parallel stage returns "error", flow should stop.
        # PocketFlow's default behavior is to stop if an action has no defined transition.
        # So, if self.parallel_generation_stage.post_async returns "error", and there's no
        # (self.parallel_generation_stage - "error") >> some_error_handler_node,
        # the flow will stop, and this (GenerateContentFlow) post_async will be called.

        log_and_notify("GenerateContentFlow (PocketAsyncFlow): Initialization complete.", "info")

    async def prep_async(self, shared: Dict[str, Any]) -> Any:
        """
        Prepares the shared state for the GenerateContentFlow.

        Performs pre-checks for essential data.

        Args:
            shared: 共享状态

        Returns:
            准备好的共享状态
        """
        log_and_notify("GenerateContentFlow (PocketAsyncFlow): Prep - Performing pre-checks.", "info")

        critical_error = False
        if "code_structure" not in shared or not shared.get("code_structure", {}).get("success"):
            error_msg = "共享存储中缺少有效代码结构 (GenerateContentFlow.prep_async)"
            log_and_notify(error_msg, "error", notify=True)
            shared["error"] = shared.get("error", "") + "; " + error_msg if shared.get("error") else error_msg
            critical_error = True

        if "core_modules" not in shared or not shared.get("core_modules", {}).get("success"):
            error_msg = "共享存储中缺少有效核心模块数据 (GenerateContentFlow.prep_async)"
            log_and_notify(error_msg, "error", notify=True)
            shared["error"] = shared.get("error", "") + "; " + error_msg if shared.get("error") else error_msg
            critical_error = True

        if "llm_config" not in shared:  # LLM config is crucial for all sub-nodes
            error_msg = "共享存储中缺少LLM配置 (GenerateContentFlow.prep_async)"
            log_and_notify(error_msg, "error", notify=True)
            shared["error"] = shared.get("error", "") + "; " + error_msg if shared.get("error") else error_msg
            critical_error = True

        # Initialize a list in shared to collect errors from this flow's stages
        shared["generate_content_flow_errors"] = []

        if critical_error:
            # How an AsyncFlow's prep_async failure stops the flow is pocketflow-dependent.
            # Returning the shared dict with an error key. Subsequent nodes' prep_async should check this.
            log_and_notify(
                "GenerateContentFlow (PocketAsyncFlow): Prep - "
                "Critical error detected. Flow may not proceed correctly.",
                "error",
            )

        return shared  # Pass shared to the first stage (parallel_generation_stage)

    async def post_async(self, shared: Dict[str, Any], prep_res: Any, exec_res: Any) -> Optional[str]:
        """
        Post-execution for the entire GenerateContentFlow.

        Aggregates results and errors from the 'shared' dictionary.
        exec_res for an AsyncFlow is typically None or not directly used; results are in 'shared'.

        Args:
            shared: 共享状态
            prep_res: 准备阶段的结果（在此方法中未使用）
            exec_res: 执行阶段的结果（在此方法中未使用）

        Returns:
            执行结果的action字符串
        """
        # 记录未使用的参数，避免IDE警告
        _ = prep_res, exec_res
        log_and_notify("GenerateContentFlow (PocketAsyncFlow): Post - Aggregating final results and errors.", "info")

        # Collect any errors that were put into shared["generate_content_flow_errors"] by stages
        # or if shared["error"] was set by the last node.
        final_errors_list = shared.get("generate_content_flow_errors", [])

        # Check shared["error"] for errors from the last executed node or the parallel stage
        last_stage_error = shared.get("error")
        if last_stage_error:
            # Avoid duplicating the same error message if already collected by a node wrapper
            # This simple check might not be perfect for complex error messages.
            is_new_error = True
            for err in final_errors_list:
                if isinstance(err, str) and last_stage_error in err:
                    is_new_error = False
                    break
            if is_new_error:
                final_errors_list.append(f"Error at end of GenerateContentFlow: {last_stage_error}")

        # Structure the final result payload
        final_result_payload = {
            "architecture_doc": shared.get("architecture_doc", {"success": False, "error": "Not generated"}),
            "glossary_doc": shared.get("glossary_doc", {"success": False, "error": "Not generated"}),
            "timeline_doc": shared.get("timeline_doc", {"success": False, "error": "Not generated"}),
            "quick_look_doc": shared.get("quick_look_doc", {"success": False, "error": "Not generated"}),
            "dependency_doc": shared.get("dependency_doc", {"success": False, "error": "Not generated"}),
            "api_docs": shared.get("api_docs", {"success": False, "error": "Not generated"}),
            "module_details": shared.get(
                "module_details", {"success": False, "error": "Not generated", "docs": [], "partial_errors": []}
            ),
            "content_quality_check": shared.get("quality_check", {"success": False, "error": "Not run"}),
            "module_quality_check": shared.get(
                "module_quality_check", {"success": False, "error": "Not run"}
            ),  # Assuming module_quality_node stores results here
            "success": not final_errors_list,
            "errors": final_errors_list,
        }
        shared["generate_content_result"] = final_result_payload  # Store final result in shared

        if final_result_payload["success"]:
            log_and_notify("GenerateContentFlow (PocketAsyncFlow) completed successfully.", "info", notify=True)
            return "default"
        else:
            log_and_notify(
                f"GenerateContentFlow (PocketAsyncFlow) completed with errors: {final_result_payload['errors']}",
                "warning",
                notify=True,
            )
            # Ensure shared["error"] reflects the overall failure for any parent flow.
            shared["error"] = f"GenerateContentFlow failed: {'; '.join(map(str, final_errors_list))}"
            return "error"


# Note: The original GenerateContentFlow had its own run method.
# By converting to a pocketflow.AsyncFlow, the execution is handled by calling
# `my_generate_content_flow_instance.run_async(shared_dict)`.
# The main.py or the calling flow (e.g., AnalyzeRepoFlow) would be responsible for this.
