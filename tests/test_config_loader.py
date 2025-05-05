"""测试配置加载器模块"""

import os
import sys
from unittest.mock import mock_open, patch

# 确保当前目录在 Python 路径中
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.utils.config_loader import ConfigLoader


class TestConfigLoader:
    """测试配置加载器类"""

    def setup_method(self):
        """每个测试方法前的准备工作"""
        # 创建配置加载器实例
        self.config_loader = ConfigLoader()

    def test_get_config(self):
        """测试获取完整配置"""
        # 获取完整配置
        config = self.config_loader.get_config()

        # 验证配置是否包含基本项
        assert "app" in config
        assert "llm" in config
        assert "nodes" in config

    def test_get_specific_config(self):
        """测试获取特定配置项"""
        # 获取特定配置项
        app_name = self.config_loader.get("app.name")
        llm_max_tokens = self.config_loader.get("llm.max_tokens")
        llm_model = self.config_loader.get("llm.model")

        # 验证配置项是否存在
        assert app_name is not None
        assert llm_max_tokens is not None
        assert llm_model is not None

    def test_get_default_value(self):
        """测试获取不存在的配置项时返回默认值"""
        # 获取不存在的配置项
        default_value = "默认值"
        result = self.config_loader.get("not.exist", default_value)

        # 验证返回默认值
        assert result == default_value

    def test_get_node_config(self):
        """测试获取节点配置"""
        # 获取节点配置
        node_config = self.config_loader.get_node_config("analyze_history")

        # 验证节点配置是否存在
        assert node_config is not None
        assert isinstance(node_config, dict)

    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open, read_data='{"test": {"key": "value"}}')
    def test_load_env_config(self, mock_file, mock_exists):
        """测试加载环境配置"""
        # 模拟文件存在
        mock_exists.return_value = True

        # 加载环境配置
        self.config_loader.load_env_config("test")

        # 验证文件是否被打开
        mock_file.assert_called_once()

        # 验证配置是否被加载
        assert self.config_loader.get("test.key") == "value"
