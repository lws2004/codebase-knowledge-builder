#!/usr/bin/env python
"""示例脚本：使用代码库知识构建器生成文档"""

import argparse
import asyncio
import os
import sys

# 添加项目根目录到 Python 路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pocketflow import AsyncFlow

from src.nodes import (
    AnalyzeRepoFlow,
    CombineContentNode,
    FormatOutputNode,
    GenerateContentFlow,
    InputNode,
    PrepareRepoNode,
)
from src.nodes.flow_connector_nodes import AnalyzeRepoConnector, GenerateContentConnector
from src.utils.config_loader import ConfigLoader


async def generate_docs(repo_url, language="zh", output_dir="docs_output", env="default", branch="main"):
    """
    生成代码库文档

    Args:
        repo_url: 代码库 URL
        language: 输出语言
        output_dir: 输出目录
        env: 环境配置
        branch: 代码库分支

    Returns:
        生成结果
    """
    # 加载配置
    config_loader = ConfigLoader(env)

    # 创建节点
    input_node = InputNode(config_loader.get_node_config("input"))
    prepare_repo_node = PrepareRepoNode(config_loader.get_node_config("prepare_repo"))
    analyze_repo_flow = AnalyzeRepoFlow(config_loader)
    generate_content_flow = GenerateContentFlow(
        {
            "generate_overall_architecture": config_loader.get_node_config("generate_overall_architecture"),
            "generate_api_docs": config_loader.get_node_config("generate_api_docs"),
            "generate_timeline": config_loader.get_node_config("generate_timeline"),
            "generate_dependency": config_loader.get_node_config("generate_dependency"),
            "generate_glossary": config_loader.get_node_config("generate_glossary"),
            "generate_quick_look": config_loader.get_node_config("generate_quick_look"),
            "content_quality_check": config_loader.get_node_config("content_quality_check"),
            "generate_module_details": config_loader.get_node_config("generate_module_details"),
            "module_quality_check": config_loader.get_node_config("module_quality_check"),
        }
    )
    combine_content_node = CombineContentNode(config_loader.get_node_config("combine_content"))
    format_output_node = FormatOutputNode(config_loader.get_node_config("format_output"))

    # 创建连接器节点
    analyze_repo_connector = AnalyzeRepoConnector(analyze_repo_flow)
    generate_content_connector = GenerateContentConnector(generate_content_flow)

    # 连接节点
    input_node >> prepare_repo_node
    prepare_repo_node >> analyze_repo_connector
    analyze_repo_connector >> generate_content_connector
    generate_content_connector >> combine_content_node
    combine_content_node >> format_output_node

    # 创建流程
    flow = AsyncFlow(start=input_node)

    # 准备共享存储
    shared = {
        "repo_url": repo_url,
        "branch": branch,
        "language": language,
        "output_dir": output_dir,
        "llm_config": config_loader.get_config().get("llm", {}),
        "repo_name": repo_url.split("/")[-1].replace(".git", "") if repo_url.endswith(".git") else "repo",
    }

    # 运行流程
    result = await flow.run_async(shared)

    return result


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="生成代码库文档")
    parser.add_argument("--repo-url", required=True, help="代码库 URL")
    parser.add_argument("--language", default="zh", help="输出语言")
    parser.add_argument("--output-dir", default="docs_output", help="输出目录")
    parser.add_argument("--env", default="default", help="环境配置")
    parser.add_argument("--branch", default="main", help="代码库分支")
    args = parser.parse_args()

    # 运行文档生成
    result = asyncio.run(generate_docs(args.repo_url, args.language, args.output_dir, args.env, args.branch))

    # 输出结果
    if isinstance(result, dict):
        if result.get("success", False):
            print(f"文档生成成功，输出目录: {result.get('output_dir', args.output_dir)}")
        else:
            print(f"文档生成失败: {result.get('error', '未知错误')}")
    else:
        print(f"文档生成失败: {result}")


if __name__ == "__main__":
    main()
