"""环境变量管理模块，用于加载和管理环境变量和配置。"""

import os
from typing import Any, Dict, Optional

from dotenv import load_dotenv

from src.utils.config_loader import ConfigLoader
from src.utils.logger import log_and_notify

# 创建全局配置加载器实例
config_loader = ConfigLoader()


def load_env_vars(env_file: Optional[str] = None, env: str = "default") -> None:
    """加载环境变量和配置文件

    Args:
        env_file: .env 文件路径，如果为 None 则使用默认路径
        env: 环境名称，用于加载对应的配置文件
    """
    # 加载环境变量，强制覆盖已存在的环境变量
    if env_file and os.path.exists(env_file):
        load_dotenv(env_file, override=True)
        log_and_notify(f"已加载环境变量: {env_file}", "info")
    else:
        # 尝试从默认位置加载，强制覆盖已存在的环境变量
        load_dotenv(override=True)
        log_and_notify("已加载默认环境变量", "info")

    # 打印当前环境变量值，用于调试
    llm_model = os.getenv("LLM_MODEL")
    log_and_notify(f"当前环境变量: LLM_MODEL={llm_model}", "info")

    # 加载环境特定配置
    if env != "default":
        config_loader.load_env_config(env)
        log_and_notify(f"已加载环境配置: {env}", "info")


def get_llm_config() -> Dict[str, Any]:
    """获取 LLM 配置，优先使用环境变量中的值，如果环境变量中没有设置，则使用配置文件中的默认值

    Returns:
        LLM 配置字典
    """
    # 优先从环境变量获取配置，如果环境变量中没有设置，则使用配置文件中的默认值
    model = os.getenv("LLM_MODEL", config_loader.get("llm.model", "openai/gpt-4"))

    # 从模型字符串中提取提供商信息
    # 如果模型字符串包含 "/"，则第一部分为提供商
    if "/" in model:
        provider = model.split("/")[0]
    else:
        # 如果没有提供商信息，则使用默认值
        provider = config_loader.get("llm.provider", "openai")

    max_tokens_str = os.getenv("LLM_MAX_TOKENS")
    max_tokens = int(max_tokens_str) if max_tokens_str else config_loader.get("llm.max_tokens", 4000)
    # 只有在环境变量中明确设置了LLM_MAX_INPUT_TOKENS时才使用该值
    max_input_tokens_str = os.getenv("LLM_MAX_INPUT_TOKENS")
    max_input_tokens = int(max_input_tokens_str) if max_input_tokens_str else None
    temperature_str = os.getenv("LLM_TEMPERATURE")
    temperature = float(temperature_str) if temperature_str else config_loader.get("llm.temperature", 0.7)

    # 获取缓存配置
    cache_enabled_str = os.getenv("LLM_CACHE_ENABLED")
    cache_enabled = (
        cache_enabled_str.lower() == "true" if cache_enabled_str else config_loader.get("llm.cache_enabled", True)
    )

    cache_ttl_str = os.getenv("LLM_CACHE_TTL")
    cache_ttl = int(cache_ttl_str) if cache_ttl_str else config_loader.get("llm.cache_ttl", 86400)

    cache_dir = os.getenv("LLM_CACHE_DIR", config_loader.get("llm.cache_dir", ".cache/llm"))

    # 创建配置字典
    config = {
        "provider": provider,
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "api_key": os.getenv("LLM_API_KEY", ""),
        "cache": {"enabled": cache_enabled, "ttl": cache_ttl, "dir": cache_dir},
    }

    # 只有当max_input_tokens不为None时，才添加到配置中
    if max_input_tokens is not None:
        config["max_input_tokens"] = max_input_tokens

    # 打印当前使用的LLM配置（不包含敏感信息）
    print(
        f"当前LLM配置: 提供商={config['provider']}, 模型={config['model']}, 缓存={'启用' if cache_enabled else '禁用'}"
    )

    # 根据提供商加载特定配置
    # 只有当环境变量中明确设置了base_url时，才添加到配置中
    # litellm已经为各种提供商实现了默认的base_url

    # 处理OpenAI
    if config["provider"] == "openai":
        # 确保OPENAI_BASE_URL被正确处理
        openai_base_url = os.getenv("OPENAI_BASE_URL")
        if openai_base_url:
            config["base_url"] = openai_base_url
            print(f"设置OpenAI base_url: {openai_base_url}")

    # 处理OpenRouter
    elif config["provider"] == "openrouter":
        # 只有当环境变量中明确设置了base_url时，才添加到配置中
        if os.getenv("OPENROUTER_BASE_URL"):
            config["base_url"] = os.getenv("OPENROUTER_BASE_URL")

        # 添加OpenRouter特有的配置
        if os.getenv("OR_SITE_URL"):  # OpenRouter文档中使用OR_SITE_URL
            config["site_url"] = os.getenv("OR_SITE_URL")
        elif os.getenv("APP_URL"):  # 兼容旧版配置
            config["site_url"] = os.getenv("APP_URL")

        if os.getenv("OR_APP_NAME"):  # OpenRouter文档中使用OR_APP_NAME
            config["app_name"] = os.getenv("OR_APP_NAME")
        elif os.getenv("APP_NAME"):  # 兼容旧版配置
            config["app_name"] = os.getenv("APP_NAME")
        else:
            config["app_name"] = config_loader.get("llm.openrouter.app_name", "Codebase Knowledge Builder")

    # 处理阿里百炼
    elif config["provider"] in ["alibaba", "tongyi"]:
        if os.getenv("ALIBABA_BASE_URL"):
            config["base_url"] = os.getenv("ALIBABA_BASE_URL")

    # 处理火山引擎
    elif config["provider"] == "volcengine":
        if os.getenv("VOLCENGINE_BASE_URL"):
            config["base_url"] = os.getenv("VOLCENGINE_BASE_URL")

        # 添加火山引擎特有的配置
        if os.getenv("VOLCENGINE_SERVICE_ID"):
            config["service_id"] = os.getenv("VOLCENGINE_SERVICE_ID")
        else:
            config["service_id"] = config_loader.get("llm.volcengine.service_id", "")

    # 处理硅基流动
    elif config["provider"] == "moonshot":
        if os.getenv("MOONSHOT_BASE_URL"):
            config["base_url"] = os.getenv("MOONSHOT_BASE_URL")

    # 加载 Langfuse 配置
    langfuse_config = config_loader.get("langfuse", {})
    config["langfuse"] = {
        "enabled": langfuse_config.get("enabled", True),
        "host": langfuse_config.get("host", "https://cloud.langfuse.com"),
        "project_name": langfuse_config.get("project_name", "codebase-knowledge-builder"),
        # 敏感信息从环境变量获取
        "public_key": os.getenv("LANGFUSE_PUBLIC_KEY", ""),
        "secret_key": os.getenv("LANGFUSE_SECRET_KEY", ""),
    }

    # 如果环境变量中明确设置了这些值，则覆盖配置文件中的值
    if os.getenv("LANGFUSE_ENABLED"):
        config["langfuse"]["enabled"] = os.getenv("LANGFUSE_ENABLED", "").lower() == "true"
    if os.getenv("LANGFUSE_HOST"):
        config["langfuse"]["host"] = os.getenv("LANGFUSE_HOST")
    if os.getenv("LANGFUSE_PROJECT"):
        config["langfuse"]["project_name"] = os.getenv("LANGFUSE_PROJECT")

    return config


def get_node_config(node_name: str) -> Dict[str, Any]:
    """获取节点配置

    Args:
        node_name: 节点名称

    Returns:
        节点配置
    """
    node_config = config_loader.get_node_config(node_name)

    # 检查是否需要更新模型配置
    if "model" in node_config:
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
            provider = config_loader.get("llm.provider", "openai")
            return f"{provider}/{node_specific_model}"
        return node_specific_model

    # 其次检查全局 LLM 模型环境变量
    global_model = os.getenv("LLM_MODEL")
    if global_model:
        # 确保模型名称包含提供商前缀
        if "/" not in global_model:
            # 如果没有提供商前缀，使用默认提供商
            provider = config_loader.get("llm.provider", "openai")
            return f"{provider}/{global_model}"
        return global_model

    # 最后使用配置文件中的默认值
    # 如果默认模型是 "default-model"，则不添加提供商前缀
    if default_model == "default-model":
        return default_model

    # 确保默认模型名称包含提供商前缀
    if "/" not in default_model:
        # 如果没有提供商前缀，使用默认提供商
        provider = config_loader.get("llm.provider", "openai")
        # 对于 OpenAI 的 gpt 模型，不添加前缀
        if provider == "openai" and default_model.startswith("gpt-"):
            return default_model
        return f"{provider}/{default_model}"
    return default_model
