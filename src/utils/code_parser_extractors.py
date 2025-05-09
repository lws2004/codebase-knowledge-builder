"""代码提取功能，提供从代码中提取导入、函数、类等信息的功能。"""

import re
from typing import Any, Dict, List

from .code_parser_base import CodeParserBase


class CodeParserExtractors(CodeParserBase):
    """代码提取类，提供从代码中提取导入、函数、类等信息的功能"""

    def _extract_python_imports(self, content: str) -> List[str]:
        """提取Python文件中的导入语句

        Args:
            content: 文件内容

        Returns:
            导入语句列表
        """
        imports = []
        import_patterns = [r"^\s*import\s+([^#\n]+)", r"^\s*from\s+([^\s#]+)\s+import\s+([^#\n]+)"]

        for pattern in import_patterns:
            matches = re.finditer(pattern, content, re.MULTILINE)
            for match in matches:
                if len(match.groups()) == 1:
                    # import xxx
                    modules = match.group(1).strip().split(",")
                    for module in modules:
                        imports.append(f"import {module.strip()}")
                elif len(match.groups()) == 2:
                    # from xxx import yyy
                    module = match.group(1).strip()
                    items = match.group(2).strip().split(",")
                    for item in items:
                        item_str = item.strip()
                        imports.append(f"from {module} import {item_str}")

        return imports

    def _extract_js_ts_imports(self, content: str) -> List[str]:
        """提取JavaScript/TypeScript文件中的导入语句

        Args:
            content: 文件内容

        Returns:
            导入语句列表
        """
        imports = []
        import_patterns = [
            r'^\s*import\s+.*?from\s+[\'"]([^\'"]+)[\'"]',
            r'^\s*require\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)',
        ]

        for pattern in import_patterns:
            matches = re.finditer(pattern, content, re.MULTILINE)
            for match in matches:
                imports.append(match.group(1))

        return imports

    def extract_imports(self, content: str, language: str) -> List[str]:
        """提取文件中的导入语句

        Args:
            content: 文件内容
            language: 编程语言

        Returns:
            导入语句列表
        """
        if language == "python":
            return self._extract_python_imports(content)
        elif language in ["javascript", "typescript"]:
            return self._extract_js_ts_imports(content)

        # 不支持的语言返回空列表
        return []

    def extract_functions(self, content: str, language: str) -> List[Dict[str, Any]]:
        """提取文件中的函数定义

        Args:
            content: 文件内容
            language: 编程语言

        Returns:
            函数定义列表
        """
        functions = []

        if language == "python":
            # Python 函数
            func_pattern = r"^\s*def\s+([^\s\(]+)\s*\(([^\)]*)\)(?:\s*->\s*([^\:]+))?\s*:"
            matches = re.finditer(func_pattern, content, re.MULTILINE)

            for match in matches:
                name = match.group(1)
                params = match.group(2).strip()
                return_type = None
                if match.group(3):
                    return_type = match.group(3).strip()

                functions.append({"name": name, "params": params, "return_type": return_type, "language": "python"})

        elif language in ["javascript", "typescript"]:
            # JavaScript/TypeScript 函数
            # 定义不同类型的函数模式
            # 普通函数
            normal_func = r"(?:function\s+([^\s\(]+))?\s*\(([^\)]*)\)\s*{"

            # 函数表达式
            func_expr = (
                r"(?:const|let|var)\s+([^\s=]+)\s*=\s*(?:function)?\s*"
                r"\(([^\)]*)\)\s*(?:=>)?\s*{"
            )

            # 箭头函数
            arrow_func = r"(?:const|let|var)\s+([^\s=]+)\s*=\s*\(([^\)]*)\)\s*=>"

            func_patterns = [normal_func, func_expr, arrow_func]

            for pattern in func_patterns:
                matches = re.finditer(pattern, content, re.MULTILINE)
                for match in matches:
                    name = match.group(1)
                    if name:
                        params = match.group(2).strip()

                        functions.append(
                            {
                                "name": name,
                                "params": params,
                                "language": ("javascript" if language == "javascript" else "typescript"),
                            }
                        )

        return functions

    def extract_classes(self, content: str, language: str) -> List[Dict[str, Any]]:
        """提取文件中的类定义

        Args:
            content: 文件内容
            language: 编程语言

        Returns:
            类定义列表
        """
        classes = []

        if language == "python":
            # Python 类
            class_pattern = r"^\s*class\s+([^\s\(]+)(?:\s*\(([^\)]*)\))?\s*:"
            matches = re.finditer(class_pattern, content, re.MULTILINE)

            for match in matches:
                name = match.group(1)
                parents = match.group(2).strip() if match.group(2) else None

                classes.append({"name": name, "parents": parents, "language": "python"})

        elif language in ["javascript", "typescript"]:
            # JavaScript/TypeScript 类
            class_pattern = r"^\s*class\s+([^\s\{]+)(?:\s+extends\s+([^\s\{]+))?\s*{"
            matches = re.finditer(class_pattern, content, re.MULTILINE)

            for match in matches:
                name = match.group(1)
                parent = match.group(2) if match.group(2) else None

                classes.append(
                    {
                        "name": name,
                        "parent": parent,
                        "language": ("javascript" if language == "javascript" else "typescript"),
                    }
                )

        return classes
