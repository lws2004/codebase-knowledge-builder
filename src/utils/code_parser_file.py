"""代码文件解析功能，提供单个文件的解析和处理。"""

import os
from typing import Any, Dict, Optional

from .code_parser_base import CodeParserBase
from .logger import log_and_notify


class CodeParserFile(CodeParserBase):
    """代码文件解析类，提供单个文件的解析和处理"""

    def _parse_file(self, file_path: str, rel_path: str) -> Optional[Dict[str, Any]]:
        """解析单个文件

        Args:
            file_path: 文件绝对路径
            rel_path: 相对路径

        Returns:
            文件信息
        """
        try:
            # 获取文件扩展名
            ext = os.path.splitext(file_path)[1].lower().lstrip(".")
            if not ext and "." in os.path.basename(file_path):
                # 处理没有扩展名但有点的文件，如 .gitignore
                ext = os.path.basename(file_path).lower()

            # 确定语言
            language = self.supported_extensions.get(ext)

            # 读取文件内容
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

            # 计算行数
            lines = content.splitlines()
            line_count = len(lines)

            # 创建文件信息
            file_info = {
                "type": "file",
                "path": rel_path,
                "language": language,
                "extension": ext,
                "line_count": line_count,
                "size": os.path.getsize(file_path),
                "content": content if line_count <= 1000 else None,  # 只保存小文件的内容
            }

            return file_info
        except UnicodeDecodeError:
            # 可能是二进制文件
            log_and_notify(f"无法解码文件，可能是二进制文件: {rel_path}", "warning")
            return None
        except Exception as e:
            log_and_notify(f"解析文件失败: {rel_path}, 错误: {str(e)}", "error")
            return None

    def _process_file(
        self, file_path: str, rel_path: str, rel_root: str, result: Dict[str, Any], max_file_size: int
    ) -> None:
        """处理单个文件

        Args:
            file_path: 文件绝对路径
            rel_path: 文件相对路径
            rel_root: 目录相对路径
            result: 结果字典
            max_file_size: 最大文件大小
        """
        # 检查是否应该忽略
        if self._should_ignore(file_path):
            return

        try:
            # 检查文件大小
            file_size = os.path.getsize(file_path)
            if file_size > max_file_size:
                msg = f"文件过大，跳过: {rel_path} ({file_size} 字节)"
                log_and_notify(msg, "warning")
                result["skipped_files"].append(rel_path)
                result["skipped_count"] += 1
                return

            # 检查是否为二进制文件
            if self._is_binary_file(file_path):
                log_and_notify(f"二进制文件，跳过: {rel_path}", "info")
                result["skipped_files"].append(rel_path)
                result["skipped_count"] += 1
                return

            # 解析文件
            file_info = self._parse_file(file_path, rel_path)
            if not file_info:
                result["skipped_files"].append(rel_path)
                result["skipped_count"] += 1
                return

            # 更新结果
            result["files"][rel_path] = file_info
            result["file_count"] += 1
            result["total_size"] += file_size

            # 更新语言统计
            self._update_language_stats(file_info, file_size, result)

            # 更新目录信息
            if rel_root and rel_root in result["directories"]:
                result["directories"][rel_root]["files"].append(rel_path)

        except Exception as e:
            log_and_notify(f"解析文件失败: {rel_path}, 错误: {str(e)}", "error")
            result["skipped_files"].append(rel_path)
            result["skipped_count"] += 1

    def _update_language_stats(self, file_info: Dict[str, Any], file_size: int, result: Dict[str, Any]) -> None:
        """更新语言统计

        Args:
            file_info: 文件信息
            file_size: 文件大小
            result: 结果字典
        """
        lang = file_info.get("language")
        if not lang:
            return

        if lang not in result["language_stats"]:
            result["language_stats"][lang] = {"file_count": 0, "total_size": 0, "line_count": 0}
        result["language_stats"][lang]["file_count"] += 1
        result["language_stats"][lang]["total_size"] += file_size
        line_count = file_info.get("line_count", 0)
        result["language_stats"][lang]["line_count"] += line_count
