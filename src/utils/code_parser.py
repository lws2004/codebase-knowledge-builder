"""
代码解析工具，用于解析代码库中的代码文件。
"""
import os
import re
from typing import Dict, List, Any, Optional

from ..utils.logger import log_and_notify


class CodeParser:
    """代码解析器，用于解析代码库中的代码文件"""

    def __init__(self, repo_path: str):
        """初始化代码解析器

        Args:
            repo_path: 代码库路径
        """
        self.repo_path = repo_path
        self.supported_extensions = {
            # 常见编程语言
            'py': 'python',
            'js': 'javascript',
            'ts': 'typescript',
            'jsx': 'javascript',
            'tsx': 'typescript',
            'java': 'java',
            'c': 'c',
            'cpp': 'cpp',
            'h': 'c',
            'hpp': 'cpp',
            'cs': 'csharp',
            'go': 'go',
            'rb': 'ruby',
            'php': 'php',
            'swift': 'swift',
            'kt': 'kotlin',
            'rs': 'rust',
            'scala': 'scala',
            'sh': 'shell',
            'bash': 'shell',
            'zsh': 'shell',
            'r': 'r',
            'pl': 'perl',
            'pm': 'perl',
            'lua': 'lua',
            'sql': 'sql',

            # 标记语言
            'html': 'html',
            'htm': 'html',
            'xml': 'xml',
            'css': 'css',
            'scss': 'scss',
            'sass': 'sass',
            'less': 'less',
            'md': 'markdown',
            'json': 'json',
            'yaml': 'yaml',
            'yml': 'yaml',
            'toml': 'toml',

            # 配置文件
            'ini': 'ini',
            'cfg': 'ini',
            'conf': 'ini',
            'properties': 'properties',
            'env': 'dotenv',
            'dockerfile': 'dockerfile',
        }

        # 忽略的文件和目录
        self.ignore_patterns = [
            r'\.git',
            r'\.vscode',
            r'\.idea',
            r'__pycache__',
            r'node_modules',
            r'venv',
            r'\.env',
            r'\.venv',
            r'\.DS_Store',
            r'\.pytest_cache',
            r'\.coverage',
            r'htmlcov',
            r'dist',
            r'build',
            r'\.cache',
            r'\.uv',
        ]

        # 二进制文件扩展名
        self.binary_extensions = {
            'png', 'jpg', 'jpeg', 'gif', 'bmp', 'ico', 'svg',
            'pdf', 'doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx',
            'zip', 'tar', 'gz', 'rar', '7z',
            'exe', 'dll', 'so', 'dylib',
            'pyc', 'pyo', 'pyd',
            'class',
            'o', 'obj',
            'bin', 'dat',
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
            "success": True
        }

    def _process_directory(
        self,
        _root: str,  # 未使用参数，添加下划线前缀
        rel_root: str,
        result: Dict[str, Any]
    ) -> None:
        """处理目录

        Args:
            _root: 目录绝对路径（未使用）
            rel_root: 相对路径
            result: 结果字典
        """
        if rel_root:
            result["directories"][rel_root] = {
                "type": "directory",
                "path": rel_root,
                "files": [],
                "subdirectories": []
            }
            result["directory_count"] += 1

    def _process_file(
        self,
        file_path: str,
        rel_path: str,
        rel_root: str,
        result: Dict[str, Any],
        max_file_size: int
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

    def _update_language_stats(
        self,
        file_info: Dict[str, Any],
        file_size: int,
        result: Dict[str, Any]
    ) -> None:
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
            result["language_stats"][lang] = {
                "file_count": 0,
                "total_size": 0,
                "line_count": 0
            }
        result["language_stats"][lang]["file_count"] += 1
        result["language_stats"][lang]["total_size"] += file_size
        line_count = file_info.get("line_count", 0)
        result["language_stats"][lang]["line_count"] += line_count

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

    def parse_repo(
        self,
        max_files: int = 1000,
        max_file_size: int = 1024 * 1024
    ) -> Dict[str, Any]:
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
                # 过滤掉忽略的目录
                filtered_dirs = []
                for d in dirs:
                    full_path = os.path.join(root, d)
                    if not self._should_ignore(full_path):
                        filtered_dirs.append(d)
                dirs[:] = filtered_dirs

                # 计算相对路径
                rel_root = os.path.relpath(root, self.repo_path)
                if rel_root == '.':
                    rel_root = ''

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
                    self._process_file(
                        file_path,
                        rel_path,
                        rel_root,
                        result,
                        max_file_size
                    )

            # 更新目录结构（添加子目录信息）
            self._update_directory_structure(result)

            log_and_notify(
                f"代码库解析完成: {result['file_count']} 个文件, "
                f"{result['directory_count']} 个目录, "
                f"{result['skipped_count']} 个文件被跳过",
                "info"
            )

            return result
        except Exception as e:
            error_msg = f"解析代码库失败: {str(e)}"
            log_and_notify(error_msg, "error")
            return {
                "error": error_msg,
                "success": False
            }

    def _parse_file(
        self,
        file_path: str,
        rel_path: str
    ) -> Optional[Dict[str, Any]]:
        """解析单个文件

        Args:
            file_path: 文件绝对路径
            rel_path: 相对路径

        Returns:
            文件信息
        """
        try:
            # 获取文件扩展名
            ext = os.path.splitext(file_path)[1].lower().lstrip('.')
            if not ext and '.' in os.path.basename(file_path):
                # 处理没有扩展名但有点的文件，如 .gitignore
                ext = os.path.basename(file_path).lower()

            # 确定语言
            language = self.supported_extensions.get(ext)

            # 读取文件内容
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
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
                "content": content if line_count <= 1000 else None  # 只保存小文件的内容
            }

            return file_info
        except UnicodeDecodeError:
            # 可能是二进制文件
            log_and_notify(f"无法解码文件，可能是二进制文件: {rel_path}", "warning")
            return None
        except Exception as e:
            log_and_notify(f"解析文件失败: {rel_path}, 错误: {str(e)}", "error")
            return None

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
        ext = os.path.splitext(file_path)[1].lower().lstrip('.')
        if ext in self.binary_extensions:
            return True

        # 读取文件前几个字节检查是否为二进制
        try:
            with open(file_path, 'rb') as f:
                chunk = f.read(1024)
                return b'\0' in chunk  # 包含空字节的通常是二进制文件
        except Exception:
            return False

    def extract_imports(self, content: str, language: str) -> List[str]:
        """提取文件中的导入语句

        Args:
            content: 文件内容
            language: 编程语言

        Returns:
            导入语句列表
        """
        imports = []

        if language == 'python':
            # Python 导入
            import_patterns = [
                r'^\s*import\s+([^#\n]+)',
                r'^\s*from\s+([^\s#]+)\s+import\s+([^#\n]+)'
            ]

            for pattern in import_patterns:
                matches = re.finditer(pattern, content, re.MULTILINE)
                for match in matches:
                    if len(match.groups()) == 1:
                        # import xxx
                        modules = match.group(1).strip().split(',')
                        for module in modules:
                            imports.append(f"import {module.strip()}")
                    elif len(match.groups()) == 2:
                        # from xxx import yyy
                        module = match.group(1).strip()
                        items = match.group(2).strip().split(',')
                        for item in items:
                            item_str = item.strip()
                            imports.append(f"from {module} import {item_str}")

        elif language in ['javascript', 'typescript']:
            # JavaScript/TypeScript 导入
            import_patterns = [
                r'^\s*import\s+.*?from\s+[\'"]([^\'"]+)[\'"]',
                r'^\s*require\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)'
            ]

            for pattern in import_patterns:
                matches = re.finditer(pattern, content, re.MULTILINE)
                for match in matches:
                    imports.append(match.group(1))

        return imports

    def extract_functions(
        self,
        content: str,
        language: str
    ) -> List[Dict[str, Any]]:
        """提取文件中的函数定义

        Args:
            content: 文件内容
            language: 编程语言

        Returns:
            函数定义列表
        """
        functions = []

        if language == 'python':
            # Python 函数
            func_pattern = (
                r'^\s*def\s+([^\s\(]+)\s*\(([^\)]*)\)(?:\s*->\s*([^\:]+))?\s*:'
            )
            matches = re.finditer(func_pattern, content, re.MULTILINE)

            for match in matches:
                name = match.group(1)
                params = match.group(2).strip()
                return_type = None
                if match.group(3):
                    return_type = match.group(3).strip()

                functions.append({
                    "name": name,
                    "params": params,
                    "return_type": return_type,
                    "language": "python"
                })

        elif language in ['javascript', 'typescript']:
            # JavaScript/TypeScript 函数
            # 定义不同类型的函数模式
            # 普通函数
            normal_func = r'(?:function\s+([^\s\(]+))?\s*\(([^\)]*)\)\s*{'

            # 函数表达式
            func_expr = (
                r'(?:const|let|var)\s+([^\s=]+)\s*=\s*(?:function)?\s*'
                r'\(([^\)]*)\)\s*(?:=>)?\s*{'
            )

            # 箭头函数
            arrow_func = (
                r'(?:const|let|var)\s+([^\s=]+)\s*=\s*\(([^\)]*)\)\s*=>'
            )

            func_patterns = [normal_func, func_expr, arrow_func]

            for pattern in func_patterns:
                matches = re.finditer(pattern, content, re.MULTILINE)
                for match in matches:
                    name = match.group(1)
                    if name:
                        params = match.group(2).strip()

                        functions.append({
                            "name": name,
                            "params": params,
                            "language": (
                                "javascript"
                                if language == "javascript"
                                else "typescript"
                            )
                        })

        return functions

    def extract_classes(
        self,
        content: str,
        language: str
    ) -> List[Dict[str, Any]]:
        """提取文件中的类定义

        Args:
            content: 文件内容
            language: 编程语言

        Returns:
            类定义列表
        """
        classes = []

        if language == 'python':
            # Python 类
            class_pattern = r'^\s*class\s+([^\s\(]+)(?:\s*\(([^\)]*)\))?\s*:'
            matches = re.finditer(class_pattern, content, re.MULTILINE)

            for match in matches:
                name = match.group(1)
                parents = match.group(2).strip() if match.group(2) else None

                classes.append({
                    "name": name,
                    "parents": parents,
                    "language": "python"
                })

        elif language in ['javascript', 'typescript']:
            # JavaScript/TypeScript 类
            class_pattern = (
                r'^\s*class\s+([^\s\{]+)(?:\s+extends\s+([^\s\{]+))?\s*{'
            )
            matches = re.finditer(class_pattern, content, re.MULTILINE)

            for match in matches:
                name = match.group(1)
                parent = match.group(2) if match.group(2) else None

                classes.append({
                    "name": name,
                    "parent": parent,
                    "language": (
                        "javascript"
                        if language == "javascript"
                        else "typescript"
                    )
                })

        return classes


if __name__ == "__main__":
    # 测试代码
    import sys

    if len(sys.argv) < 2:
        print("用法: python code_parser.py <repo_path>")
        sys.exit(1)

    repo_path = sys.argv[1]
    parser = CodeParser(repo_path)
    result = parser.parse_repo()

    print(f"解析完成: {result['file_count']} 个文件, {result['directory_count']} 个目录")
    print(f"语言统计: {result['language_stats']}")
