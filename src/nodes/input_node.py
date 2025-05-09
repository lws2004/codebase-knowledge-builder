"""输入节点，用于获取用户输入。"""

# import argparse # Removed argparse
from typing import Any, Dict, Optional

from pocketflow import AsyncNode
from pydantic import BaseModel, Field

# from ..utils.config_loader import ConfigLoader # No longer directly needed here for default_branch
from ..utils.env_manager import get_node_config  # Moved to top
from ..utils.logger import log_and_notify


class InputNodeConfig(BaseModel):
    """InputNode 配置"""

    # These defaults are now primarily for type hinting and structure,
    # as actual defaults are better handled by main.py's argparse or initial shared setup.
    default_repo_url: Optional[str] = Field(None, description="默认仓库 URL")
    default_branch: Optional[str] = Field(None, description="默认分支")
    default_output_dir: str = Field("docs_output", description="默认输出目录")
    default_language: str = Field("zh", description="默认语言")
    default_local_path: Optional[str] = Field(None, description="默认本地路径")


class InputNode(AsyncNode):
    """输入节点，用于获取和验证来自共享存储的输入参数。"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化输入节点

        Args:
            config: 节点配置 (通常来自 YAML)
        """
        super().__init__()
        # Load node-specific config from YAML (e.g., for Pydantic model defaults if needed)
        default_config_from_yaml = get_node_config("input")
        merged_config_data = {**default_config_from_yaml, **(config or {})}
        self.config = InputNodeConfig(**merged_config_data)
        log_and_notify("初始化输入节点", "info")

    async def prep_async(self, shared: Dict[str, Any]) -> Dict[str, Any]:
        """准备阶段，从共享存储中提取输入参数。

        这些参数应该由 main.py 通过命令行参数和主配置文件设置。

        Args:
            shared: 共享存储

        Returns:
            提取的输入参数
        """
        log_and_notify("InputNode: prep_async - 从共享存储提取参数", "debug")

        # 主配置/命令行参数应优先于 InputNode 的 YAML 配置中的 'default_' 值
        # InputNodeConfig 的 'default_' 值更多是作为结构定义和备用（如果shared中完全没有）

        repo_url = shared.get("repo_url", self.config.default_repo_url)
        branch = shared.get("branch", self.config.default_branch)
        output_dir = shared.get("output_dir", self.config.default_output_dir)
        language = shared.get("language", self.config.default_language)
        local_path = shared.get("local_path", self.config.default_local_path)
        user_query = shared.get("user_query")  # Optional
        publish_target = shared.get("publish_target")  # Optional
        publish_repo = shared.get("publish_repo")  # Optional
        output_format = shared.get("output_format", "markdown")  # Default here or from main.py
        repo_name = shared.get("repo_name")  # Should be populated by main.py

        return {
            "repo_url": repo_url,
            "branch": branch,
            "output_dir": output_dir,
            "language": language,
            "local_path": local_path,
            "user_query": user_query,
            "publish_target": publish_target,
            "publish_repo": publish_repo,
            "output_format": output_format,
            "repo_name": repo_name,
        }

    async def exec_async(self, prep_res: Dict[str, Any]) -> Dict[str, Any]:
        """执行阶段，验证输入参数。

        Args:
            prep_res: 准备阶段的结果 (提取的参数)

        Returns:
            验证后的输入参数及成功状态
        """
        log_and_notify(f"InputNode: exec_async - 验证参数: {prep_res}", "debug")

        repo_url = prep_res.get("repo_url")
        local_path = prep_res.get("local_path")

        # 验证仓库 URL 或本地路径至少有一个存在
        if not repo_url and not local_path:
            err_msg = "必须提供仓库 URL (--repo-url) 或本地路径 (--local-path)。"
            log_and_notify(err_msg, "error", notify=True)
            return {"error": err_msg, "success": False, **prep_res}

        if repo_url and local_path:
            log_and_notify("提供了仓库URL和本地路径，将优先使用本地路径。", "warning")
            # Potentially clear repo_url if local_path takes precedence,
            # or let subsequent nodes decide.
            # For now, just log.

        # 确保 repo_name 已填充 (应由 main.py 完成)
        if not prep_res.get("repo_name"):
            err_msg = "repo_name 未在共享存储中设置 (应由 main.py 处理)。"
            log_and_notify(err_msg, "error", notify=True)
            # This is more of an assertion of a precondition set by main.py
            return {"error": err_msg, "success": False, **prep_res}

        log_and_notify(
            f"InputNode: 验证后的输入参数: repo_url={prep_res.get('repo_url')}, "
            f"local_path={prep_res.get('local_path')}, branch={prep_res.get('branch')}",
            "info",
        )

        return {"success": True, **prep_res}  # Add success flag and return all params

    async def post_async(self, shared: Dict[str, Any], prep_res: Dict[str, Any], exec_res: Dict[str, Any]) -> str:
        """后处理阶段，将最终的输入参数存储/更新到共享存储中。

        Args:
            shared: 共享存储
            prep_res: 准备阶段的结果 (原始提取的参数)
            exec_res: 执行阶段的结果 (验证后的参数及状态)

        Returns:
            下一个节点的动作
        """
        if not exec_res.get("success", False):
            shared["error"] = exec_res.get("error", "输入验证失败 (InputNode)")
            log_and_notify(f"InputNode: post_async - 输入验证失败: {shared['error']}", "error")
            return "error"  # Stop the flow

        # 更新共享存储，使用 exec_res 中的（可能已验证/调整的）值
        # exec_res 包含了所有 prep_res 的参数以及 success 标志
        shared["input_params"] = exec_res  # Store all validated params under a specific key

        # 关键参数也更新到 shared 的顶层，以供后续节点使用
        for key, value in exec_res.items():
            if key not in ["success", "error"]:  # 不要将操作标志复制到顶层
                shared[key] = value

        log_and_notify(f"InputNode: post_async - 输入参数已更新到 shared: {exec_res}", "info")
        return "default"  # Proceed to the next node
