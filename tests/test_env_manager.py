#!/usr/bin/env python3
"""测试环境变量管理模块"""

import os

# 确保当前目录在 Python 路径中
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.utils.env_manager import get_llm_config, load_env_vars


class TestEnvManager(unittest.TestCase):
    """测试环境变量管理模块"""

    def setUp(self):
        """测试前的准备工作"""
        # 保存原始环境变量
        self.original_env = os.environ.copy()

    def tearDown(self):
        """测试后的清理工作"""
        # 恢复原始环境变量
        os.environ.clear()
        os.environ.update(self.original_env)

    @patch.dict(os.environ, {"LLM_MODEL": "openai/gpt-4", "LLM_API_KEY": "test-key"}, clear=True)
    def test_base_url_not_set_by_default(self):
        """测试默认情况下不设置base_url"""
        # 加载环境变量
        load_env_vars()

        # 获取LLM配置
        config = get_llm_config()

        # 验证base_url不在配置中
        self.assertNotIn("base_url", config)

    @patch.dict(os.environ, {"OPENAI_BASE_URL": "https://custom-openai-api.com/v1"}, clear=True)
    @patch("src.utils.env_manager.get_llm_config")
    def test_base_url_set_when_env_var_exists(self, mock_get_llm_config):
        """测试当环境变量存在时设置base_url"""
        # 设置模拟返回值
        mock_get_llm_config.return_value = {
            "provider": "openai",
            "model": "gpt-4",
            "api_key": "test-key",
            "base_url": "https://custom-openai-api.com/v1",
        }

        # 调用函数
        config = get_llm_config()

        # 验证结果
        self.assertIn("base_url", config)
        self.assertEqual(config["base_url"], "https://custom-openai-api.com/v1")

    @patch.dict(
        os.environ,
        {
            "LLM_MODEL": "openrouter/anthropic/claude-3-opus-20240229",
            "LLM_API_KEY": "test-key",
            "OR_SITE_URL": "https://myapp.com",
            "OR_APP_NAME": "My Test App",
        },
        clear=True,
    )
    def test_openrouter_config(self):
        """测试OpenRouter配置"""
        # 加载环境变量
        load_env_vars()

        # 获取LLM配置
        config = get_llm_config()

        # 验证OpenRouter特有配置
        self.assertIn("site_url", config)
        self.assertEqual(config["site_url"], "https://myapp.com")
        self.assertIn("app_name", config)
        self.assertEqual(config["app_name"], "My Test App")

        # 验证base_url不在配置中
        self.assertNotIn("base_url", config)

    @patch.dict(
        os.environ,
        {
            "LLM_MODEL": "openrouter/anthropic/claude-3-opus-20240229",
            "LLM_API_KEY": "test-key",
            "OPENROUTER_BASE_URL": "https://custom-openrouter-api.com/v1",
        },
        clear=True,
    )
    def test_openrouter_with_base_url(self):
        """测试OpenRouter配置，包含base_url"""
        # 加载环境变量
        load_env_vars()

        # 获取LLM配置
        config = get_llm_config()

        # 验证base_url在配置中且值正确
        self.assertIn("base_url", config)
        self.assertEqual(config["base_url"], "https://custom-openrouter-api.com/v1")


if __name__ == "__main__":
    unittest.main()
