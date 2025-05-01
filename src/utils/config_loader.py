"""配置加载器，用于从 YAML 文件加载配置。"""
import os
from typing import Any, Dict

import yaml

from ..utils.logger import log_and_notify


class ConfigLoader:
    """配置加载器，用于从 YAML 文件加载配置"""

    def __init__(self, config_dir: str = "config"):
        """初始化配置加载器

        Args:
            config_dir: 配置文件目录
        """
        self.config_dir = config_dir
        self.config = {}
        self.load_default_config()

    def load_default_config(self) -> None:
        """加载默认配置"""
        default_config_path = os.path.join(self.config_dir, "default.yml")
        if os.path.exists(default_config_path):
            try:
                with open(default_config_path, "r", encoding="utf-8") as f:
                    self.config = yaml.safe_load(f) or {}
                log_and_notify(f"已加载默认配置: {default_config_path}", "info")
            except Exception as e:
                log_and_notify(f"加载默认配置失败: {str(e)}", "error")
        else:
            log_and_notify(f"默认配置文件不存在: {default_config_path}", "warning")

    def load_env_config(self, env: str) -> None:
        """加载环境特定配置

        Args:
            env: 环境名称
        """
        env_config_path = os.path.join(self.config_dir, f"{env}.yml")
        if os.path.exists(env_config_path):
            try:
                with open(env_config_path, "r", encoding="utf-8") as f:
                    env_config = yaml.safe_load(f) or {}

                # 递归合并配置
                self._merge_config(self.config, env_config)
                log_and_notify(f"已加载环境配置: {env_config_path}", "info")
            except Exception as e:
                log_and_notify(f"加载环境配置失败: {str(e)}", "error")
        else:
            log_and_notify(f"环境配置文件不存在: {env_config_path}", "warning")

    def _merge_config(self, base: Dict[str, Any], override: Dict[str, Any]) -> None:
        """递归合并配置

        Args:
            base: 基础配置
            override: 覆盖配置
        """
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value

    def get_config(self) -> Dict[str, Any]:
        """获取完整配置

        Returns:
            完整配置
        """
        return self.config

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项

        Args:
            key: 配置项键，支持点号分隔的路径，如 "app.debug"
            default: 默认值

        Returns:
            配置项值
        """
        keys = key.split(".")
        value = self.config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def get_node_config(self, node_name: str) -> Dict[str, Any]:
        """获取节点配置

        Args:
            node_name: 节点名称

        Returns:
            节点配置
        """
        return self.get(f"nodes.{node_name}", {})
