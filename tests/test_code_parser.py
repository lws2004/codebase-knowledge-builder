"""测试代码解析器的脚本。"""
import argparse
import json
import os
import sys

# 确保当前目录在 Python 路径中
sys.path.insert(0, os.path.abspath("."))

from src.utils.code_parser import CodeParser


def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="测试代码解析器")
    parser.add_argument("--repo-path", type=str, required=True, help="代码库路径")
    parser.add_argument("--max-files", type=int, default=100, help="最大解析文件数")
    parser.add_argument("--output", type=str, default="code_structure.json", help="输出文件路径")
    args = parser.parse_args()

    # 检查仓库路径是否存在
    if not os.path.exists(args.repo_path):
        print(f"错误: 仓库路径不存在: {args.repo_path}")
        return

    # 创建代码解析器
    code_parser = CodeParser(args.repo_path)

    # 设置自定义忽略模式
    code_parser.ignore_patterns = [
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
    ]

    # 解析代码库
    print(f"开始解析代码库: {args.repo_path}")
    result = code_parser.parse_repo(max_files=args.max_files)

    # 检查解析是否成功
    if not result.get("success", False):
        print(f"解析失败: {result.get('error', '未知错误')}")
        return

    # 输出结果
    print("\n解析完成:")
    print(f"- 文件数量: {result['file_count']}")
    print(f"- 目录数量: {result['directory_count']}")
    print(f"- 跳过文件数量: {result['skipped_count']}")

    # 输出语言统计
    print("\n语言统计:")
    for lang, stats in result.get("language_stats", {}).items():
        print(f"- {lang}: {stats['file_count']} 个文件, {stats['line_count']} 行代码")

    # 保存结果到文件
    with open(args.output, "w", encoding="utf-8") as f:
        # 简化结果，避免文件过大
        simplified_result = {
            "file_count": result["file_count"],
            "directory_count": result["directory_count"],
            "language_stats": result["language_stats"],
            "file_types": {},
            "directories": {}
        }

        # 提取文件类型统计
        for file_path, file_info in result.get("files", {}).items():
            ext = file_info.get("extension", "")
            if ext not in simplified_result["file_types"]:
                simplified_result["file_types"][ext] = 0
            simplified_result["file_types"][ext] += 1

        # 提取目录结构
        for dir_path, dir_info in result.get("directories", {}).items():
            simplified_result["directories"][dir_path] = {
                "type": dir_info.get("type", "directory"),
                "files": [os.path.basename(f) for f in dir_info.get("files", [])],
                "subdirectories": [os.path.basename(d) for d in dir_info.get("subdirectories", [])]
            }

        json.dump(simplified_result, f, indent=2, ensure_ascii=False)

    print(f"\n结果已保存到: {args.output}")

if __name__ == "__main__":
    main()
