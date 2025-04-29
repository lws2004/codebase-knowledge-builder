"""
输入节点，用于获取用户输入。
"""
import argparse
from typing import Dict, Any, Optional
from pocketflow import Node
from pydantic import BaseModel, Field

from ..utils.logger import log_and_notify
from ..utils.config_loader import ConfigLoader

class InputNodeConfig(BaseModel):
    """InputNode 配置"""
    default_repo_url: str = Field("", description="默认仓库 URL")
    default_branch: str = Field("", description="默认分支")
    default_output_dir: str = Field("docs_output", description="默认输出目录")
    default_language: str = Field("zh", description="默认语言")

class InputNode(Node):
    """输入节点，用于获取用户输入"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化输入节点

        Args:
            config: 节点配置
        """
        super().__init__()

        # 从配置文件获取默认配置
        from ..utils.env_manager import get_node_config
        default_config = get_node_config("input")

        # 合并配置
        merged_config = default_config.copy()
        if config:
            merged_config.update(config)

        self.config = InputNodeConfig(**merged_config)
        log_and_notify("初始化输入节点", "info")

        # 获取 Git 默认分支
        config_loader = ConfigLoader()
        self.default_branch = config_loader.get("git.default_branch", "main")

    def prep(self, shared: Dict[str, Any]) -> Dict[str, Any]:
        """准备阶段，解析命令行参数

        Args:
            shared: 共享存储

        Returns:
            解析后的参数
        """
        # 解析命令行参数
        parser = argparse.ArgumentParser(description="代码库知识构建器")
        parser.add_argument("--repo-url", type=str, default=self.config.default_repo_url, help="Git 仓库 URL")
        parser.add_argument("--branch", type=str, default=self.config.default_branch or self.default_branch, help="分支名称")
        parser.add_argument("--output-dir", type=str, default=self.config.default_output_dir, help="输出目录")
        parser.add_argument("--language", type=str, default=self.config.default_language, help="输出语言")
        parser.add_argument("--local-path", type=str, default=None, help="本地仓库路径")

        # 如果共享存储中有命令行参数，使用它们
        if "args" in shared:
            args = parser.parse_args(shared["args"])
        else:
            args = parser.parse_args()

        return {
            "args": args,
            "repo_url": args.repo_url,
            "branch": args.branch,
            "output_dir": args.output_dir,
            "language": args.language,
            "local_path": args.local_path
        }

    def exec(self, prep_res: Dict[str, Any]) -> Dict[str, Any]:
        """执行阶段，验证输入参数

        Args:
            prep_res: 准备阶段的结果

        Returns:
            验证后的输入参数
        """
        repo_url = prep_res.get("repo_url")
        branch = prep_res.get("branch")
        output_dir = prep_res.get("output_dir")
        language = prep_res.get("language")
        local_path = prep_res.get("local_path")

        # 验证仓库 URL
        if not repo_url:
            log_and_notify("缺少仓库 URL", "error", notify=True)
            return {"error": "缺少仓库 URL", "success": False}

        log_and_notify(f"输入参数: repo_url={repo_url}, branch={branch}, output_dir={output_dir}, language={language}", "info")

        return {
            "repo_url": repo_url,
            "branch": branch,
            "output_dir": output_dir,
            "language": language,
            "local_path": local_path,
            "success": True
        }

    def post(self, shared: Dict[str, Any], prep_res: Dict[str, Any], exec_res: Dict[str, Any]) -> str:
        """后处理阶段，将输入参数存储到共享存储中

        Args:
            shared: 共享存储
            prep_res: 准备阶段的结果
            exec_res: 执行阶段的结果

        Returns:
            下一个节点的动作
        """
        if not exec_res.get("success", False):
            shared["error"] = exec_res.get("error", "输入验证失败")
            return "error"

        # 存储输入参数到共享存储
        shared["input"] = {
            "repo_url": exec_res["repo_url"],
            "branch": exec_res["branch"],
            "output_dir": exec_res["output_dir"],
            "language": exec_res["language"],
            "local_path": exec_res["local_path"]
        }

        return "default"
