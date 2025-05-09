"""代码解析工具，用于解析代码库中的代码文件。"""

import sys

from .code_parser_extractors import CodeParserExtractors
from .code_parser_repo import CodeParserRepo


class CodeParser(CodeParserRepo, CodeParserExtractors):
    """代码解析器，用于解析代码库中的代码文件"""

    pass


if __name__ == "__main__":
    # 测试代码
    if len(sys.argv) < 2:
        print("用法: python code_parser.py <repo_path>")
        sys.exit(1)

    repo_path = sys.argv[1]
    parser = CodeParser(repo_path)
    result = parser.parse_repo()

    print(f"解析完成: {result['file_count']} 个文件, {result['directory_count']} 个目录")
    print(f"语言统计: {result['language_stats']}")
