"""测试输入和准备仓库节点的脚本。"""

import argparse
import os
import sys

from pocketflow import Flow

# 确保当前目录在 Python 路径中
sys.path.insert(0, os.path.abspath("."))

from src.nodes import InputNode, PrepareRepoNode
from src.utils.env_manager import get_llm_config, load_env_vars


def create_flow():
    """创建流程

    Returns:
        流程
    """
    # 创建节点
    input_node = InputNode()
    prepare_repo_node = PrepareRepoNode()

    # 连接节点
    input_node >> prepare_repo_node

    # 创建流程
    return Flow(start=input_node)


def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="测试输入和准备仓库节点")
    parser.add_argument(
        "--repo-url", type=str, default="https://github.com/octocat/Hello-World.git", help="Git 仓库 URL"
    )
    parser.add_argument("--branch", type=str, default="master", help="分支名称")
    parser.add_argument("--output-dir", type=str, default="docs_output", help="输出目录")
    parser.add_argument("--language", type=str, default="zh", help="输出语言")
    parser.add_argument("--local-path", type=str, default=None, help="本地仓库路径")
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
    flow = create_flow()

    # 运行流程
    print(f"开始测试输入和准备仓库节点，仓库: {args.repo_url}, 分支: {args.branch}")
    flow.run(shared)

    # 输出结果
    if "repo_path" in shared:
        print("\n准备仓库成功:")
        print(f"- 仓库路径: {shared['repo_path']}")
        print(f"- 分支: {shared['branch']}")
        print(f"- 仓库 URL: {shared['repo_url']}")
        if "file_count" in shared:
            print(f"- 文件数量: {shared['file_count']}")
    elif "error" in shared:
        print(f"\n准备仓库失败: {shared['error']}")
    else:
        print("\n流程完成，但没有生成仓库信息")


if __name__ == "__main__":
    main()
