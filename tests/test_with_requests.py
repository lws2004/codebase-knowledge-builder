"""使用 requests 库测试 AnalyzeHistoryNode 节点。

这个脚本模拟了一个简单的 Git 仓库，并使用 AnalyzeHistoryNode 节点分析它。
"""

import json
import os
import shutil
import subprocess
import tempfile

import requests

from src.nodes import AnalyzeHistoryNode
from src.utils.env_manager import get_llm_config, load_env_vars


def create_test_repo():
    """创建一个测试 Git 仓库

    Returns:
        临时仓库路径
    """
    # 创建临时目录
    temp_dir = tempfile.mkdtemp(prefix="test_git_repo_")
    print(f"创建临时目录: {temp_dir}")

    try:
        # 初始化 Git 仓库
        subprocess.run(["git", "init"], cwd=temp_dir, check=True)

        # 创建一些文件
        for i in range(5):
            file_path = os.path.join(temp_dir, f"file{i}.txt")
            with open(file_path, "w") as f:
                f.write(f"This is test file {i}\n")

        # 添加并提交文件
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=temp_dir, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=temp_dir, check=True)
        subprocess.run(["git", "add", "."], cwd=temp_dir, check=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=temp_dir, check=True)

        # 修改一些文件并再次提交
        for i in range(3):
            file_path = os.path.join(temp_dir, f"file{i}.txt")
            with open(file_path, "a") as f:
                f.write(f"Added more content to file {i}\n")

        subprocess.run(["git", "add", "."], cwd=temp_dir, check=True)
        subprocess.run(["git", "commit", "-m", "Update files"], cwd=temp_dir, check=True)

        return temp_dir
    except Exception as e:
        print(f"创建测试仓库失败: {str(e)}")
        shutil.rmtree(temp_dir)
        return None


def test_with_real_repo(repo_url):
    """使用真实的 Git 仓库测试

    Args:
        repo_url: 仓库 URL
    """
    # 创建临时目录
    temp_dir = tempfile.mkdtemp(prefix="test_real_repo_")
    print(f"创建临时目录: {temp_dir}")

    try:
        # 克隆仓库
        print(f"克隆仓库: {repo_url}")
        subprocess.run(["git", "clone", repo_url, temp_dir], check=True)

        # 测试节点
        test_node(temp_dir)
    finally:
        # 清理临时目录
        print(f"清理临时目录: {temp_dir}")
        shutil.rmtree(temp_dir)


def test_node(repo_path):
    """测试 AnalyzeHistoryNode 节点

    Args:
        repo_path: 仓库路径
    """
    # 加载环境变量
    load_env_vars()

    # 获取 LLM 配置
    llm_config = get_llm_config()

    # 创建共享存储
    shared = {"repo_path": repo_path, "llm_config": llm_config}

    # 创建节点配置
    node_config = {"max_commits": 20, "include_file_history": True, "analyze_contributors": True}

    # 创建节点
    node = AnalyzeHistoryNode(config=node_config)

    # 运行节点
    print(f"开始分析仓库: {repo_path}")
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
        output_file = "history_analysis.json"
        with open(output_file, "w", encoding="utf-8") as f:
            # 移除过大的字段以减小文件大小
            output_analysis = analysis.copy()
            if "commit_history" in output_analysis:
                output_analysis["commit_history"] = output_analysis["commit_history"][:10]  # 只保留前 10 个提交

            json.dump(output_analysis, f, indent=2, ensure_ascii=False)

        print(f"\n结果已保存到: {output_file}")

        # 打印历史总结
        if "history_summary" in analysis and analysis["history_summary"]:
            print("\n历史总结:")
            print(analysis["history_summary"])
    else:
        error = shared.get("history_analysis", {}).get("error", "未知错误")
        print(f"\n分析失败: {error}")


def test_with_requests():
    """使用 requests 库测试 GitHub API

    这个函数模拟了一个使用 requests 库的测试，实际上并不调用 GitHub API。
    """
    print("使用 requests 库测试 GitHub API")

    # 模拟 GitHub API 请求
    api_url = "https://api.github.com/repos/octocat/Hello-World"

    try:
        # 发送请求
        response = requests.get(api_url)
        response.raise_for_status()

        # 解析响应
        repo_data = response.json()

        print("仓库信息:")
        print(f"- 名称: {repo_data.get('name')}")
        print(f"- 描述: {repo_data.get('description')}")
        print(f"- 星标数: {repo_data.get('stargazers_count')}")
        print(f"- Fork 数: {repo_data.get('forks_count')}")

        # 使用断言而不是返回值
        assert repo_data.get("name") is not None, "仓库名称不应为空"
    except requests.RequestException as e:
        print(f"请求失败: {str(e)}")
        assert False, f"请求失败: {str(e)}"


def main():
    """主函数"""
    print("开始测试 AnalyzeHistoryNode 节点")

    # 测试 requests 库
    try:
        test_with_requests()
        print("requests 库测试成功")
    except Exception as e:
        print(f"requests 库测试失败，请检查网络连接: {str(e)}")
        return

    # 创建测试仓库
    repo_path = create_test_repo()
    if not repo_path:
        print("创建测试仓库失败")
        return

    try:
        # 测试节点
        test_node(repo_path)
    finally:
        # 清理测试仓库
        print(f"清理测试仓库: {repo_path}")
        shutil.rmtree(repo_path)

    print("\n测试完成")


if __name__ == "__main__":
    main()
