"""测试分析仓库流程的脚本。"""

import argparse
import json
import os
import sys

from pocketflow import Flow

# 确保当前目录在 Python 路径中
sys.path.insert(0, os.path.abspath("."))

from src.nodes import AnalyzeRepoFlow, InputNode, PrepareRepoNode
from src.utils.env_manager import get_llm_config, load_env_vars


def create_flow():
    """创建流程

    Returns:
        流程
    """
    # 创建节点
    input_node = InputNode()
    prepare_repo_node = PrepareRepoNode()

    # 创建分析仓库流程
    analyze_repo_flow = AnalyzeRepoFlow()

    # 连接节点
    input_node >> prepare_repo_node

    # 创建流程
    flow = Flow(start=input_node)

    return flow, prepare_repo_node, analyze_repo_flow


def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="测试分析仓库流程")
    parser.add_argument(
        "--repo-url", type=str, default="https://github.com/octocat/Hello-World.git", help="Git 仓库 URL"
    )
    parser.add_argument("--branch", type=str, default="master", help="分支名称")
    parser.add_argument("--output-dir", type=str, default="docs", help="输出目录")
    parser.add_argument("--language", type=str, default="zh", help="输出语言")
    parser.add_argument("--local-path", type=str, default=None, help="本地仓库路径")
    parser.add_argument("--output", type=str, default="analyze_repo_result.json", help="输出文件路径")
    args = parser.parse_args()

    # 加载环境变量
    load_env_vars()

    # 获取 LLM 配置
    llm_config = get_llm_config()

    # 创建共享存储
    shared = {
        "llm_config": llm_config,
        "args": [
            f"--repo-url={args.repo_url}",
            f"--branch={args.branch}",
            f"--output-dir={args.output_dir}",
            f"--language={args.language}",
        ],
    }

    if args.local_path:
        shared["args"].append(f"--local-path={args.local_path}")

    # 创建流程
    flow, prepare_repo_node, analyze_repo_flow = create_flow()

    # 运行流程
    print(f"开始测试分析仓库流程，仓库: {args.repo_url}, 分支: {args.branch}")
    flow.run(shared)

    # 检查流程是否成功
    if "error" in shared:
        print(f"\n流程失败: {shared['error']}")
        return

    # 检查仓库是否准备好
    if "repo_path" not in shared:
        print("\n流程完成，但没有生成仓库路径")
        return

    # 运行分析仓库流程
    print("\n开始运行分析仓库流程")
    result = analyze_repo_flow.run(shared)

    # 输出结果
    if result.get("success", False):
        print("\n分析仓库流程完成:")
        print(
            f"- 代码结构: {result['code_structure'].get('file_count', 0)} 个文件, "
            f"{result['code_structure'].get('directory_count', 0)} 个目录"
        )
        print(f"- 核心模块: {len(result['core_modules'].get('modules', []))} 个")
        print(
            f"- 历史分析: {result['history_analysis'].get('commit_count', 0)} 个提交, "
            f"{result['history_analysis'].get('contributor_count', 0)} 个贡献者"
        )
        print(f"- RAG 数据: {len(result['rag_data'].get('chunks', []))} 个块")

        # 保存结果到文件
        with open(args.output, "w", encoding="utf-8") as f:
            # 简化结果，避免文件过大
            simplified_result = {
                "code_structure": {
                    "file_count": result["code_structure"].get("file_count", 0),
                    "directory_count": result["code_structure"].get("directory_count", 0),
                    "language_stats": result["code_structure"].get("language_stats", {}),
                    "file_types": result["code_structure"].get("file_types", {}),
                },
                "core_modules": {
                    "modules": result["core_modules"].get("modules", []),
                    "architecture": result["core_modules"].get("architecture", ""),
                    "relationships": result["core_modules"].get("relationships", []),
                },
                "history_analysis": {
                    "commit_count": result["history_analysis"].get("commit_count", 0),
                    "contributor_count": result["history_analysis"].get("contributor_count", 0),
                    "history_summary": result["history_analysis"].get("history_summary", ""),
                },
                "rag_data": {
                    "file_count": len(result["rag_data"].get("files", [])),
                    "chunk_count": len(result["rag_data"].get("chunks", [])),
                },
            }

            json.dump(simplified_result, f, indent=2, ensure_ascii=False)

        print(f"\n结果已保存到: {args.output}")
    else:
        print(f"\n分析仓库流程失败: {result.get('error', '未知错误')}")


if __name__ == "__main__":
    main()
