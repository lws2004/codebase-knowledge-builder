"""解析代码批处理节点，用于解析代码库中的代码。"""

import os
from typing import Any, Dict, List, Optional

from pocketflow import Node
from pydantic import BaseModel, Field

from ..utils.code_parser import CodeParser
from ..utils.logger import log_and_notify


class ParseCodeBatchNodeConfig(BaseModel):
    """ParseCodeBatchNode 配置"""

    max_files: int = Field(1000, description="最大解析文件数量")
    batch_size: int = Field(100, description="批处理大小")
    ignore_patterns: List[str] = Field(
        [
            r"\.git",
            r"\.vscode",
            r"\.idea",
            r"__pycache__",
            r"node_modules",
            r"venv",
            r"\.env",
            r"\.venv",
            r"\.DS_Store",
            r"\.pytest_cache",
            r"\.coverage",
            r"htmlcov",
            r"dist",
            r"build",
            r"\.cache",
        ],
        description="忽略的文件和目录模式",
    )
    binary_extensions: List[str] = Field(
        [
            "png",
            "jpg",
            "jpeg",
            "gif",
            "bmp",
            "ico",
            "svg",
            "pdf",
            "doc",
            "docx",
            "ppt",
            "pptx",
            "xls",
            "xlsx",
            "zip",
            "tar",
            "gz",
            "rar",
            "7z",
            "exe",
            "dll",
            "so",
            "dylib",
            "pyc",
            "pyo",
            "pyd",
            "class",
            "o",
            "obj",
            "bin",
            "dat",
        ],
        description="二进制文件扩展名",
    )


class ParseCodeBatchNode(Node):
    """解析代码批处理节点，用于解析代码库中的代码"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化解析代码批处理节点

        Args:
            config: 节点配置
        """
        super().__init__()

        # 从配置文件获取默认配置
        from ..utils.env_manager import get_node_config

        default_config = get_node_config("parse_code_batch")

        # 合并配置
        merged_config = default_config.copy()
        if config:
            merged_config.update(config)

        self.config = ParseCodeBatchNodeConfig(**merged_config)
        log_and_notify("初始化解析代码批处理节点", "info")

    def prep(self, shared: Dict[str, Any]) -> Dict[str, Any]:
        """准备阶段，从共享存储中获取仓库路径

        Args:
            shared: 共享存储

        Returns:
            包含仓库路径的字典
        """
        log_and_notify("ParseCodeBatchNode: 准备阶段开始", "info")

        # 从共享存储中获取仓库路径
        repo_path = shared.get("repo_path")
        if not repo_path:
            error_msg = "共享存储中缺少仓库路径"
            log_and_notify(error_msg, "error", notify=True)
            return {"error": error_msg}

        # 检查仓库路径是否存在
        if not os.path.exists(repo_path):
            error_msg = f"仓库路径不存在: {repo_path}"
            log_and_notify(error_msg, "error", notify=True)
            return {"error": error_msg}

        return {
            "repo_path": repo_path,
            "max_files": self.config.max_files,
            "batch_size": self.config.batch_size,
            "ignore_patterns": self.config.ignore_patterns,
            "binary_extensions": self.config.binary_extensions,
        }

    def exec(self, prep_res: Dict[str, Any]) -> Dict[str, Any]:
        """执行阶段，解析代码库中的代码

        Args:
            prep_res: 准备阶段的结果

        Returns:
            解析结果
        """
        log_and_notify("ParseCodeBatchNode: 执行阶段开始", "info")

        # 检查准备阶段是否出错
        if "error" in prep_res:
            return {"error": prep_res["error"], "success": False}

        repo_path = prep_res["repo_path"]
        max_files = prep_res["max_files"]
        ignore_patterns = prep_res["ignore_patterns"]
        binary_extensions = prep_res["binary_extensions"]

        try:
            # 创建代码解析器
            parser = CodeParser(repo_path=repo_path)

            # 设置忽略模式和二进制扩展名
            parser.ignore_patterns = ignore_patterns
            parser.binary_extensions = set(binary_extensions)

            # 解析代码库
            log_and_notify(f"开始解析代码库: {repo_path}", "info")
            parse_result = parser.parse_repo(max_files=max_files)

            # 提取关键信息
            result = {
                "file_count": parse_result.get("file_count", 0),
                "directory_count": parse_result.get("directory_count", 0),
                "skipped_count": parse_result.get("skipped_count", 0),
                "language_stats": parse_result.get("language_stats", {}),
                "file_types": parse_result.get("file_types", {}),
                "files": parse_result.get("files", {}),
                "directories": parse_result.get("directories", {}),
                "success": True,
            }

            log_and_notify(
                f"代码解析完成: {result['file_count']} 个文件, "
                f"{result['directory_count']} 个目录, "
                f"{result['skipped_count']} 个跳过的文件",
                "info",
            )

            return result
        except Exception as e:
            error_msg = f"解析代码失败: {str(e)}"
            log_and_notify(error_msg, "error", notify=True)
            return {"error": error_msg, "success": False}

    def post(self, shared: Dict[str, Any], _prep_res: Dict[str, Any], exec_res: Dict[str, Any]) -> str:
        """后处理阶段，将解析结果存储到共享存储中

        Args:
            shared: 共享存储
            _prep_res: 准备阶段的结果（未使用）
            exec_res: 执行阶段的结果

        Returns:
            下一个节点的动作
        """
        log_and_notify("ParseCodeBatchNode: 后处理阶段开始", "info")

        # 检查执行阶段是否出错
        if not exec_res.get("success", False):
            error_msg = exec_res.get("error", "未知错误")
            log_and_notify(f"代码解析失败: {error_msg}", "error", notify=True)
            shared["code_structure"] = {"error": error_msg, "success": False}
            return "error"

        # 获取仓库名称
        repo_name = shared.get("repo_name", "unknown")

        # 将解析结果存储到共享存储中
        shared["code_structure"] = {
            "file_count": exec_res.get("file_count", 0),
            "directory_count": exec_res.get("directory_count", 0),
            "language_stats": exec_res.get("language_stats", {}),
            "file_types": exec_res.get("file_types", {}),
            "files": exec_res.get("files", {}),
            "directories": exec_res.get("directories", {}),
            "repo_name": repo_name,  # 添加仓库名称
            "success": True,
        }

        log_and_notify(
            f"代码解析完成，解析了 {exec_res.get('file_count', 0)} 个文件和 "
            f"{exec_res.get('directory_count', 0)} 个目录",
            "info",
            notify=True,
        )

        return "default"
