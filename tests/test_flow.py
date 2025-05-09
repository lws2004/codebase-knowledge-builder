"""测试完整流程的脚本。"""

import argparse
import json

from pocketflow import Flow, Node

from src.nodes import AsyncAnalyzeHistoryNode
from src.utils.env_manager import get_llm_config, load_env_vars
from src.utils.git_utils import GitRepoManager


class InputNode(Node):
    """输入节点，用于获取用户输入"""

    def exec(self, _):
        """执行阶段，获取用户输入

        Args:
            _: 无用参数

        Returns:
            用户输入
        """
        # 这里可以从命令行参数获取输入
        return {
            "repo_url": "https://github.com/octocat/Hello-World.git",
            "local_path": None,
            "branch": "master",  # 注意：octocat/Hello-World 的默认分支是 master
        }

    def post(self, shared, prep_res, exec_res):
        """后处理阶段，将用户输入存储到共享存储中

        Args:
            shared: 共享存储
            prep_res: 准备阶段的结果
            exec_res: 执行阶段的结果

        Returns:
            下一个节点的动作
        """
        shared["input"] = exec_res
        return "default"


class PrepareRepoNode(Node):
    """准备仓库节点，用于克隆和准备 Git 仓库"""

    def prep(self, shared):
        """准备阶段，从共享存储中获取用户输入

        Args:
            shared: 共享存储

        Returns:
            用户输入
        """
        return shared.get("input", {})

    def exec(self, prep_res):
        """执行阶段，克隆和准备 Git 仓库

        Args:
            prep_res: 准备阶段的结果

        Returns:
            仓库信息
        """
        repo_url = prep_res.get("repo_url")
        local_path = prep_res.get("local_path")
        branch = prep_res.get("branch", "main")

        if not repo_url:
            return {"error": "缺少仓库 URL", "success": False}

        # 创建 Git 仓库管理器
        repo_manager = GitRepoManager(repo_url, local_path, branch)

        # 克隆仓库
        if not repo_manager.clone():
            return {"error": "克隆仓库失败", "success": False}

        # 检出指定分支
        if branch != "main" and not repo_manager.checkout(branch):
            return {"error": f"检出分支 {branch} 失败", "success": False}

        return {"repo_path": repo_manager.local_path, "branch": branch, "success": True}

    def post(self, shared, prep_res, exec_res):
        """后处理阶段，将仓库信息存储到共享存储中

        Args:
            shared: 共享存储
            prep_res: 准备阶段的结果
            exec_res: 执行阶段的结果

        Returns:
            下一个节点的动作
        """
        if not exec_res.get("success", False):
            shared["error"] = exec_res.get("error", "准备仓库失败")
            return "error"

        shared["repo_path"] = exec_res["repo_path"]
        shared["branch"] = exec_res["branch"]
        return "default"


def create_flow():
    """创建流程

    Returns:
        流程
    """
    # 创建节点
    input_node = InputNode()
    prepare_repo_node = PrepareRepoNode()
    analyze_history_node = AsyncAnalyzeHistoryNode()

    # 连接节点
    input_node >> prepare_repo_node >> analyze_history_node

    # 创建流程
    return Flow(start=input_node)


def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="测试完整流程")
    parser.add_argument(
        "--repo-url", type=str, default="https://github.com/octocat/Hello-World.git", help="Git 仓库 URL"
    )
    parser.add_argument("--branch", type=str, default="master", help="分支名称")
    parser.add_argument("--output", type=str, default="flow_result.json", help="输出文件路径")
    args = parser.parse_args()

    # 加载环境变量
    load_env_vars()

    # 获取 LLM 配置
    llm_config = get_llm_config()

    # 创建共享存储
    shared = {"llm_config": llm_config}

    # 创建流程
    flow = create_flow()

    # 运行流程
    print(f"开始运行流程，仓库: {args.repo_url}, 分支: {args.branch}")
    flow.run(shared)

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
    elif "error" in shared:
        print(f"\n流程失败: {shared['error']}")
    else:
        print("\n流程完成，但没有生成历史分析结果")


if __name__ == "__main__":
    main()
