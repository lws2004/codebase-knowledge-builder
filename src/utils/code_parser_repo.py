"""代码库解析功能，提供整个代码库的解析和处理。"""

import os
from typing import Any, Dict

from .code_parser_file import CodeParserFile
from .logger import log_and_notify


class CodeParserRepo(CodeParserFile):
    """代码库解析类，提供整个代码库的解析和处理"""

    def _process_directory(
        self,
        root: str,  # 目录绝对路径
        rel_root: str,
        result: Dict[str, Any],
    ) -> None:
        """处理目录

        Args:
            root: 目录绝对路径
            rel_root: 相对路径
            result: 结果字典
        """
        # 使用root参数，避免IDE警告
        if os.path.exists(root) and rel_root:
            result["directories"][rel_root] = {"type": "directory", "path": rel_root, "files": [], "subdirectories": []}
            result["directory_count"] += 1

    def _update_directory_structure(self, result: Dict[str, Any]) -> None:
        """更新目录结构

        Args:
            result: 结果字典
        """
        for dir_path, _ in result["directories"].items():
            parent_dir = os.path.dirname(dir_path)
            if parent_dir and parent_dir in result["directories"]:
                parent_dict = result["directories"][parent_dir]
                parent_dirs = parent_dict["subdirectories"]
                parent_dirs.append(dir_path)

    def parse_repo(self, max_files: int = 1000, max_file_size: int = 1024 * 1024) -> Dict[str, Any]:
        """解析整个代码库

        Args:
            max_files: 最大解析文件数
            max_file_size: 最大文件大小（字节）

        Returns:
            解析结果
        """
        log_and_notify(f"开始解析代码库: {self.repo_path}", "info")
        result = self._init_result_dict()

        try:
            # 遍历代码库
            for root, dirs, files in os.walk(self.repo_path):
                # 过滤掉忽略的目录
                filtered_dirs = []
                for d in dirs:
                    full_path = os.path.join(root, d)
                    if not self._should_ignore(full_path):
                        filtered_dirs.append(d)
                dirs[:] = filtered_dirs

                # 计算相对路径
                rel_root = os.path.relpath(root, self.repo_path)
                if rel_root == ".":
                    rel_root = ""

                # 添加目录信息
                self._process_directory(root, rel_root, result)

                # 处理文件
                for file in files:
                    # 检查是否达到最大文件数
                    if result["file_count"] >= max_files:
                        log_and_notify(f"达到最大文件数 {max_files}，停止解析", "warning")
                        result["skipped_count"] += len(files)
                        break

                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, self.repo_path)
                    self._process_file(file_path, rel_path, rel_root, result, max_file_size)

            # 更新目录结构（添加子目录信息）
            self._update_directory_structure(result)

            log_and_notify(
                f"代码库解析完成: {result['file_count']} 个文件, "
                f"{result['directory_count']} 个目录, "
                f"{result['skipped_count']} 个文件被跳过",
                "info",
            )

            return result
        except Exception as e:
            error_msg = f"解析代码库失败: {str(e)}"
            log_and_notify(error_msg, "error")
            return {"error": error_msg, "success": False}
