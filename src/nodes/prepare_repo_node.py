"""准备仓库节点，用于克隆和准备 Git 仓库。"""
from typing import Any, Dict, Optional

from pocketflow import Node
from pydantic import BaseModel, Field

from ..utils.git_utils import GitRepoManager
from ..utils.logger import log_and_notify


class PrepareRepoNodeConfig(BaseModel):
    """PrepareRepoNode 配置"""
    cache_ttl: int = Field(86400, description="缓存有效期，单位：秒")
    force_clone: bool = Field(False, description="是否强制克隆")

class PrepareRepoNode(Node):
    """准备仓库节点，用于克隆和准备 Git 仓库"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化准备仓库节点

        Args:
            config: 节点配置
        """
        super().__init__()

        # 从配置文件获取默认配置
        from ..utils.env_manager import get_node_config
        default_config = get_node_config("prepare_repo")

        # 合并配置
        merged_config = default_config.copy()
        if config:
            merged_config.update(config)

        self.config = PrepareRepoNodeConfig(**merged_config)
        log_and_notify("初始化准备仓库节点", "info")

    def prep(self, shared: Dict[str, Any]) -> Dict[str, Any]:
        """准备阶段，从共享存储中获取用户输入

        Args:
            shared: 共享存储

        Returns:
            用户输入
        """
        input_data = shared.get("input", {})

        # 检查输入是否有效
        if not input_data:
            return {"error": "缺少输入数据", "success": False}

        return input_data

    def exec(self, prep_res: Dict[str, Any]) -> Dict[str, Any]:
        """执行阶段，克隆和准备 Git 仓库

        Args:
            prep_res: 准备阶段的结果

        Returns:
            仓库信息
        """
        repo_url = prep_res.get("repo_url")
        local_path = prep_res.get("local_path")
        branch = prep_res.get("branch", "main")

        if not repo_url:
            return {"error": "缺少仓库 URL", "success": False}

        # 创建 Git 仓库管理器
        repo_manager = GitRepoManager(repo_url, local_path, branch)

        # 克隆仓库
        if not repo_manager.clone():
            return {"error": "克隆仓库失败", "success": False}

        # 检出指定分支
        if branch != "main" and not repo_manager.checkout(branch):
            return {"error": f"检出分支 {branch} 失败", "success": False}

        # 获取仓库基本信息
        repo_info = {
            "repo_path": repo_manager.local_path,
            "branch": branch,
            "repo_url": repo_url,
            "success": True
        }

        # 获取文件列表
        file_list = repo_manager.get_file_list()
        if file_list:
            repo_info["file_count"] = len(file_list)

        return repo_info

    def post(self, shared: Dict[str, Any], prep_res: Dict[str, Any], exec_res: Dict[str, Any]) -> str:
        """后处理阶段，将仓库信息存储到共享存储中

        Args:
            shared: 共享存储
            prep_res: 准备阶段的结果
            exec_res: 执行阶段的结果

        Returns:
            下一个节点的动作
        """
        if not exec_res.get("success", False):
            shared["error"] = exec_res.get("error", "准备仓库失败")
            return "error"

        # 存储仓库信息到共享存储
        shared["repo_path"] = exec_res["repo_path"]
        shared["branch"] = exec_res["branch"]
        shared["repo_url"] = exec_res["repo_url"]

        if "file_count" in exec_res:
            shared["file_count"] = exec_res["file_count"]

        return "default"
