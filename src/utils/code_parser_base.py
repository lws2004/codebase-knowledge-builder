"""代码解析器基础类，提供初始化和配置功能。"""

import os
import re
from typing import Any, Dict, List, Set


class CodeParserBase:
    """代码解析器基础类，提供初始化和配置功能"""

    def __init__(self, repo_path: str):
        """初始化代码解析器基础类

        Args:
            repo_path: 代码库路径
        """
        self.repo_path = repo_path
        self.supported_extensions = self._init_supported_extensions()
        self.ignore_patterns = self._init_ignore_patterns()
        self.binary_extensions = self._init_binary_extensions()

    def _init_supported_extensions(self) -> Dict[str, str]:
        """初始化支持的文件扩展名

        Returns:
            支持的文件扩展名字典，键为扩展名，值为语言名称
        """
        return {
            # 常见编程语言
            "py": "python",
            "js": "javascript",
            "ts": "typescript",
            "jsx": "javascript",
            "tsx": "typescript",
            "java": "java",
            "c": "c",
            "cpp": "cpp",
            "h": "c",
            "hpp": "cpp",
            "cs": "csharp",
            "go": "go",
            "rb": "ruby",
            "php": "php",
            "swift": "swift",
            "kt": "kotlin",
            "rs": "rust",
            "scala": "scala",
            "sh": "shell",
            "bash": "shell",
            "zsh": "shell",
            "r": "r",
            "pl": "perl",
            "pm": "perl",
            "lua": "lua",
            "sql": "sql",
            # 标记语言
            "html": "html",
            "htm": "html",
            "xml": "xml",
            "css": "css",
            "scss": "scss",
            "sass": "sass",
            "less": "less",
            "md": "markdown",
            "json": "json",
            "yaml": "yaml",
            "yml": "yaml",
            "toml": "toml",
            # 配置文件
            "ini": "ini",
            "cfg": "ini",
            "conf": "ini",
            "properties": "properties",
            "env": "dotenv",
            "dockerfile": "dockerfile",
        }

    def _init_ignore_patterns(self) -> List[str]:
        """初始化忽略的文件和目录模式

        Returns:
            忽略的文件和目录模式列表
        """
        return [
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
            r"\.uv",
        ]

    def _init_binary_extensions(self) -> Set[str]:
        """初始化二进制文件扩展名

        Returns:
            二进制文件扩展名集合
        """
        return {
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
        }

    def _init_result_dict(self) -> Dict[str, Any]:
        """初始化结果字典

        Returns:
            初始化的结果字典
        """
        return {
            "files": {},
            "directories": {},
            "file_count": 0,
            "directory_count": 0,
            "language_stats": {},
            "total_size": 0,
            "skipped_files": [],
            "skipped_count": 0,
            "success": True,
        }

    def _should_ignore(self, path: str) -> bool:
        """检查是否应该忽略文件或目录

        Args:
            path: 文件或目录路径

        Returns:
            是否应该忽略
        """
        rel_path = os.path.relpath(path, self.repo_path)

        # 检查忽略模式
        for pattern in self.ignore_patterns:
            if re.search(pattern, rel_path):
                return True

        return False

    def _is_binary_file(self, file_path: str) -> bool:
        """检查是否为二进制文件

        Args:
            file_path: 文件路径

        Returns:
            是否为二进制文件
        """
        # 检查扩展名
        ext = os.path.splitext(file_path)[1].lower().lstrip(".")
        if ext in self.binary_extensions:
            return True

        # 读取文件前几个字节检查是否为二进制
        try:
            with open(file_path, "rb") as f:
                chunk = f.read(1024)
                return b"\0" in chunk  # 包含空字节的通常是二进制文件
        except Exception:
            return False
