"""代码库知识构建器的主入口点。"""

import argparse

from pocketflow import Flow

from src.nodes import (
    AnalyzeRepoFlow,
    CombineAndTranslateNode,
    FormatOutputNode,
    GenerateContentFlow,
    InputNode,
    InteractiveQANode,
    PrepareRepoNode,
    PublishNode,
)
from src.nodes.flow_connector_nodes import AnalyzeRepoConnector, GenerateContentConnector
from src.utils.config_loader import ConfigLoader
from src.utils.env_manager import get_llm_config, load_env_vars


def create_flow():
    """创建流程

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
    combine_translate_node = CombineAndTranslateNode(config_loader.get_node_config("combine_translate"))
    format_output_node = FormatOutputNode(config_loader.get_node_config("format_output"))
    interactive_qa_node = InteractiveQANode(config_loader.get_node_config("interactive_qa"))
    publish_node = PublishNode(config_loader.get_node_config("publish"))

    # 连接节点
    input_node >> prepare_repo_node

    # 创建连接器节点
    analyze_repo_connector = AnalyzeRepoConnector(analyze_repo_flow)
    generate_content_connector = GenerateContentConnector(generate_content_flow)

    # 连接节点
    prepare_repo_node >> analyze_repo_connector
    analyze_repo_connector >> generate_content_connector
    generate_content_connector >> combine_translate_node
    combine_translate_node >> format_output_node
    format_output_node >> interactive_qa_node
    interactive_qa_node >> publish_node

    # 创建流程
    return Flow(start=input_node)


def main():
    """主函数"""
    # 解析命令行参数
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
    args = parser.parse_args()

    # 加载环境变量和配置
    load_env_vars(env=args.env)

    # 加载配置
    config_loader = ConfigLoader()
    if args.env != "default":
        config_loader.load_env_config(args.env)

    # 打印当前环境变量中的模型配置，用于调试
    import os

    print("当前环境变量中的模型配置:")
    for key in os.environ:
        if key.startswith("LLM_MODEL"):
            print(f"- {key}={os.environ[key]}")

    # 获取 LLM 配置
    llm_config = get_llm_config()

    # 创建共享存储
    shared = {
        "llm_config": llm_config,
        "repo_url": args.repo_url,
        "branch": args.branch,
        "output_dir": args.output_dir or config_loader.get("nodes.input.default_output_dir", "docs_output"),
        "language": args.language or config_loader.get("nodes.input.default_language", "zh"),
        "local_path": args.local_path,
        "user_query": args.user_query,
        "publish_target": args.publish_target,
        "publish_repo": args.publish_repo,
        "output_format": args.output_format,
    }

    # 创建流程
    flow = create_flow()

    # 运行流程
    print(f"开始分析仓库: {args.repo_url or '未指定'}")
    flow.run(shared)

    # 输出结果
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
        print(f"\n处理失败: {shared['error']}")
    elif "output_files" not in shared or not shared["output_files"]:
        print("\n处理完成，但没有生成文档文件")


if __name__ == "__main__":
    main()
