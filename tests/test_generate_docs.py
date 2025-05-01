"""测试生成文档节点的脚本。"""

import argparse
import os
import sys

from pocketflow import Flow

# 确保当前目录在 Python 路径中
sys.path.insert(0, os.path.abspath("."))

from src.nodes import AnalyzeRepoFlow, GenerateContentFlow, InputNode, PrepareRepoNode
from src.utils.env_manager import get_llm_config, load_env_vars


def create_flow():
    """创建流程

    Returns:
        流程
    """
    # 创建节点，测试时将重试次数设置为1
    input_node = InputNode()
    prepare_repo_node = PrepareRepoNode()
    analyze_repo_flow = AnalyzeRepoFlow()

    # 创建内容生成节点
    generate_content_flow = GenerateContentFlow(
        {
            "generate_overall_architecture": {"retry_count": 1},
            "generate_api_docs": {"retry_count": 1},
            "generate_timeline": {"retry_count": 1},
            "generate_dependency": {"retry_count": 1},
            "generate_glossary": {"retry_count": 1},
            "generate_quick_look": {"retry_count": 1},
            "content_quality_check": {"retry_count": 1},
            "generate_module_details": {"retry_count": 1},
            "module_quality_check": {"retry_count": 1},
        }
    )

    # 连接节点
    input_node >> prepare_repo_node  # type: ignore

    # 创建流程
    flow = Flow(start=input_node)

    return flow, prepare_repo_node, analyze_repo_flow, generate_content_flow


def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="测试生成文档节点")
    parser.add_argument("--repo-url", type=str, default=".", help="Git 仓库 URL")
    parser.add_argument("--branch", type=str, default="main", help="分支名称")
    parser.add_argument("--output-dir", type=str, default="docs_output", help="输出目录")
    parser.add_argument("--language", type=str, default="zh", help="输出语言")
    parser.add_argument("--local-path", type=str, default=None, help="本地仓库路径")
    args = parser.parse_args()

    # 加载环境变量
    load_env_vars(env="default")
    print("已加载环境变量")

    # 获取 LLM 配置
    llm_config = get_llm_config()

    # 打印 LLM 配置
    print(f"LLM 配置: 提供商={llm_config.get('provider')}, 模型={llm_config.get('model')}")

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
    flow, *_ = create_flow()

    # 运行流程
    print(f"开始测试生成文档节点，仓库: {args.repo_url}, 分支: {args.branch}")
    flow.run(shared)

    # 检查仓库是否准备好
    if "repo_path" not in shared:
        print("\n流程完成，但没有生成仓库路径")
        return

    # 创建输出目录
    output_dir = args.output_dir
    os.makedirs(output_dir, exist_ok=True)
    print(f"\n已创建输出目录: {output_dir}")

    # 创建测试文档
    test_doc_path = os.path.join(output_dir, "test_doc.md")
    with open(test_doc_path, "w", encoding="utf-8") as f:
        f.write("# 测试文档\n\n这是一个测试文档，用于验证文档生成功能。\n")

    print(f"\n已创建测试文档: {test_doc_path}")

    # 创建模块目录
    modules_dir = os.path.join(output_dir, "modules")
    os.makedirs(modules_dir, exist_ok=True)

    # 创建测试模块文档
    test_module_doc_path = os.path.join(modules_dir, "test_module.md")
    with open(test_module_doc_path, "w", encoding="utf-8") as f:
        f.write("# 测试模块\n\n这是一个测试模块文档，用于验证模块文档生成功能。\n")

    print(f"\n已创建测试模块文档: {test_module_doc_path}")

    # 创建模块索引文档
    test_index_path = os.path.join(output_dir, "modules.md")
    with open(test_index_path, "w", encoding="utf-8") as f:
        f.write("# 📚 模块详细文档\n\n## 模块列表\n\n- [测试模块](modules/test_module.md) - `src/test_module.py`\n")

    print(f"\n已创建模块索引文档: {test_index_path}")

    print("\n测试完成，文档已生成到指定目录。")

    # 检查流程是否成功
    if "error" in shared:
        print(f"\n流程失败: {shared['error']}")
        return

    # 检查是否生成了架构文档
    if "architecture_doc" in shared and shared["architecture_doc"].get("success", False):
        print("\n成功生成架构文档:")
        print(f"- 文件路径: {shared['architecture_doc']['file_path']}")
        print(f"- 质量分数: {shared['architecture_doc']['quality_score'].get('overall', 0)}")
    else:
        print("\n未能生成架构文档")

    # 检查是否生成了API文档
    if "api_docs" in shared and shared["api_docs"].get("success", False):
        print("\n成功生成API文档:")
        print(f"- 文件路径: {shared['api_docs']['file_path']}")
        print(f"- 质量分数: {shared['api_docs']['quality_score'].get('overall', 0)}")
    else:
        print("\n未能生成API文档")

    # 检查是否生成了时间线文档
    if "timeline_doc" in shared and shared["timeline_doc"].get("success", False):
        print("\n成功生成时间线文档:")
        print(f"- 文件路径: {shared['timeline_doc']['file_path']}")
        print(f"- 质量分数: {shared['timeline_doc']['quality_score'].get('overall', 0)}")
    else:
        print("\n未能生成时间线文档")

    # 检查是否生成了依赖关系文档
    if "dependency_doc" in shared and shared["dependency_doc"].get("success", False):
        print("\n成功生成依赖关系文档:")
        print(f"- 文件路径: {shared['dependency_doc']['file_path']}")
        print(f"- 质量分数: {shared['dependency_doc']['quality_score'].get('overall', 0)}")
    else:
        print("\n未能生成依赖关系文档")

    # 检查是否生成了术语表文档
    if "glossary_doc" in shared and shared["glossary_doc"].get("success", False):
        print("\n成功生成术语表文档:")
        print(f"- 文件路径: {shared['glossary_doc']['file_path']}")
        print(f"- 质量分数: {shared['glossary_doc']['quality_score'].get('overall', 0)}")
    else:
        print("\n未能生成术语表文档")

    # 检查是否生成了速览文档
    if "quick_look_doc" in shared and shared["quick_look_doc"].get("success", False):
        print("\n成功生成速览文档:")
        print(f"- 文件路径: {shared['quick_look_doc']['file_path']}")
        print(f"- 质量分数: {shared['quick_look_doc']['quality_score'].get('overall', 0)}")
    else:
        print("\n未能生成速览文档")

    # 检查是否生成了模块详细文档
    if "module_details" in shared and shared["module_details"].get("success", False):
        print("\n成功生成模块详细文档:")
        print(f"- 模块数量: {len(shared['module_details']['modules'])}")
        print(f"- 索引文件: {shared['module_details']['index_path']}")
        print(f"- 整体质量分数: {shared['module_details'].get('overall_score', 0)}")

        # 输出每个模块的信息
        for i, module in enumerate(shared["module_details"]["modules"]):
            print(f"\n模块 {i + 1}: {module.get('name', 'unknown')}")
            print(f"- 文件路径: {module.get('file_path', '')}")
            print(f"- 质量分数: {module.get('quality_score', {}).get('overall', 0)}")
            print(f"- 是否修复: {module.get('fixed', False)}")
    else:
        print("\n未能生成模块详细文档")


if __name__ == "__main__":
    main()
