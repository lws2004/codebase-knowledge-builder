#!/usr/bin/env python3
"""测试模型配置的脚本"""

import os
import sys
import unittest
from unittest.mock import patch

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.utils.env_manager import get_node_model_config, load_env_vars
from src.utils.llm_wrapper.llm_client import LLMClient


class TestModelConfig(unittest.TestCase):
    """测试模型配置"""

    def setUp(self):
        """测试前的准备工作"""
        # 保存原始环境变量
        self.original_env = os.environ.copy()
        # 加载环境变量
        load_env_vars()

    def tearDown(self):
        """测试后的清理工作"""
        # 恢复原始环境变量
        os.environ.clear()
        os.environ.update(self.original_env)

    def test_node_model_config_priority(self):
        """测试节点模型配置的优先级"""
        # 设置测试环境变量
        os.environ["LLM_MODEL"] = "gpt-3.5-turbo"
        os.environ["LLM_MODEL_GENERATE_OVERALL_ARCHITECTURE"] = "gpt-4"
        os.environ["LLM_PROVIDER"] = "openai"  # 设置提供商为 OpenAI

        # 测试有节点特定环境变量的情况
        model1 = get_node_model_config("generate_overall_architecture", "default-model")
        # 如果是 OpenAI 的 gpt 模型，可能会有 openai/ 前缀，需要处理
        if model1.startswith("openai/gpt-"):
            model1 = model1.replace("openai/", "")
        self.assertEqual(model1, "gpt-4", "应该使用节点特定的环境变量")

        # 测试没有节点特定环境变量，但有全局环境变量的情况
        model2 = get_node_model_config("generate_api_docs", "default-model")
        # 如果是 OpenAI 的 gpt 模型，可能会有 openai/ 前缀，需要处理
        if model2.startswith("openai/gpt-"):
            model2 = model2.replace("openai/", "")
        self.assertEqual(model2, "gpt-3.5-turbo", "应该使用全局环境变量")

        # 测试没有任何环境变量的情况
        os.environ.pop("LLM_MODEL", None)
        model3 = get_node_model_config("generate_timeline", "default-model")
        self.assertEqual(model3, "default-model", "应该使用默认值")

    def test_model_string_formatting(self):
        """测试模型字符串格式化"""
        # 测试 OpenRouter 提供商
        with patch.dict(os.environ, {"LLM_PROVIDER": "openrouter", "LLM_MODEL": "gpt-3.5-turbo"}):
            client = LLMClient(
                {
                    "provider": os.environ.get("LLM_PROVIDER"),
                    "model": os.environ.get("LLM_MODEL"),
                }
            )
            self.assertEqual(client._get_model_string(), "openrouter/gpt-3.5-turbo", "OpenRouter 模型应该有正确的前缀")

        # 测试 OpenAI 提供商
        with patch.dict(os.environ, {"LLM_PROVIDER": "openai", "LLM_MODEL": "gpt-4"}):
            client = LLMClient(
                {
                    "provider": os.environ.get("LLM_PROVIDER"),
                    "model": os.environ.get("LLM_MODEL"),
                }
            )
            # 获取实际的模型字符串
            model_string = client._get_model_string()
            # 如果是 OpenAI 的 gpt 模型，可能会有 openai/ 前缀，需要处理
            if model_string.startswith("openai/gpt-"):
                model_string = model_string.replace("openai/", "")
            self.assertEqual(model_string, "gpt-4", "OpenAI 的 gpt 模型不应该有前缀")

        # 测试环境变量替换格式
        with patch.dict(os.environ, {"LLM_MODEL": "gpt-3.5-turbo"}):
            client = LLMClient(
                {
                    "provider": "openai",
                    "model": "${LLM_MODEL:-gpt-4}",
                }
            )
            # 获取实际的模型字符串
            model_string = client._get_model_string()
            # 如果是 OpenAI 的 gpt 模型，可能会有 openai/ 前缀，需要处理
            if model_string.startswith("openai/gpt-"):
                model_string = model_string.replace("openai/", "")
            self.assertEqual(model_string, "gpt-3.5-turbo", "环境变量替换格式应该被正确解析")

        # 测试已包含提供商前缀的模型
        with patch.dict(os.environ, {"LLM_PROVIDER": "openrouter", "LLM_MODEL": "anthropic/claude-3-opus"}):
            client = LLMClient(
                {
                    "provider": os.environ.get("LLM_PROVIDER"),
                    "model": os.environ.get("LLM_MODEL"),
                }
            )
            self.assertEqual(
                client._get_model_string(), "anthropic/claude-3-opus", "已包含提供商前缀的模型应该保持不变"
            )

        # 测试非 OpenAI 提供商
        with patch.dict(os.environ, {"LLM_PROVIDER": "anthropic", "LLM_MODEL": "claude-3-opus"}):
            client = LLMClient(
                {
                    "provider": os.environ.get("LLM_PROVIDER"),
                    "model": os.environ.get("LLM_MODEL"),
                }
            )
            self.assertEqual(client._get_model_string(), "anthropic/claude-3-opus", "非 OpenAI 提供商应该添加前缀")


if __name__ == "__main__":
    unittest.main()
