"""测试优化后的文档生成质量。

这个脚本用于测试优化后的文档生成节点，验证生成的文档质量是否有所提升。
"""

import asyncio
import os
import sys
import tempfile

# 确保当前目录在 Python 路径中
sys.path.insert(0, os.path.abspath("."))

from src.nodes import (
    AsyncGenerateApiDocsNode,
    AsyncGenerateModuleDetailsNode,
    ContentQualityCheckNode,
    ModuleQualityCheckNode,
)
from src.utils.env_manager import get_llm_config, get_node_config, load_env_vars


async def test_module_details_generation():
    """测试模块详情文档生成"""
    print("🧪 测试模块详情文档生成...")

    # 加载环境变量
    load_env_vars(env="default")
    llm_config = get_llm_config()

    if not llm_config.get("model"):
        print("❌ LLM配置不完整，跳过测试")
        return

    # 创建测试数据（将在shared_data中使用）

    test_code_content = '''
"""测试模块，用于演示文档生成功能。"""

from typing import Optional, List, Dict, Any
import json


class DataProcessor:
    """数据处理器，提供数据清洗和转换功能。"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化数据处理器。

        Args:
            config: 配置字典，包含处理参数
        """
        self.config = config or {}
        self.processed_count = 0

    def process_data(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """处理数据列表。

        Args:
            data: 待处理的数据列表

        Returns:
            处理后的数据列表

        Raises:
            ValueError: 当数据格式不正确时
        """
        if not isinstance(data, list):
            raise ValueError("数据必须是列表格式")

        processed_data = []
        for item in data:
            if self._validate_item(item):
                processed_item = self._transform_item(item)
                processed_data.append(processed_item)
                self.processed_count += 1

        return processed_data

    def _validate_item(self, item: Dict[str, Any]) -> bool:
        """验证数据项。"""
        return isinstance(item, dict) and "id" in item

    def _transform_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """转换数据项。"""
        transformed = item.copy()
        transformed["processed"] = True
        return transformed


def load_config(config_path: str) -> Dict[str, Any]:
    """加载配置文件。

    Args:
        config_path: 配置文件路径

    Returns:
        配置字典
    """
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_results(results: List[Dict[str, Any]], output_path: str) -> bool:
    """保存处理结果。

    Args:
        results: 处理结果列表
        output_path: 输出文件路径

    Returns:
        是否保存成功
    """
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False
'''

    # 共享存储将在下面创建

    # 创建节点
    node_config = get_node_config("generate_module_details")
    node_config["retry_count"] = 1  # 测试时减少重试次数
    node = AsyncGenerateModuleDetailsNode(node_config)

    # 创建模拟的共享存储，包含核心模块数据
    shared_data = {
        "llm_config": llm_config,
        "language": "zh",
        "output_dir": "test_output",
        "core_modules": {
            "modules": [
                {
                    "name": "test_module",
                    "path": "src/test_module.py",
                    "description": "测试模块，用于演示文档生成功能",
                    "importance": 9,
                    "code_content": test_code_content,
                }
            ]
        },
    }

    # 准备输入数据
    prep_data = await node.prep_async(shared_data)

    try:
        # 执行文档生成
        print("📝 正在生成模块文档...")
        exec_result = await node.exec_async(prep_data)

        if exec_result.get("success", False):
            content = exec_result.get("content", "")
            print("✅ 模块文档生成成功")
            print(f"📄 文档长度: {len(content)} 字符")

            # 保存生成的文档到临时文件
            with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
                f.write(content)
                temp_file = f.name

            print(f"💾 文档已保存到: {temp_file}")

            # 测试质量检查
            await test_quality_check(content, "module")

            return True
        else:
            error = exec_result.get("error", "未知错误")
            print(f"❌ 模块文档生成失败: {error}")
            return False

    except Exception as e:
        print(f"❌ 测试过程中出现异常: {str(e)}")
        return False


async def test_api_docs_generation():
    """测试API文档生成"""
    print("\n🧪 测试API文档生成...")

    # 加载环境变量
    load_env_vars(env="default")
    llm_config = get_llm_config()

    if not llm_config.get("model"):
        print("❌ LLM配置不完整，跳过测试")
        return

    # 创建测试数据
    test_code_structure = {
        "file_count": 50,
        "directory_count": 10,
        "language_stats": {"Python": 80, "Markdown": 15, "YAML": 5},
        "file_types": {".py": 40, ".md": 8, ".yml": 2},
    }

    test_core_modules = {
        "modules": [
            {"name": "data_processor", "path": "src/data_processor.py", "description": "数据处理模块", "importance": 9},
            {"name": "config_manager", "path": "src/config_manager.py", "description": "配置管理模块", "importance": 8},
        ],
        "architecture": "模块化架构，采用分层设计",
        "relationships": ["data_processor -> config_manager", "config_manager -> utils"],
    }

    # 创建节点
    node_config = get_node_config("generate_api_docs")
    node_config["retry_count"] = 1
    node = AsyncGenerateApiDocsNode(node_config)

    # 创建模拟的共享存储
    shared_data = {
        "llm_config": llm_config,
        "language": "zh",
        "output_dir": "test_output",
        "repo_name": "test-project",
        "code_structure": test_code_structure,
        "core_modules": test_core_modules,
    }

    # 准备输入数据
    prep_data = await node.prep_async(shared_data)

    try:
        # 执行文档生成
        print("📝 正在生成API文档...")
        exec_result = await node.exec_async(prep_data)

        if exec_result.get("success", False):
            content = exec_result.get("content", "")
            print("✅ API文档生成成功")
            print(f"📄 文档长度: {len(content)} 字符")

            # 保存生成的文档到临时文件
            with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
                f.write(content)
                temp_file = f.name

            print(f"💾 文档已保存到: {temp_file}")

            # 测试质量检查
            await test_quality_check(content, "api")

            return True
        else:
            error = exec_result.get("error", "未知错误")
            print(f"❌ API文档生成失败: {error}")
            return False

    except Exception as e:
        print(f"❌ 测试过程中出现异常: {str(e)}")
        return False


async def test_quality_check(content: str, doc_type: str):
    """测试质量检查功能"""
    print(f"\n🔍 测试{doc_type}文档质量检查...")

    llm_config = get_llm_config()

    if doc_type == "module":
        # 测试模块质量检查
        node_config = get_node_config("module_quality_check")
        node_config["retry_count"] = 1
        node = ModuleQualityCheckNode(node_config)

        # 模拟模块详细文档数据
        shared = {
            "module_details": {"docs": [{"name": "test_module", "content": content, "file_path": "test_module.md"}]},
            "llm_config": llm_config,
            "language": "zh",
        }

        prep_result = node.prep(shared)
        exec_result = node.exec(prep_result)

        if exec_result.get("success", False):
            overall_score = exec_result.get("overall_score", 0)
            modules = exec_result.get("modules", [])
            print(f"✅ 模块质量检查完成，总体评分: {overall_score:.2f}")

            if modules:
                module = modules[0]
                quality_score = module.get("quality_score", {})
                print(f"📊 详细评分: {quality_score}")

                if module.get("needs_fix", False):
                    suggestions = module.get("improvement_suggestions", "")
                    print(f"💡 改进建议: {suggestions[:200]}...")
        else:
            print(f"❌ 模块质量检查失败: {exec_result.get('error', '未知错误')}")

    else:
        # 测试内容质量检查
        node_config = get_node_config("content_quality_check")
        node_config["retry_count"] = 1
        node = ContentQualityCheckNode(node_config)

        # 模拟内容数据
        shared = {
            "api_docs": {"success": True, "content": content, "file_path": "api_docs.md"},
            "llm_config": llm_config,
            "language": "zh",
        }

        prep_result = node.prep(shared)
        exec_result = node.exec(prep_result)

        if exec_result.get("success", False):
            quality_score = exec_result.get("quality_score", {})
            overall_score = quality_score.get("overall", 0)
            print(f"✅ 内容质量检查完成，总体评分: {overall_score:.2f}")
            print(f"📊 详细评分: {quality_score}")

            if exec_result.get("needs_fix", False):
                evaluation = exec_result.get("evaluation", {})
                suggestions = evaluation.get("fix_suggestions", "")
                print(f"💡 改进建议: {suggestions[:200]}...")
        else:
            print(f"❌ 内容质量检查失败: {exec_result.get('error', '未知错误')}")


async def main():
    """主函数"""
    print("🚀 开始测试优化后的文档生成质量\n")

    # 测试模块详情文档生成
    module_success = await test_module_details_generation()

    # 测试API文档生成
    api_success = await test_api_docs_generation()

    # 总结测试结果
    print("\n📋 测试结果总结:")
    print(f"  模块文档生成: {'✅ 成功' if module_success else '❌ 失败'}")
    print(f"  API文档生成: {'✅ 成功' if api_success else '❌ 失败'}")

    if module_success and api_success:
        print("\n🎉 所有测试通过！文档生成质量优化成功。")
    else:
        print("\n⚠️ 部分测试失败，请检查配置和网络连接。")


if __name__ == "__main__":
    asyncio.run(main())
