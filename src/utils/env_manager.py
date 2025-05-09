"""环境变量管理模块，用于加载和管理环境变量和配置。"""

import os
from typing import Any, Dict, Optional, cast

from dotenv import load_dotenv

from src.utils.config_loader import ConfigLoader
from src.utils.logger import log_and_notify

# --- Constants for Environment Variables and Config Keys ---
# LLM Generic
LLM_PROVIDER_ENV = "LLM_PROVIDER"
LLM_MODEL_ENV = "LLM_MODEL"
LLM_API_KEY_ENV = "LLM_API_KEY"
LLM_MAX_TOKENS_ENV = "LLM_MAX_TOKENS"
LLM_MAX_INPUT_TOKENS_ENV = "LLM_MAX_INPUT_TOKENS"
LLM_TEMPERATURE_ENV = "LLM_TEMPERATURE"
LLM_CACHE_ENABLED_ENV = "LLM_CACHE_ENABLED"
LLM_CACHE_TTL_ENV = "LLM_CACHE_TTL"
LLM_CACHE_DIR_ENV = "LLM_CACHE_DIR"

LLM_PROVIDER_CONFIG = "llm.provider"
LLM_MODEL_CONFIG = "llm.model"
LLM_MAX_TOKENS_CONFIG = "llm.max_tokens"
LLM_TEMPERATURE_CONFIG = "llm.temperature"
LLM_CACHE_ENABLED_CONFIG = "llm.cache_enabled"
LLM_CACHE_TTL_CONFIG = "llm.cache_ttl"
LLM_CACHE_DIR_CONFIG = "llm.cache_dir"

# OpenAI Specific
OPENAI_BASE_URL_ENV = "OPENAI_BASE_URL"

# OpenRouter Specific
OPENROUTER_BASE_URL_ENV = "OPENROUTER_BASE_URL"
OR_SITE_URL_ENV = "OR_SITE_URL"
OR_APP_NAME_ENV = "OR_APP_NAME"
# Compatibility for OpenRouter
APP_URL_ENV_COMPAT = "APP_URL"
APP_NAME_ENV_COMPAT = "APP_NAME"
OPENROUTER_APP_NAME_CONFIG = "llm.openrouter.app_name"

# Alibaba Specific
ALIBABA_BASE_URL_ENV = "ALIBABA_BASE_URL"

# Volcengine Specific
VOLCENGINE_BASE_URL_ENV = "VOLCENGINE_BASE_URL"
VOLCENGINE_SERVICE_ID_ENV = "VOLCENGINE_SERVICE_ID"
VOLCENGINE_SERVICE_ID_CONFIG = "llm.volcengine.service_id"

# Moonshot Specific
MOONSHOT_BASE_URL_ENV = "MOONSHOT_BASE_URL"

# Langfuse Specific
LANGFUSE_ENABLED_ENV = "LANGFUSE_ENABLED"
LANGFUSE_HOST_ENV = "LANGFUSE_HOST"
LANGFUSE_PROJECT_ENV = "LANGFUSE_PROJECT"
LANGFUSE_PUBLIC_KEY_ENV = "LANGFUSE_PUBLIC_KEY"
LANGFUSE_SECRET_KEY_ENV = "LANGFUSE_SECRET_KEY"

LANGFUSE_CONFIG = "langfuse"
LANGFUSE_ENABLED_CONFIG = "enabled"
LANGFUSE_HOST_CONFIG = "host"
LANGFUSE_PROJECT_NAME_CONFIG = "project_name"
# --- End Constants ---

# 创建全局配置加载器实例
config_loader_instance = ConfigLoader()


def load_env_vars(env_file: Optional[str] = None, env: str = "default") -> None:
    """加载环境变量和配置文件

    Args:
        env_file: .env 文件路径，如果为 None 则使用默认路径
        env: 环境名称，用于加载对应的配置文件
    """
    if env_file and os.path.exists(env_file):
        load_dotenv(env_file, override=True)
        log_and_notify(f"已加载环境变量: {env_file}", "info")
    else:
        loaded_default = load_dotenv(override=True)
        if loaded_default:
            log_and_notify("已加载默认 .env 文件中的环境变量", "info")
        else:
            log_and_notify("未找到 .env 文件，使用现有环境变量", "info")

    llm_model_env_val = os.getenv(LLM_MODEL_ENV)
    log_and_notify(f"环境变量检查: {LLM_MODEL_ENV}={llm_model_env_val}", "debug")

    if env != "default":
        config_loader_instance.load_env_config(env)


def get_llm_config() -> Dict[str, Any]:
    """获取 LLM 配置，优先使用环境变量中的值，如果环境变量中没有设置，则使用配置文件中的默认值

    Returns:
        LLM 配置字典
    """
    config = _get_base_llm_config(config_loader_instance)  # type: ignore[arg-type]
    _apply_provider_specific_config(config, config_loader_instance)  # type: ignore[arg-type]
    config[LANGFUSE_CONFIG] = _get_langfuse_config(config_loader_instance)  # type: ignore[arg-type]

    log_and_notify(
        f"最终LLM配置: Provider={config.get('provider')}, Model={config.get('model')}, "
        f"CacheEnabled={config.get('cache', {}).get('enabled')}, "
        f"LangfuseEnabled={config.get(LANGFUSE_CONFIG, {}).get('enabled')}",
        "info",
    )
    if config.get("base_url"):
        log_and_notify(f"LLM Base URL: {config['base_url']}", "debug")
    return config


def get_node_config(node_name: str) -> Dict[str, Any]:
    """获取节点配置

    Args:
        node_name: 节点名称

    Returns:
        节点配置
    """
    node_config = config_loader_instance.get_node_config(node_name)

    # 确保node_config是字典
    if node_config is None:
        node_config = {}

    # 检查是否需要更新模型配置
    if isinstance(node_config, dict) and "model" in node_config:
        node_config["model"] = get_node_model_config(node_name, node_config["model"])

    return node_config


def get_node_model_config(node_name: str, default_model: str) -> str:
    """获取节点的模型配置，优先级：

    1. 节点特定的环境变量（例如 LLM_MODEL_GENERATE_OVERALL_ARCHITECTURE）
    2. 全局 LLM 模型环境变量（LLM_MODEL）
    3. 配置文件中的默认值

    Args:
        node_name: 节点名称
        default_model: 配置文件中的默认模型

    Returns:
        模型名称，格式为 "provider/model"
    """
    # 将节点名称转换为环境变量格式（小写转大写，下划线分隔）
    env_var_name = f"LLM_MODEL_{node_name.upper()}"

    # 首先检查节点特定的环境变量
    node_specific_model = os.getenv(env_var_name)
    if node_specific_model:
        # 确保模型名称包含提供商前缀
        if "/" not in node_specific_model:
            # 如果没有提供商前缀，使用默认提供商
            provider = config_loader_instance.get("llm.provider", "openai")
            return f"{provider}/{node_specific_model}"
        return node_specific_model

    # 其次检查全局 LLM 模型环境变量
    global_model = os.getenv("LLM_MODEL")
    if global_model:
        # 确保模型名称包含提供商前缀
        if "/" not in global_model:
            # 如果没有提供商前缀，使用默认提供商
            provider = config_loader_instance.get("llm.provider", "openai")
            return f"{provider}/{global_model}"
        return global_model

    # 最后使用配置文件中的默认值
    # 如果默认模型是 "default-model"，则不添加提供商前缀
    if default_model == "default-model":
        return default_model

    # 确保默认模型名称包含提供商前缀
    if "/" not in default_model:
        # 如果没有提供商前缀，使用默认提供商
        provider = config_loader_instance.get("llm.provider", "openai")
        # 对于 OpenAI 的 gpt 模型，不添加前缀
        if provider == "openai" and default_model.startswith("gpt-"):
            return default_model
        return f"{provider}/{default_model}"
    return default_model


def _get_base_llm_config(loader: ConfigLoader) -> Dict[str, Any]:
    """Gets the foundational LLM settings (model, provider, tokens, temp, cache)."""
    model = os.getenv(LLM_MODEL_ENV, loader.get(LLM_MODEL_CONFIG, "openai/gpt-4"))
    provider = os.getenv(LLM_PROVIDER_ENV)  # Provider primarily from env or inferred from model
    if not provider:
        if "/" in model:
            provider = model.split("/")[0]
        else:
            provider = loader.get(LLM_PROVIDER_CONFIG, "openai")

    max_tokens_str = os.getenv(LLM_MAX_TOKENS_ENV)
    max_tokens = int(max_tokens_str) if max_tokens_str else loader.get(LLM_MAX_TOKENS_CONFIG, 4000)

    max_input_tokens_str = os.getenv(LLM_MAX_INPUT_TOKENS_ENV)
    max_input_tokens = int(max_input_tokens_str) if max_input_tokens_str else None

    temperature_str = os.getenv(LLM_TEMPERATURE_ENV)
    temperature = float(temperature_str) if temperature_str else loader.get(LLM_TEMPERATURE_CONFIG, 0.7)

    cache_enabled_str = os.getenv(LLM_CACHE_ENABLED_ENV)
    cache_enabled = (
        cache_enabled_str.lower() == "true" if cache_enabled_str else loader.get(LLM_CACHE_ENABLED_CONFIG, True)
    )
    cache_ttl_str = os.getenv(LLM_CACHE_TTL_ENV)
    cache_ttl = int(cache_ttl_str) if cache_ttl_str else loader.get(LLM_CACHE_TTL_CONFIG, 86400)
    cache_dir = os.getenv(LLM_CACHE_DIR_ENV, loader.get(LLM_CACHE_DIR_CONFIG, ".cache/llm"))

    config = {
        "provider": provider,
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "api_key": os.getenv(LLM_API_KEY_ENV, ""),
        "cache": {"enabled": cache_enabled, "ttl": cache_ttl, "dir": cache_dir},
    }
    if max_input_tokens is not None:
        config["max_input_tokens"] = max_input_tokens
    return config


def _apply_provider_specific_config(config: Dict[str, Any], loader: ConfigLoader) -> None:
    """Applies provider-specific settings (base_url, etc.) to the config dict."""
    provider = config.get("provider")

    if provider == "openai":
        base_url = os.getenv(OPENAI_BASE_URL_ENV)
        if base_url:
            config["base_url"] = base_url
    elif provider == "openrouter":
        base_url = os.getenv(OPENROUTER_BASE_URL_ENV)
        if base_url:
            config["base_url"] = base_url
        config["site_url"] = os.getenv(OR_SITE_URL_ENV, os.getenv(APP_URL_ENV_COMPAT))
        config["app_name"] = os.getenv(
            OR_APP_NAME_ENV,
            os.getenv(APP_NAME_ENV_COMPAT, loader.get(OPENROUTER_APP_NAME_CONFIG, "Codebase Knowledge Builder")),
        )
    elif provider in ["alibaba", "tongyi"]:
        base_url = os.getenv(ALIBABA_BASE_URL_ENV)
        if base_url:
            config["base_url"] = base_url
    elif provider == "volcengine":
        base_url = os.getenv(VOLCENGINE_BASE_URL_ENV)
        if base_url:
            config["base_url"] = base_url
        config["service_id"] = os.getenv(VOLCENGINE_SERVICE_ID_ENV, loader.get(VOLCENGINE_SERVICE_ID_CONFIG, ""))
    elif provider == "moonshot":
        base_url = os.getenv(MOONSHOT_BASE_URL_ENV)
        if base_url:
            config["base_url"] = base_url


def _get_langfuse_config(loader: ConfigLoader) -> Dict[str, Any]:
    """Gets Langfuse configuration."""
    langfuse_cfg_from_file = loader.get(LANGFUSE_CONFIG, {})
    enabled_from_env = os.getenv(LANGFUSE_ENABLED_ENV)

    return {
        "enabled": enabled_from_env.lower() == "true"
        if enabled_from_env
        else langfuse_cfg_from_file.get(LANGFUSE_ENABLED_CONFIG, True),
        "host": os.getenv(
            LANGFUSE_HOST_ENV, langfuse_cfg_from_file.get(LANGFUSE_HOST_CONFIG, "https://cloud.langfuse.com")
        ),
        "project_name": os.getenv(
            LANGFUSE_PROJECT_ENV, langfuse_cfg_from_file.get(LANGFUSE_PROJECT_NAME_CONFIG, "codebase-knowledge-builder")
        ),
        "public_key": os.getenv(LANGFUSE_PUBLIC_KEY_ENV, ""),
        "secret_key": os.getenv(LANGFUSE_SECRET_KEY_ENV, ""),
    }


if __name__ == "__main__":
    # Simple test for env_manager functions
    # For more thorough testing, mock os.getenv and config_loader

    def print_logger_for_test(message: str, level: str = "info", notify: bool = False) -> None:
        """测试用的简单日志打印函数。"""
        # 记录未使用的参数，避免IDE警告
        _ = notify
        print(f"[ENV_MGR_TEST][{level.upper()}] {message}")

    original_log_and_notify = log_and_notify
    log_and_notify = print_logger_for_test

    # Test load_env_vars (assuming a .env file might exist or not)
    print("\n--- Testing load_env_vars ---")
    # load_env_vars(env="test_env") # Creates a new ConfigLoader internally if not careful
    # The global config_loader_instance is used by get_llm_config
    # Temporarily disable direct call to load_env_vars in test to avoid real file ops / global state meddling
    # Instead, we will mock the config_loader_instance directly.
    print_logger_for_test("Skipping direct load_env_vars call in test, will mock ConfigLoader.", "debug")

    # To test get_llm_config effectively, we might need to set some env vars
    print("\n--- Testing get_llm_config (with potential mocks needed for full test) ---")
    # Example: Temporarily set some env vars for testing this run
    os.environ[LLM_MODEL_ENV] = "test_provider/test_model_from_env"
    os.environ[LLM_API_KEY_ENV] = "test_api_key_from_env"
    os.environ[OPENAI_BASE_URL_ENV] = "https://custom.openai.com/v1"
    os.environ[LANGFUSE_ENABLED_ENV] = "false"

    # Ensure the global config_loader_instance has some mock data for testing
    # This is a bit hacky for a simple __main__ test; proper mocks are better.
    class MockConfigLoader(ConfigLoader):
        """用于测试 env_manager 的 Mock 配置加载器。"""

        def __init__(self) -> None:
            """初始化 MockConfigLoader。"""
            super().__init__(config_dir="mock_config")  # Call super with a dummy dir
            self.mock_data = {
                LLM_MODEL_CONFIG: "openai/gpt-3.5-turbo-default",
                LLM_PROVIDER_CONFIG: "openai",
                LANGFUSE_CONFIG: {LANGFUSE_ENABLED_CONFIG: True, LANGFUSE_HOST_CONFIG: "https://config.langfuse.com"},
            }
            print_logger_for_test("MockConfigLoader initialized", "debug")

        def get(self, key: str, default: Any = None) -> Any:  # Add type hints
            """模拟 get 方法。"""
            return self.mock_data.get(key, default)

        def get_node_config(self, node_name: str) -> Dict[str, Any]:
            """模拟 get_node_config 方法。"""
            # Cast the result of self.get which returns Any
            return cast(Dict[str, Any], self.get(f"nodes.{node_name}", {}))

        def load_env_config(self, env: str) -> None:  # Add type hints
            """模拟 load_env_config 方法。"""
            print_logger_for_test(f"MockConfigLoader: load_env_config({env}) called", "debug")
            # In a real mock, you might update self.mock_data based on 'env'

    original_config_loader = config_loader_instance
    config_loader_instance = MockConfigLoader()  # Now this assignment should be fine

    llm_conf = get_llm_config()
    print_logger_for_test(f"Fetched LLM Config: {llm_conf}", "info")

    # Test get_node_model_config
    print("\n--- Testing get_node_model_config ---")
    # Clear specific model env vars for a clean test
    if "LLM_MODEL_NODE_A" in os.environ:
        del os.environ["LLM_MODEL_NODE_A"]
    if "LLM_MODEL_NODE_B" in os.environ:
        del os.environ["LLM_MODEL_NODE_B"]
    if "LLM_MODEL_NODE_C" in os.environ:
        del os.environ["LLM_MODEL_NODE_C"]

    # Case 1: Global LLM_MODEL_ENV is set (test_provider/test_model_from_env)
    model_a_conf = get_node_model_config("node_a", "config_provider/model_a_default")
    print_logger_for_test(f"Node A model (global env): {model_a_conf}", "info")
    assert model_a_conf == "test_provider/test_model_from_env"

    # Case 2: Node-specific env var overrides global
    os.environ["LLM_MODEL_NODE_B"] = "nodespec_provider/nodespec_model_b"
    model_b_conf = get_node_model_config("node_b", "config_provider/model_b_default")
    print_logger_for_test(f"Node B model (node env): {model_b_conf}", "info")
    assert model_b_conf == "nodespec_provider/nodespec_model_b"

    # Case 3: No relevant env vars, uses config default
    if LLM_MODEL_ENV in os.environ:
        del os.environ[LLM_MODEL_ENV]  # Unset global for this case
    if "LLM_MODEL_NODE_B" in os.environ:
        del os.environ["LLM_MODEL_NODE_B"]  # Unset node-specific for this case
    model_c_conf = get_node_model_config("node_c", "config_provider/model_c_default")
    print_logger_for_test(f"Node C model (config default): {model_c_conf}", "info")
    assert model_c_conf == "config_provider/model_c_default"

    # Case 4: Config default needs provider prefix
    # Ensure global LLM_PROVIDER_ENV is not set, so it falls back to config_loader_instance.get(LLM_PROVIDER_CONFIG)
    if LLM_PROVIDER_ENV in os.environ:
        del os.environ[LLM_PROVIDER_ENV]
    model_d_conf = get_node_model_config("node_d", "model_d_no_prefix")
    print_logger_for_test(f"Node D model (config default, needs prefix): {model_d_conf}", "info")
    # This assertion depends on MockConfigLoader providing LLM_PROVIDER_CONFIG = "openai"
    assert model_d_conf == "openai/model_d_no_prefix"

    # Case 5: OpenAI gpt- model from config (should not add openai/ prefix again)
    os.environ[LLM_PROVIDER_ENV] = "openai"
    model_e_conf = get_node_model_config("node_e", "gpt-4-turbo")
    print_logger_for_test(f"Node E model (OpenAI gpt- special case): {model_e_conf}", "info")
    assert model_e_conf == "gpt-4-turbo"

    # Clean up environment variables set for testing
    # Check existence before deleting to avoid KeyError if already deleted by a test case
    # For LLM_MODEL_ENV, specifically check if it was set by this test block before deleting.
    # This avoids accidentally deleting a pre-existing LLM_MODEL_ENV if Case 3 didn't run or ran differently.
    # A more robust cleanup might involve storing initial values and restoring them.
    if (
        os.getenv(LLM_MODEL_ENV) == "test_provider/test_model_from_env"
        or LLM_MODEL_ENV not in os.environ
        and "test_provider/test_model_from_env" == "test_provider/test_model_from_env"
    ):  # check if it was set by this test or unset by case 3
        if LLM_MODEL_ENV in os.environ:
            del os.environ[LLM_MODEL_ENV]

    if LLM_API_KEY_ENV in os.environ:
        del os.environ[LLM_API_KEY_ENV]
    if OPENAI_BASE_URL_ENV in os.environ:
        del os.environ[OPENAI_BASE_URL_ENV]
    if LANGFUSE_ENABLED_ENV in os.environ:
        del os.environ[LANGFUSE_ENABLED_ENV]
    if "LLM_MODEL_NODE_B" in os.environ:
        del os.environ["LLM_MODEL_NODE_B"]
    if LLM_PROVIDER_ENV in os.environ and os.getenv(LLM_PROVIDER_ENV) == "openai":
        del os.environ[LLM_PROVIDER_ENV]

    # Restore original patched objects
    log_and_notify = original_log_and_notify
    config_loader_instance = original_config_loader
    print("\n--- Env Manager Test End ---")
