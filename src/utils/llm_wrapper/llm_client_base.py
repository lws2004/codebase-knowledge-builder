"""LLM 客户端基础类，提供初始化和配置功能。"""

import os
from typing import Any, Dict

import litellm

from ..logger import log_and_notify


class LLMClientBase:
    """LLM 客户端基础类，提供初始化和配置功能"""

    def __init__(self, config: Dict[str, Any]):
        """初始化 LLM 客户端基础类

        Args:
            config: LLM 配置
        """
        self.config = config
        self.model = config.get("model", "")

        if not self.model:
            # 如果没有提供模型，记录警告
            log_and_notify("未提供模型配置，请确保在环境变量或配置文件中设置LLM_MODEL", "warning")
            # 尝试从环境变量获取
            self.model = os.getenv("LLM_MODEL", "")

        # 从模型字符串中提取提供商信息
        if self.model and "/" in self.model:
            self.provider = self.model.split("/")[0]
        else:
            self.provider = config.get("provider", "")

        self.api_key = config.get("api_key", "")
        self.base_url = config.get("base_url", "")
        self.max_tokens = config.get("max_tokens", 4000)
        # 只有当配置中明确设置了max_input_tokens时才使用，否则不设置限制
        # 使用None作为默认值，表示不限制输入token数
        self.max_input_tokens = config.get("max_input_tokens") if "max_input_tokens" in config else None
        self.temperature = config.get("temperature", 0.7)

        # Langfuse 相关属性
        self.langfuse_config = self.config.get("langfuse", {})
        self.langfuse_enabled = self.langfuse_config.get("enabled", False)
        self.langfuse = None

        # 配置 LiteLLM
        self._configure_litellm()

        log_and_notify(f"初始化 LLM 客户端: {self.model}", "info")

    def _configure_litellm(self) -> None:
        """配置 LiteLLM"""
        # 设置 API 密钥
        if not self.provider:
            log_and_notify("未提供有效的提供商信息，无法设置API密钥", "warning")
            return

        provider_env = f"{self.provider.upper()}_API_KEY"
        api_key = self.api_key or os.getenv(provider_env) or os.getenv("LLM_API_KEY")

        if not api_key:
            log_and_notify(
                f"未找到{self.provider}的API密钥，请确保设置了{provider_env}或LLM_API_KEY环境变量", "warning"
            )

        # 确保模型字符串包含提供商前缀
        if self.model and "/" not in self.model:
            if self.provider == "openai" and self.model.startswith("gpt-"):
                log_and_notify(f"OpenAI gpt 模型不添加前缀: model={self.model}", "debug")
            else:
                self.model = f"{self.provider}/{self.model}"
                log_and_notify(f"添加提供商前缀: model={self.model}", "debug")

        # 设置 API 密钥
        litellm.api_key = api_key

        # 设置基础 URL
        if self.base_url:
            litellm.api_base = self.base_url

        # 设置通用头信息
        headers = {}

        # 添加可能的引用URL和应用名称
        if self.config.get("site_url"):
            headers["HTTP-Referer"] = self.config.get("site_url")
        if self.config.get("app_name"):
            headers["X-Title"] = self.config.get("app_name")

        # 如果有头信息，设置到litellm
        if headers:
            litellm.headers = headers  # type: ignore[assignment]

        # 配置缓存
        self._configure_cache()

    def _configure_cache(self) -> None:
        """配置 LiteLLM 缓存"""
        cache_config = self.config.get("cache", {})
        if cache_config.get("enabled", False):
            try:
                # 获取缓存目录
                cache_dir = cache_config.get("dir", ".cache/llm")

                # 确保缓存目录存在
                os.makedirs(cache_dir, exist_ok=True)

                # 设置缓存环境变量
                os.environ["LITELLM_CACHE"] = "true"
                os.environ["LITELLM_CACHE_TYPE"] = "redis"
                os.environ["LITELLM_CACHE_HOST"] = "memory"
                os.environ["LITELLM_CACHE_PORT"] = "6379"
                os.environ["LITELLM_CACHE_TTL"] = str(cache_config.get("ttl", 86400))

                log_and_notify(f"LiteLLM 缓存已启用，TTL: {cache_config.get('ttl', 86400)}秒", "info")
            except Exception as e:
                log_and_notify(f"配置 LiteLLM 缓存失败: {str(e)}", "error")

    def _get_model_string(self) -> str:
        """获取模型字符串，使用 LiteLLM 的模型解析格式

        LiteLLM 支持以下格式：
        - 'openai/gpt-3.5-turbo'
        - 'anthropic/claude-3-opus'
        - 'openrouter/anthropic/claude-3-opus'

        详见: https://docs.litellm.ai/docs/providers

        Returns:
            模型字符串
        """
        # 如果没有设置模型，尝试从环境变量获取
        if not self.model:
            self.model = os.getenv("LLM_MODEL", "")
            if not self.model:
                log_and_notify("未设置模型，请确保在环境变量或配置中设置LLM_MODEL", "error")
                return ""

        # 处理环境变量替换格式 ${VAR:-default}
        if (
            isinstance(self.model, str)
            and self.model.startswith("${")
            and ":-" in self.model
            and self.model.endswith("}")
        ):
            # 解析环境变量名称和默认值
            env_part = self.model[2:-1]  # 去掉 ${ 和 }
            env_name, default_value = env_part.split(":-", 1)
            # 获取环境变量值，如果不存在则使用默认值
            self.model = os.getenv(env_name, default_value)

        # 记录当前的模型
        log_and_notify(f"处理模型字符串: model={self.model}", "debug")

        # 确保模型字符串包含提供商前缀
        if self.model and "/" not in self.model and self.provider:
            # 对于 OpenAI 的 gpt 模型，不添加前缀
            if self.provider == "openai" and self.model.startswith("gpt-"):
                log_and_notify(f"OpenAI gpt 模型不添加前缀: model={self.model}", "debug")
            else:
                self.model = f"{self.provider}/{self.model}"
                log_and_notify(f"添加提供商前缀: model={self.model}", "debug")

        # 直接返回模型字符串，假设它已经是完整的格式
        # 例如: "openai/gpt-4" 或 "openrouter/qwen/qwen3-30b-a3b:free"
        log_and_notify(f"最终模型字符串: {self.model}", "debug")
        return self.model
