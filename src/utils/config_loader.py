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
        self.config: Dict[str, Any] = {}
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
        result = self.get(f"nodes.{node_name}", {})
        if not isinstance(result, dict):
            return {}
        return result

    def _set_llm_config(self, llm_config: Dict[str, Any]) -> None:
        """设置 LLM 配置

        Args:
            llm_config: LLM 配置字典
        """
        self.llm_config = llm_config


if __name__ == "__main__":
    # This main block is for demonstration and basic testing of ConfigLoader.
    # It assumes a 'config' directory sibling to the 'utils' directory if run directly,
    # or relative to the project root if the utils module is imported.
    # For robust testing, use a proper test framework and mock file system.

    # Create dummy logger for testing if real logger is complex to set up
    def print_logger(message: str, level: str = "info", notify: bool = False) -> None:
        """
        简单的日志打印函数，用于测试。

        Args:
            message: 日志消息
            level: 日志级别
            notify: 是否通知（在此函数中被忽略）

        Returns:
            None
        """
        # 记录未使用的参数，避免IDE警告
        _ = notify
        print(f"[{level.upper()}] {message}")

    # Replace log_and_notify with a simple print for this test block
    # This avoids issues with logger setup when running this file directly.
    original_log_and_notify = log_and_notify
    log_and_notify = print_logger

    print("--- ConfigLoader Test ---")
    test_config_dir = "./temp_test_config_dir"
    default_config_file = os.path.join(test_config_dir, "default.yml")
    dev_config_file = os.path.join(test_config_dir, "dev.yml")

    # Create temporary config directory and files
    os.makedirs(test_config_dir, exist_ok=True)
    with open(default_config_file, "w", encoding="utf-8") as f:
        yaml.dump(
            {
                "app": {"name": "DefaultApp", "version": "1.0"},
                "logging": {"level": "INFO"},
                "nodes": {"input": {"default_repo_url": "git@default.com:repo.git"}},
            },
            f,
        )

    with open(dev_config_file, "w", encoding="utf-8") as f:
        yaml.dump(
            {"app": {"name": "DevApp", "debug": True}, "logging": {"level": "DEBUG"}, "new_feature": {"enabled": True}},
            f,
        )

    print(f"\n1. Initializing ConfigLoader with dir: {test_config_dir}")
    loader = ConfigLoader(config_dir=test_config_dir)
    print("Initial config (after default.yml load):")
    print(yaml.dump(loader.get_config()))

    print("\n2. Testing get() method:")
    print(f"app.name: {loader.get('app.name')}")
    print(f"logging.level: {loader.get('logging.level')}")
    print(f"nodes.input.default_repo_url: {loader.get('nodes.input.default_repo_url')}")
    print(f"non_existent.key (with default): {loader.get('non_existent.key', 'fallback')}")

    print("\n3. Loading 'dev' environment config:")
    loader.load_env_config("dev")
    print("Config after dev.yml load (merged):")
    print(yaml.dump(loader.get_config()))

    print("\n4. Testing get() method after merge:")
    print(f"app.name (overridden): {loader.get('app.name')}")
    print(f"app.version (from default): {loader.get('app.version')}")
    print(f"app.debug (from dev): {loader.get('app.debug')}")
    print(f"logging.level (overridden): {loader.get('logging.level')}")
    print(f"new_feature.enabled (from dev): {loader.get('new_feature.enabled')}")

    print("\n5. Testing get_node_config():")
    input_node_cfg = loader.get_node_config("input")
    print("Input node config:")
    print(yaml.dump(input_node_cfg))

    print("\n6. Testing non-existent env config:")
    loader.load_env_config("prod")  # Assuming prod.yml doesn't exist

    # Clean up temporary directory and files
    try:
        os.remove(default_config_file)
        os.remove(dev_config_file)
        os.rmdir(test_config_dir)
        print("\nCleaned up temporary config files and directory.")
    except OSError as e:
        print(f"Error during cleanup: {e}")

    # Restore original logger if it was patched
    log_and_notify = original_log_and_notify
    print("--- ConfigLoader Test End ---")
