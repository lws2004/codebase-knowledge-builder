#!/usr/bin/env python3
"""测试LiteLLM日志配置的脚本"""

import os
import sys
import unittest

# 确保当前目录在 Python 路径中
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.utils.env_manager import get_llm_config, load_env_vars
from src.utils.llm_wrapper.llm_client import LLMClient
from src.utils.logging_config import configure_logging


class TestLiteLLMLogging(unittest.TestCase):
    """测试LiteLLM日志配置"""

    def setUp(self):
        """测试前的准备工作"""
        # 保存原始环境变量
        self.original_env = os.environ.copy()
        # 加载环境变量
        load_env_vars()
        # 配置日志
        self.logger = configure_logging()

    def tearDown(self):
        """测试后的清理工作"""
        # 恢复原始环境变量
        os.environ.clear()
        os.environ.update(self.original_env)

    def test_litellm_logging(self):
        """测试LiteLLM日志配置"""
        # 获取LLM配置
        llm_config = get_llm_config()

        # 创建LLM客户端
        client = LLMClient(llm_config)

        # 测试一个简单的LLM调用
        messages = [{"role": "user", "content": "你好，这是一个测试。"}]
        response = client.completion(messages=messages, max_tokens=10)

        # 获取响应内容
        content = client.get_completion_content(response)

        # 验证响应不为空
        self.assertIsNotNone(content)
        self.assertNotEqual(content, "")


if __name__ == "__main__":
    unittest.main()
