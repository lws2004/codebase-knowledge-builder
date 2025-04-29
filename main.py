"""
代码库知识构建器的主入口点。
"""
import os
import argparse
from pocketflow import Flow
from dotenv import load_dotenv

from src.nodes import AnalyzeHistoryNode, InputNode, PrepareRepoNode
from src.utils.env_manager import load_env_vars, get_llm_config
from src.utils.config_loader import ConfigLoader

def create_flow():
    """创建流程

    Returns:
        流程
    """
    # 创建节点
    input_node = InputNode()
    prepare_repo_node = PrepareRepoNode()
    analyze_history_node = AnalyzeHistoryNode()

    # 连接节点
    input_node >> prepare_repo_node >> analyze_history_node

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
    parser.add_argument("--output", type=str, default="history_analysis.json", help="历史分析输出文件路径")
    parser.add_argument("--env", type=str, default="default", help="环境名称，用于加载对应的配置文件")
    args = parser.parse_args()

    # 加载环境变量和配置
    load_env_vars(env=args.env)

    # 获取 LLM 配置
    llm_config = get_llm_config()

    # 创建共享存储
    shared = {
        "llm_config": llm_config,
        "args": [
            f"--repo-url={args.repo_url}" if args.repo_url else "",
            f"--branch={args.branch}" if args.branch else "",
            f"--output-dir={args.output_dir}" if args.output_dir else "",
            f"--language={args.language}" if args.language else "",
            f"--local-path={args.local_path}" if args.local_path else ""
        ]
    }

    # 过滤掉空参数
    shared["args"] = [arg for arg in shared["args"] if arg]

    # 创建流程
    flow = create_flow()

    # 运行流程
    print(f"开始分析仓库: {args.repo_url or '未指定'}")
    flow.run(shared)

    # 输出结果
    if "history_analysis" in shared and shared["history_analysis"].get("success", False):
        analysis = shared["history_analysis"]

        # 打印摘要信息
        print(f"\n分析完成:")
        print(f"- 提交数量: {analysis.get('commit_count', 0)}")
        print(f"- 贡献者数量: {analysis.get('contributor_count', 0)}")
        print(f"- 分析的文件数量: {len(analysis.get('file_histories', {}))}")

        # 保存结果到文件
        import json
        with open(args.output, "w", encoding="utf-8") as f:
            # 移除过大的字段以减小文件大小
            output_analysis = analysis.copy()
            if "commit_history" in output_analysis:
                output_analysis["commit_history"] = output_analysis["commit_history"][:10]  # 只保留前 10 个提交

            json.dump(output_analysis, f, indent=2, ensure_ascii=False)

        print(f"\n结果已保存到: {args.output}")

        # 打印历史总结
        if "history_summary" in analysis and analysis["history_summary"]:
            print("\n历史总结:")
            print(analysis["history_summary"])
    elif "error" in shared:
        print(f"\n分析失败: {shared['error']}")
    else:
        print("\n分析完成，但没有生成历史分析结果")

if __name__ == "__main__":
    main()
