#!/usr/bin/env python3
"""测试 LLM 调用的脚本"""

import asyncio
import os
import sys
import unittest
from unittest.mock import patch

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.utils.env_manager import load_env_vars
from src.utils.llm_wrapper.llm_client import LLMClient


class TestLLMCall(unittest.TestCase):
    """测试 LLM 调用"""

    def setUp(self):
        """测试前的准备工作"""
        # 保存原始环境变量
        self.original_env = os.environ.copy()
        # 加载环境变量
        load_env_vars()
        # 设置测试环境变量
        os.environ["LLM_PROVIDER"] = "openai"
        os.environ["LLM_MODEL"] = "gpt-3.5-turbo"
        os.environ["OPENAI_API_KEY"] = "sk-mock-api-key"

    def tearDown(self):
        """测试后的清理工作"""
        # 恢复原始环境变量
        os.environ.clear()
        os.environ.update(self.original_env)

    @patch("litellm.completion")
    @patch("src.utils.llm_wrapper.token_utils.count_message_tokens")
    def test_completion(self, mock_count_tokens, mock_completion):
        """测试同步 LLM 调用"""
        # 设置模拟响应
        mock_response = {
            "choices": [{"message": {"content": "这是一个测试响应"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }

        # 设置token计数的模拟返回值，避免调用litellm.completion
        mock_count_tokens.return_value = 20

        # 重置mock以清除之前的调用
        mock_completion.reset_mock()
        mock_completion.return_value = mock_response

        # 创建 LLM 客户端
        client = LLMClient(
            {
                "provider": os.environ.get("LLM_PROVIDER"),
                "model": os.environ.get("LLM_MODEL"),
                "temperature": 0.7,
                "max_tokens": 1000,
                "max_input_tokens": 4000,
            }
        )

        # 测试消息
        messages = [
            {"role": "system", "content": "你是一个有用的助手。"},
            {"role": "user", "content": "你好，请简要介绍一下 Python 语言。"},
        ]

        # 调用 LLM
        response = client.completion(messages=messages)

        # 验证结果
        self.assertEqual(response, mock_response)
        self.assertEqual(client.get_completion_content(response), "这是一个测试响应")

        # 验证调用参数 - 使用call_count而不是assert_called_once
        self.assertEqual(mock_completion.call_count, 1, "completion应该只被调用一次")
        _, kwargs = mock_completion.call_args

        # 获取实际传递的模型名称
        actual_model = kwargs["model"]
        # 如果是 OpenAI 的 gpt 模型，可能会有 openai/ 前缀，需要处理
        if actual_model.startswith("openai/gpt-"):
            actual_model = actual_model.replace("openai/", "")

        self.assertEqual(actual_model, "gpt-3.5-turbo")
        self.assertEqual(kwargs["messages"], messages)
        self.assertEqual(kwargs["temperature"], 0.7)
        self.assertEqual(kwargs["max_tokens"], 1000)

    @patch("litellm.acompletion")
    @patch("src.utils.llm_wrapper.token_utils.count_message_tokens")
    def test_acompletion(self, mock_count_tokens, mock_acompletion):
        """测试异步 LLM 调用"""
        # 设置模拟响应
        mock_response = {
            "choices": [{"message": {"content": "这是一个异步测试响应"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }

        # 设置token计数的模拟返回值，避免调用litellm.completion
        mock_count_tokens.return_value = 20

        # 设置模拟函数返回值
        async def mock_async_response(*args, **kwargs):  # pylint: disable=unused-argument
            return mock_response

        # 重置mock以清除之前的调用
        mock_acompletion.reset_mock()
        mock_acompletion.side_effect = mock_async_response

        # 创建 LLM 客户端
        client = LLMClient(
            {
                "provider": os.environ.get("LLM_PROVIDER"),
                "model": os.environ.get("LLM_MODEL"),
                "temperature": 0.7,
                "max_tokens": 1000,
                "max_input_tokens": 4000,
            }
        )

        # 测试消息
        messages = [
            {"role": "system", "content": "你是一个有用的助手。"},
            {"role": "user", "content": "你好，请简要介绍一下 Python 语言。"},
        ]

        # 调用异步 LLM
        async def run_test():
            response = await client.acompletion(messages=messages)
            return response

        response = asyncio.run(run_test())

        # 验证结果
        self.assertEqual(response, mock_response)
        self.assertEqual(client.get_completion_content(response), "这是一个异步测试响应")

        # 验证调用参数 - 使用call_count而不是assert_called_once
        self.assertEqual(mock_acompletion.call_count, 1, "acompletion应该只被调用一次")
        _, kwargs = mock_acompletion.call_args

        # 获取实际传递的模型名称
        actual_model = kwargs["model"]
        # 如果是 OpenAI 的 gpt 模型，可能会有 openai/ 前缀，需要处理
        if actual_model.startswith("openai/gpt-"):
            actual_model = actual_model.replace("openai/", "")

        self.assertEqual(actual_model, "gpt-3.5-turbo")
        self.assertEqual(kwargs["messages"], messages)
        self.assertEqual(kwargs["temperature"], 0.7)
        self.assertEqual(kwargs["max_tokens"], 1000)


if __name__ == "__main__":
    unittest.main()
