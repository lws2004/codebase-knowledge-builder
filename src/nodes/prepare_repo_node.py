"""准备仓库节点，用于克隆和准备 Git 仓库。"""

from typing import Any, Dict, Optional, cast

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
        # 直接从shared中获取参数，而不是从shared["input"]中获取
        # 这是因为InputNode已经将参数放在了shared的顶层
        repo_url = shared.get("repo_url")
        local_path = shared.get("local_path")
        branch = shared.get("branch")

        # 创建输入数据字典
        input_data = {
            "repo_url": repo_url,
            "local_path": local_path,
            "branch": branch,
        }

        # 检查输入是否有效
        if not repo_url and not local_path:
            return {"error": "缺少仓库 URL 或本地路径", "success": False}

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

        # 获取缓存配置
        use_cache = not self.config.force_clone
        cache_ttl = self.config.cache_ttl

        # 如果既没有repo_url也没有local_path，则返回错误
        if not repo_url and not local_path:
            return {"error": "缺少仓库 URL 或本地路径", "success": False}

        # 如果只有local_path而没有repo_url，则使用本地路径
        if local_path and not repo_url:
            # 创建仓库信息
            repo_info = {
                "repo_path": local_path,
                "branch": branch,
                "repo_url": None,
                "success": True,
                "used_cache": False,
            }
            return cast(Dict[str, Any], repo_info)

        # 确保repo_url不为None
        if not repo_url:
            return {"error": "缺少仓库 URL", "success": False}

        # 创建 Git 仓库管理器，启用缓存
        repo_manager = GitRepoManager(repo_url, local_path, branch, use_cache=use_cache)

        # 设置缓存有效期
        repo_manager.cache_ttl = cache_ttl

        # 克隆仓库（会自动使用缓存）
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
            "success": True,
            "used_cache": use_cache and repo_manager._is_cache_valid(),
        }

        # 获取文件列表
        file_list = repo_manager.get_file_list()
        if file_list:
            repo_info["file_count"] = len(file_list)

        return cast(Dict[str, Any], repo_info)

    def post(self, shared: Dict[str, Any], prep_res: Dict[str, Any], exec_res: Dict[str, Any]) -> str:
        """后处理阶段，将仓库信息存储到共享存储中

        Args:
            shared: 共享存储
            prep_res: 准备阶段的结果（未使用）
            exec_res: 执行阶段的结果

        Returns:
            下一个节点的动作
        """
        # 记录未使用的参数，避免IDE警告
        _ = prep_res
        if not exec_res.get("success", False):
            shared["error"] = exec_res.get("error", "准备仓库失败")
            return "error"

        # 存储仓库信息到共享存储
        shared["repo_path"] = exec_res["repo_path"]
        shared["branch"] = exec_res["branch"]
        shared["repo_url"] = exec_res["repo_url"]

        if "file_count" in exec_res:
            shared["file_count"] = exec_res["file_count"]

        # 记录是否使用了缓存
        if "used_cache" in exec_res:
            shared["used_cache"] = exec_res["used_cache"]
            if exec_res["used_cache"]:
                log_and_notify(f"使用了缓存的仓库: {exec_res['repo_url']}", "info")
            else:
                log_and_notify(f"使用了新克隆的仓库: {exec_res['repo_url']}", "info")

        return "default"
