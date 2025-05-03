#!/usr/bin/env python3
"""测试环境变量管理模块（直接方法）"""

import os

# 确保当前目录在 Python 路径中
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.utils.env_manager import get_llm_config


class TestEnvManagerDirect(unittest.TestCase):
    """测试环境变量管理模块（直接方法）"""

    def setUp(self):
        """测试前的准备工作"""
        # 保存原始环境变量
        self.original_env = os.environ.copy()

    def tearDown(self):
        """测试后的清理工作"""
        # 恢复原始环境变量
        os.environ.clear()
        os.environ.update(self.original_env)

    def test_base_url_not_set_by_default(self):
        """测试默认情况下不设置base_url"""
        # 清除所有环境变量
        for key in list(os.environ.keys()):
            if key.startswith("LLM_") or key.startswith("OPENAI_") or key.startswith("OPENROUTER_"):
                del os.environ[key]

        # 设置测试环境变量
        os.environ["LLM_PROVIDER"] = "openai"
        os.environ["LLM_MODEL"] = "gpt-4"
        os.environ["LLM_API_KEY"] = "test-key"

        # 获取LLM配置
        config = get_llm_config()

        # 验证base_url不在配置中
        self.assertNotIn("base_url", config)

    def test_base_url_set_when_env_var_exists(self):
        """测试当环境变量存在时设置base_url"""
        # 清除所有环境变量
        for key in list(os.environ.keys()):
            if key.startswith("LLM_") or key.startswith("OPENAI_") or key.startswith("OPENROUTER_"):
                del os.environ[key]

        # 设置测试环境变量
        os.environ["LLM_PROVIDER"] = "openai"
        os.environ["LLM_MODEL"] = "gpt-4"
        os.environ["LLM_API_KEY"] = "test-key"
        os.environ["OPENAI_BASE_URL"] = "https://custom-openai-api.com/v1"

        # 获取LLM配置
        config = get_llm_config()

        # 验证base_url在配置中且值正确
        self.assertIn("base_url", config)
        self.assertEqual(config["base_url"], "https://custom-openai-api.com/v1")

    def test_openrouter_config(self):
        """测试OpenRouter配置"""
        # 清除所有环境变量
        for key in list(os.environ.keys()):
            if (
                key.startswith("LLM_")
                or key.startswith("OPENAI_")
                or key.startswith("OPENROUTER_")
                or key.startswith("OR_")
                or key.startswith("APP_")
            ):
                del os.environ[key]

        # 设置测试环境变量
        os.environ["LLM_PROVIDER"] = "openrouter"
        os.environ["LLM_MODEL"] = "qwen/qwen3-30b-a3b:free"
        os.environ["LLM_API_KEY"] = "test-key"
        os.environ["OR_SITE_URL"] = "https://myapp.com"
        os.environ["OR_APP_NAME"] = "My Test App"

        # 获取LLM配置
        config = get_llm_config()

        # 验证OpenRouter特有配置
        self.assertIn("site_url", config)
        self.assertEqual(config["site_url"], "https://myapp.com")
        self.assertIn("app_name", config)
        self.assertEqual(config["app_name"], "My Test App")

        # 验证base_url不在配置中
        self.assertNotIn("base_url", config)

    def test_openrouter_with_base_url(self):
        """测试OpenRouter配置，包含base_url"""
        # 清除所有环境变量
        for key in list(os.environ.keys()):
            if (
                key.startswith("LLM_")
                or key.startswith("OPENAI_")
                or key.startswith("OPENROUTER_")
                or key.startswith("OR_")
                or key.startswith("APP_")
            ):
                del os.environ[key]

        # 设置测试环境变量
        os.environ["LLM_PROVIDER"] = "openrouter"
        os.environ["LLM_MODEL"] = "qwen/qwen3-30b-a3b:free"
        os.environ["LLM_API_KEY"] = "test-key"
        os.environ["OPENROUTER_BASE_URL"] = "https://custom-openrouter-api.com/v1"

        # 获取LLM配置
        config = get_llm_config()

        # 验证base_url在配置中且值正确
        self.assertIn("base_url", config)
        self.assertEqual(config["base_url"], "https://custom-openrouter-api.com/v1")


if __name__ == "__main__":
    unittest.main()
