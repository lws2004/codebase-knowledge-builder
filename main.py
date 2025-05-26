"""代码库知识构建器的主入口点"""

import argparse
import asyncio
import os
import re
from typing import Any, Dict, Optional

from pocketflow import AsyncFlow

from src.nodes import (
    AnalyzeRepoFlow,
    CombineContentNode,
    FormatOutputNode,
    GenerateContentFlow,
    InputNode,
    InteractiveQANode,
    PrepareRepoNode,
    PublishNode,
)
from src.nodes.flow_connector_nodes import AnalyzeRepoConnector, GenerateContentConnector
from src.nodes.mermaid_validation_node import MermaidValidationNode
from src.utils.config_loader import ConfigLoader
from src.utils.env_manager import get_llm_config, load_env_vars
from src.utils.logger import log_and_notify


def create_flow() -> AsyncFlow:
    """创建流程。.

    Returns:
        流程
    """
    # 加载配置
    config_loader = ConfigLoader()

    # 创建节点
    input_node = InputNode(config_loader.get_node_config("input"))
    prepare_repo_node = PrepareRepoNode(config_loader.get_node_config("prepare_repo"))
    analyze_repo_flow = AnalyzeRepoFlow(config_loader.get("nodes.analyze_repo"))
    generate_content_flow = GenerateContentFlow(config_loader.get("nodes.generate_content"))
    combine_content_node = CombineContentNode(config_loader.get_node_config("combine_content"))
    mermaid_validation_node = MermaidValidationNode(config_loader.get_node_config("mermaid_validation"))
    format_output_node = FormatOutputNode(config_loader.get_node_config("format_output"))
    interactive_qa_node = InteractiveQANode(config_loader.get_node_config("interactive_qa"))
    publish_node = PublishNode(config_loader.get_node_config("publish"))

    # 连接节点
    input_node >> prepare_repo_node
    # 错误处理通过post_async方法返回"error"字符串，不需要额外连接

    # 创建连接器节点
    analyze_repo_connector = AnalyzeRepoConnector(analyze_repo_flow)
    generate_content_connector = GenerateContentConnector(generate_content_flow)

    # 连接节点
    prepare_repo_node >> analyze_repo_connector
    analyze_repo_connector >> generate_content_connector
    generate_content_connector >> combine_content_node
    combine_content_node >> mermaid_validation_node
    mermaid_validation_node >> format_output_node
    format_output_node >> interactive_qa_node
    interactive_qa_node >> publish_node

    # 创建流程
    return AsyncFlow(start=input_node)


def parse_arguments() -> argparse.Namespace:
    """解析命令行参数。.

    Returns:
        解析后的参数
    """
    parser = argparse.ArgumentParser(description="代码库知识构建器")
    parser.add_argument("--repo-url", type=str, help="Git 仓库 URL")
    parser.add_argument("--branch", type=str, help="分支名称")
    parser.add_argument("--output-dir", type=str, help="输出目录")
    parser.add_argument("--language", type=str, help="输出语言")
    parser.add_argument("--local-path", type=str, help="本地仓库路径")
    parser.add_argument("--user-query", type=str, help="用户问题")
    parser.add_argument("--publish-target", type=str, help="发布目标平台")
    parser.add_argument("--publish-repo", type=str, help="发布目标仓库")
    parser.add_argument("--output-format", type=str, default="markdown", help="输出格式")
    parser.add_argument("--env", type=str, default="default", help="环境名称，用于加载对应的配置文件")
    return parser.parse_args()


def load_configuration(args: argparse.Namespace) -> ConfigLoader:
    """加载环境变量和配置。.

    Args:
        args: 命令行参数

    Returns:
        配置加载器
    """
    # 加载环境变量
    load_env_vars(env=args.env)

    # 加载配置
    config_loader = ConfigLoader()
    if args.env != "default":
        config_loader.load_env_config(args.env)

    # 打印当前环境变量中的模型配置，用于调试
    log_and_notify("当前环境变量中的模型配置:", "debug")
    for key in os.environ:
        if key.startswith("LLM_MODEL"):
            log_and_notify(f"- {key}={os.environ[key]}", "debug")

    return config_loader


def extract_repo_name(repo_url: Optional[str], local_path: Optional[str]) -> str:
    """从仓库URL或本地路径中提取仓库名称。.

    Args:
        repo_url: 仓库URL
        local_path: 本地仓库路径

    Returns:
        仓库名称
    """
    repo_name = "docs"  # 默认仓库名称

    if repo_url:
        # 匹配 GitHub/GitLab 等常见 Git 仓库 URL 格式
        match = re.search(r"[:/]([^/]+/[^/]+?)(?:\.git)?$", repo_url)
        if match:
            # 提取组织/用户名和仓库名
            full_name = match.group(1)
            # 只使用仓库名部分
            repo_name = full_name.split("/")[-1]
    elif local_path:
        # 如果没有 repo_url 但有 local_path，从 local_path 推断 repo_name
        repo_name = os.path.basename(os.path.normpath(local_path))

    log_and_notify(f"提取的仓库名称: {repo_name}", "info")
    return repo_name


def create_shared_storage(
    args: argparse.Namespace,
    config_loader: ConfigLoader,
    repo_name: str,
    llm_config: Dict[str, Any],
) -> Dict[str, Any]:
    """创建共享存储。.

    Args:
        args: 命令行参数
        config_loader: 配置加载器
        repo_name: 仓库名称
        llm_config: LLM配置

    Returns:
        共享存储
    """
    # 设置输出目录，如果用户未指定则使用仓库名
    output_dir = args.output_dir or config_loader.get("nodes.input.default_output_dir", "docs_output")

    # 创建共享存储
    return {
        "llm_config": llm_config,
        "repo_url": args.repo_url,
        "branch": args.branch,
        "output_dir": output_dir,
        "repo_name": repo_name,
        "language": args.language or config_loader.get("nodes.input.default_language", "zh"),
        "local_path": args.local_path,
        "user_query": args.user_query,
        "publish_target": args.publish_target,
        "publish_repo": args.publish_repo,
        "output_format": args.output_format,
        "cli_args": args,
    }


def print_results(shared: Dict[str, Any]) -> None:
    """打印处理结果。.

    Args:
        shared: 共享存储
    """
    # 输出结果 - these are user-facing outputs, so print is appropriate
    if "output_files" in shared and shared["output_files"]:
        # 打印输出文件信息
        print("\n文档生成完成:")
        print(f"- 输出目录: {shared.get('output_dir', '未指定')}")
        print(f"- 生成的文件数量: {len(shared['output_files'])}")

        # 打印文件列表
        print("\n生成的文件:")
        for file_path in shared["output_files"]:
            print(f"- {file_path}")

        # 如果有发布 URL，打印发布信息
        if "publish_url" in shared and shared["publish_url"]:
            print(f"\n文档已发布到: {shared['publish_url']}")

    # 如果有用户问题和回答，打印问答结果
    if "user_query" in shared and shared["user_query"] and "answer" in shared:
        print(f"\n问题: {shared['user_query']}")
        print(f"\n回答: {shared['answer']}")

    # 如果有错误，打印错误信息
    if "error" in shared:
        # Using log_and_notify for errors is good, but final user message can be print
        log_and_notify(f"处理失败: {shared['error']}", "error", notify=True)
        print(f"\n处理失败: {shared['error']}")
    elif "output_files" not in shared or not shared["output_files"]:
        # This is a valid outcome, not necessarily an error.
        print("\n处理完成,但没有生成文档文件.")


async def main() -> None:
    """主函数。.

    执行代码库知识构建器的主要流程。
    """
    # 解析命令行参数
    args = parse_arguments()

    # 加载配置
    config_loader = load_configuration(args)

    # 获取 LLM 配置
    llm_config = get_llm_config()

    # 提取仓库名称
    repo_name = extract_repo_name(args.repo_url, args.local_path)

    # 创建共享存储
    shared = create_shared_storage(args, config_loader, repo_name, llm_config)

    # 创建流程
    flow = create_flow()

    # 运行流程
    log_and_notify(f"开始分析仓库: {args.repo_url or args.local_path or '未指定'}", "info")
    await flow.run_async(shared)

    # 打印结果
    print_results(shared)


if __name__ == "__main__":
    # Setup basic logging if log_and_notify doesn't do it
    # For now, assuming log_and_notify handles its own setup or uses a pre-configured logger
    asyncio.run(main())
