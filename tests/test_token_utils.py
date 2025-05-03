#!/usr/bin/env python3
"""测试Token工具模块"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.utils.llm_wrapper.token_utils import (
    count_message_tokens,
    count_tokens,
    truncate_messages_if_needed,
    truncate_non_system_messages,
)


class TestTokenUtils(unittest.TestCase):
    """测试Token工具模块"""

    @patch("litellm.completion")
    def test_count_tokens(self, mock_completion):
        """测试token计数功能"""
        # 设置模拟响应
        mock_response = MagicMock()
        mock_response.usage.prompt_tokens = 4  # 设置为固定值
        mock_completion.return_value = mock_response

        # 测试正常情况
        result = count_tokens("测试文本", "openai/gpt-4")
        self.assertEqual(result, 4)
        mock_completion.assert_called_once()

        # 测试异常情况 - 模拟litellm抛出异常
        mock_completion.reset_mock()
        mock_completion.side_effect = Exception("测试异常")

        # 跳过tiktoken测试，因为它依赖于实际的tiktoken库
        # 我们只测试正常情况下的litellm调用
        self.assertTrue(1 <= count_tokens("This is a test", "gpt-4") <= 10)

    @patch("litellm.completion")
    def test_count_message_tokens(self, mock_completion):
        """测试消息token计数功能"""
        # 设置模拟响应
        mock_response = MagicMock()
        mock_response.usage.prompt_tokens = 14  # 设置为固定值
        mock_completion.return_value = mock_response

        # 测试正常情况
        messages = [{"role": "system", "content": "你是助手"}, {"role": "user", "content": "你好"}]
        result = count_message_tokens(messages, "openai/gpt-4")
        self.assertEqual(result, 14)
        mock_completion.assert_called_once()

        # 测试异常情况 - 模拟litellm抛出异常
        mock_completion.reset_mock()
        mock_completion.side_effect = Exception("测试异常")

        # 跳过tiktoken测试，因为它依赖于实际的tiktoken库
        # 我们只测试正常情况下的litellm调用
        messages = [{"role": "system", "content": "You are an assistant"}, {"role": "user", "content": "Hello"}]
        self.assertTrue(5 <= count_message_tokens(messages, "gpt-4") <= 30)

    @patch("src.utils.llm_wrapper.token_utils.count_message_tokens")
    def test_truncate_messages_if_needed_no_truncation(self, mock_count_message_tokens):
        """测试不需要截断的情况"""
        # 设置模拟返回值
        mock_count_message_tokens.return_value = 15

        # 测试不需要截断的情况
        messages = [{"role": "system", "content": "你是助手"}, {"role": "user", "content": "你好"}]
        result = truncate_messages_if_needed(messages, 100, "openai/gpt-4")
        self.assertEqual(result, messages)

    @patch("src.utils.llm_wrapper.token_utils.count_message_tokens")
    @patch("src.utils.llm_wrapper.token_utils.truncate_non_system_messages")
    def test_truncate_messages_if_needed_no_system(self, mock_truncate_non_system, mock_count_message_tokens):
        """测试无系统消息的截断"""
        # 设置模拟返回值
        mock_count_message_tokens.return_value = 50
        mock_truncate_non_system.return_value = ["truncated_message"]

        # 测试无系统消息的截断
        messages = [
            {"role": "user", "content": "第一条消息"},
            {"role": "assistant", "content": "第二条消息"},
        ]
        result = truncate_messages_if_needed(messages, 30, "openai/gpt-4")
        self.assertEqual(result, ["truncated_message"])
        mock_truncate_non_system.assert_called_once()

    @patch("src.utils.llm_wrapper.token_utils.count_message_tokens")
    @patch("src.utils.llm_wrapper.token_utils.truncate_non_system_messages")
    def test_truncate_messages_if_needed_with_system(self, mock_truncate_non_system, mock_count_message_tokens):
        """测试有系统消息的截断"""

        # 设置模拟返回值
        def count_tokens_side_effect(msgs, _):  # 使用下划线表示未使用的参数
            if len(msgs) == 3:  # 全部消息
                return 50
            elif len(msgs) == 1:  # 系统消息
                if msgs[0]["role"] == "system":
                    return 10
                return 5
            return 0

        mock_count_message_tokens.side_effect = count_tokens_side_effect
        mock_truncate_non_system.return_value = ["truncated_message"]

        # 测试有系统消息的截断
        messages = [
            {"role": "system", "content": "你是助手"},
            {"role": "user", "content": "用户消息"},
            {"role": "assistant", "content": "助手消息"},
        ]
        result = truncate_messages_if_needed(messages, 30, "openai/gpt-4")
        # 结果应该是系统消息加上截断后的非系统消息
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], messages[0])  # 系统消息保持不变
        self.assertEqual(result[1], "truncated_message")  # 非系统消息被截断

    @patch("src.utils.llm_wrapper.token_utils.count_message_tokens")
    def test_truncate_non_system_messages(self, mock_count_message_tokens):
        """测试截断非系统消息"""

        # 设置模拟返回值
        def count_tokens_side_effect(msgs, _):  # 使用下划线表示未使用的参数
            if len(msgs) == 1:
                return 10
            return 0

        mock_count_message_tokens.side_effect = count_tokens_side_effect

        # 测试截断非系统消息
        messages = [
            {"role": "user", "content": "第一条消息"},
            {"role": "assistant", "content": "第二条消息"},
            {"role": "user", "content": "第三条消息"},
        ]
        result = truncate_non_system_messages(messages, 25, "openai/gpt-4")
        # 应该保留最新的两条消息
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], messages[1])
        self.assertEqual(result[1], messages[2])

    @patch("src.utils.llm_wrapper.token_utils.count_message_tokens")
    def test_truncate_non_system_messages_single_message(self, mock_count_message_tokens):
        """测试单条消息超过限制的情况"""
        # 设置模拟返回值
        mock_count_message_tokens.return_value = 50

        # 创建模拟的split_text_func
        split_text_func = MagicMock()
        split_text_func.return_value = ["截断后的内容"]

        # 测试单条消息超过限制的情况
        messages = [{"role": "user", "content": "这是一条很长的消息" * 10}]
        result = truncate_non_system_messages(messages, 30, "openai/gpt-4", split_text_func)
        # 应该调用split_text_func截断消息
        split_text_func.assert_called_once()
        # 结果应该包含一条截断后的消息
        self.assertEqual(len(result), 1)
        self.assertIn("截断后的内容", result[0]["content"])
        self.assertIn("[内容已截断]", result[0]["content"])


if __name__ == "__main__":
    unittest.main()
