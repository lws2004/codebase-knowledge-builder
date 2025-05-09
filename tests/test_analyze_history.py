"""测试 AnalyzeHistoryNode 节点的脚本。"""

import argparse
import json

from src.nodes import AsyncAnalyzeHistoryNode
from src.utils.env_manager import get_llm_config, load_env_vars


def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="测试 AnalyzeHistoryNode 节点")
    parser.add_argument("--repo-path", type=str, default=".", help="Git 仓库路径")
    parser.add_argument("--max-commits", type=int, default=50, help="最大分析的提交数量")
    parser.add_argument("--output", type=str, default="history_analysis.json", help="输出文件路径")
    args = parser.parse_args()

    # 加载环境变量
    load_env_vars()

    # 获取 LLM 配置
    llm_config = get_llm_config()

    # 创建共享存储
    shared = {"repo_path": args.repo_path, "llm_config": llm_config}

    # 创建节点配置
    node_config = {"max_commits": args.max_commits, "include_file_history": True, "analyze_contributors": True}

    # 创建被测节点实例
    node = AsyncAnalyzeHistoryNode(config=node_config)

    # 运行节点
    print(f"开始分析仓库: {args.repo_path}")
    prep_res = node.prep(shared)
    exec_res = node.exec(prep_res)
    node.post(shared, prep_res, exec_res)

    # 输出结果
    if "history_analysis" in shared and shared["history_analysis"].get("success", False):
        analysis = shared["history_analysis"]

        # 打印摘要信息
        print("\n分析完成:")
        print(f"- 提交数量: {analysis.get('commit_count', 0)}")
        print(f"- 贡献者数量: {analysis.get('contributor_count', 0)}")
        print(f"- 分析的文件数量: {len(analysis.get('file_histories', {}))}")

        # 保存结果到文件
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
    else:
        error = shared.get("history_analysis", {}).get("error", "未知错误")
        print(f"\n分析失败: {error}")


if __name__ == "__main__":
    main()
