"""
环境变量管理模块，用于加载和管理环境变量和配置。
"""
import os
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from .config_loader import ConfigLoader
from ..utils.logger import log_and_notify

# 创建全局配置加载器实例
config_loader = ConfigLoader()

def load_env_vars(env_file: Optional[str] = None, env: str = "default") -> None:
    """加载环境变量和配置文件

    Args:
        env_file: .env 文件路径，如果为 None 则使用默认路径
        env: 环境名称，用于加载对应的配置文件
    """
    # 加载环境变量
    if env_file and os.path.exists(env_file):
        load_dotenv(env_file)
        log_and_notify(f"已加载环境变量: {env_file}", "info")
    else:
        # 尝试从默认位置加载
        load_dotenv()
        log_and_notify("已加载默认环境变量", "info")

    # 加载环境特定配置
    if env != "default":
        config_loader.load_env_config(env)
        log_and_notify(f"已加载环境配置: {env}", "info")

def get_llm_config() -> Dict[str, Any]:
    """获取 LLM 配置，从配置文件获取默认值，只有关键配置（如 API 密钥）从环境变量获取

    Returns:
        LLM 配置字典
    """
    # 从配置文件获取基础配置
    config = {
        "provider": config_loader.get("llm.provider", "openai"),
        "model": config_loader.get("llm.model", "gpt-4"),
        "max_tokens": config_loader.get("llm.max_tokens", 4000),
        "temperature": config_loader.get("llm.temperature", 0.7),
    }

    # 只有关键配置从环境变量获取，这些通常是敏感信息或需要在不同环境中变化的配置
    config["api_key"] = os.getenv("LLM_API_KEY", "")

    # 如果环境变量中明确设置了这些值，则覆盖配置文件中的值
    if os.getenv("LLM_PROVIDER"):
        config["provider"] = os.getenv("LLM_PROVIDER")
    if os.getenv("LLM_MODEL"):
        config["model"] = os.getenv("LLM_MODEL")
    if os.getenv("LLM_MAX_TOKENS"):
        config["max_tokens"] = int(os.getenv("LLM_MAX_TOKENS"))
    if os.getenv("LLM_TEMPERATURE"):
        config["temperature"] = float(os.getenv("LLM_TEMPERATURE"))

    # 根据提供商加载特定配置
    if config["provider"] == "openai":
        config["base_url"] = os.getenv("OPENAI_BASE_URL", config_loader.get("llm.openai.base_url", "https://api.openai.com/v1"))
    elif config["provider"] == "openrouter":
        config["base_url"] = os.getenv("OPENROUTER_BASE_URL", config_loader.get("llm.openrouter.base_url", "https://openrouter.ai/api/v1"))
        config["app_url"] = os.getenv("APP_URL", config_loader.get("llm.openrouter.app_url", ""))
        config["app_name"] = os.getenv("APP_NAME", config_loader.get("llm.openrouter.app_name", "Codebase Knowledge Builder"))
    elif config["provider"] in ["alibaba", "tongyi"]:
        config["base_url"] = os.getenv("ALIBABA_BASE_URL", config_loader.get("llm.alibaba.base_url", "https://dashscope.aliyuncs.com/api/v1"))
    elif config["provider"] == "volcengine":
        config["base_url"] = os.getenv("VOLCENGINE_BASE_URL", config_loader.get("llm.volcengine.base_url", "https://api.volcengine.com/ml/api/v1/services"))
        config["service_id"] = os.getenv("VOLCENGINE_SERVICE_ID", config_loader.get("llm.volcengine.service_id", ""))
    elif config["provider"] == "moonshot":
        config["base_url"] = os.getenv("MOONSHOT_BASE_URL", config_loader.get("llm.moonshot.base_url", "https://api.moonshot.cn/v1"))

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
        config["langfuse"]["enabled"] = os.getenv("LANGFUSE_ENABLED").lower() == "true"
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
    return config_loader.get_node_config(node_name)
