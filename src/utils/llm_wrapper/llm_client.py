"""
LLM 客户端，提供统一的 LLM 调用接口。
"""
import json
import os
import time
from typing import Dict, List, Any, Optional, Tuple
import litellm
from langfuse.client import Langfuse
from ..logger import log_and_notify


class LLMClient:
    """LLM 客户端，提供统一的 LLM 调用接口"""

    def __init__(self, config: Dict[str, Any]):
        """初始化 LLM 客户端

        Args:
            config: LLM 配置
        """
        self.config = config
        self.provider = config.get("provider", "openai")
        self.model = config.get("model", "gpt-4")
        self.api_key = config.get("api_key", "")
        self.base_url = config.get("base_url", "")
        self.max_tokens = config.get("max_tokens", 4000)
        self.temperature = config.get("temperature", 0.7)

        # 初始化 Langfuse
        self._init_langfuse()

        # 配置 LiteLLM
        self._configure_litellm()

        log_and_notify(f"初始化 LLM 客户端: {self.provider}/{self.model}", "info")

    def _init_langfuse(self) -> None:
        """初始化 Langfuse"""
        self.langfuse_config = self.config.get("langfuse", {})
        self.langfuse_enabled = self.langfuse_config.get("enabled", False)
        self.langfuse = None

        if not (self.langfuse_enabled and
                self.langfuse_config.get("public_key") and
                self.langfuse_config.get("secret_key")):
            return

        try:
            self._create_langfuse_client()
            log_and_notify("Langfuse 初始化成功", "info")
        except Exception as e:
            log_and_notify(f"Langfuse 初始化失败: {str(e)}", "error")
            self.langfuse_enabled = False

    def _create_langfuse_client(self) -> None:
        """创建 Langfuse 客户端"""
        # 尝试使用 project 参数
        try:
            self.langfuse = Langfuse(
                public_key=self.langfuse_config.get("public_key", ""),
                secret_key=self.langfuse_config.get("secret_key", ""),
                host=self.langfuse_config.get(
                    "host", "https://cloud.langfuse.com"
                ),
                project=self.langfuse_config.get(
                    "project_name", "codebase-knowledge-builder"
                )
            )
        except TypeError:
            # 如果失败，尝试使用 project_name 参数
            self.langfuse = Langfuse(
                public_key=self.langfuse_config.get("public_key", ""),
                secret_key=self.langfuse_config.get("secret_key", ""),
                host=self.langfuse_config.get(
                    "host", "https://cloud.langfuse.com"
                )
            )

    def _configure_litellm(self) -> None:
        """配置 LiteLLM"""
        # 设置 API 密钥
        provider_env = f"{self.provider.upper()}_API_KEY"
        litellm.api_key = self.api_key or os.getenv(provider_env, "")

        # 设置基础 URL
        if self.base_url:
            litellm.api_base = self.base_url

        # 特定提供商的配置
        if self.provider == "openrouter":
            litellm.headers = {
                "HTTP-Referer": self.config.get("app_url", ""),
                "X-Title": self.config.get(
                    "app_name", "Code Tutorial Generator"
                )
            }

    def _get_model_string(self) -> str:
        """获取模型字符串

        Returns:
            模型字符串
        """
        if self.provider == "openai":
            return self.model
        elif self.provider == "openrouter":
            return f"openrouter/{self.model}"
        elif self.provider in ["alibaba", "tongyi"]:
            return f"alibaba/{self.model}"
        elif self.provider == "volcengine":
            return f"volcengine/{self.model}"
        elif self.provider == "moonshot":
            return f"moonshot/{self.model}"
        else:
            return self.model

    def _create_langfuse_trace(
        self,
        trace_id: Optional[str],
        trace_name: Optional[str]
    ) -> Tuple[Any, Any]:
        """创建 Langfuse 跟踪

        Args:
            trace_id: 跟踪 ID
            trace_name: 跟踪名称

        Returns:
            跟踪对象和生成对象
        """
        if not (self.langfuse_enabled and self.langfuse):
            return None, None

        # 创建跟踪
        if trace_id:
            trace = self.langfuse.trace(
                id=trace_id,
                name=trace_name or "LLM 调用"
            )
        else:
            trace = self.langfuse.trace(
                name=trace_name or "LLM 调用"
            )

        return trace, None

    def _create_langfuse_generation(
        self,
        trace: Any,
        model: str,
        messages: List[Dict[str, str]],
        temp: float,
        tokens: int
    ) -> Any:
        """创建 Langfuse 生成

        Args:
            trace: 跟踪对象
            model: 模型名称
            messages: 消息列表
            temp: 温度
            tokens: 最大 token 数

        Returns:
            生成对象
        """
        if not trace:
            return None

        return trace.generation(
            name="LLM 请求",
            model=model,
            input=messages,
            metadata={
                "temperature": temp,
                "max_tokens": tokens
            }
        )

    def _record_langfuse_result(
        self,
        trace: Any,
        generation: Any,
        response: Dict[str, Any]
    ) -> None:
        """记录 Langfuse 结果

        Args:
            trace: 跟踪对象
            generation: 生成对象
            response: LLM 响应
        """
        if not (trace and generation and self.langfuse_enabled):
            return

        generation.end(
            output=self._get_content_from_response(response),
            metadata={
                "finish_reason": self._get_finish_reason(response),
                "usage": response.get("usage", {})
            }
        )

    def _get_content_from_response(self, response: Dict[str, Any]) -> str:
        """从响应中获取内容

        Args:
            response: LLM 响应

        Returns:
            内容字符串
        """
        choices = response.get("choices", [{}])
        if not choices:
            return ""
        return choices[0].get("message", {}).get("content", "")

    def _get_finish_reason(self, response: Dict[str, Any]) -> str:
        """从响应中获取完成原因

        Args:
            response: LLM 响应

        Returns:
            完成原因
        """
        choices = response.get("choices", [{}])
        if not choices:
            return ""
        return choices[0].get("finish_reason", "")

    def _record_langfuse_error(
        self,
        trace: Any,
        generation: Any,
        error: str
    ) -> None:
        """记录 Langfuse 错误

        Args:
            trace: 跟踪对象
            generation: 生成对象
            error: 错误信息
        """
        if not (trace and generation and self.langfuse_enabled):
            return

        generation.end(error=error)

    async def acompletion(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        trace_id: Optional[str] = None,
        trace_name: Optional[str] = None,
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """异步调用 LLM 完成请求

        Args:
            messages: 消息列表
            temperature: 温度参数，如果为 None 则使用默认值
            max_tokens: 最大 token 数，如果为 None 则使用默认值
            trace_id: Langfuse 跟踪 ID
            trace_name: Langfuse 跟踪名称
            model: 模型名称，如果为 None 则使用默认值

        Returns:
            LLM 响应
        """
        model_name = model or self._get_model_string()
        temp = temperature if temperature is not None else self.temperature
        tokens = max_tokens if max_tokens is not None else self.max_tokens

        log_msg = f"调用 LLM: {model_name}, 温度: {temp}, 最大 token: {tokens}"
        log_and_notify(log_msg, "info")

        start_time = time.time()
        trace, generation = self._create_langfuse_trace(trace_id, trace_name)

        try:
            # 创建 Langfuse 生成
            generation = self._create_langfuse_generation(
                trace, model_name, messages, temp, tokens
            )

            # 调用 LLM
            response = await litellm.acompletion(
                model=model_name,
                messages=messages,
                temperature=temp,
                max_tokens=tokens
            )

            # 记录 Langfuse 结果
            self._record_langfuse_result(trace, generation, response)

            elapsed_time = time.time() - start_time
            log_and_notify(f"LLM 调用完成，耗时: {elapsed_time:.2f}s", "info")

            return response
        except Exception as e:
            elapsed_time = time.time() - start_time
            error_msg = f"LLM 调用失败: {str(e)}, 耗时: {elapsed_time:.2f}s"
            log_and_notify(error_msg, "error")

            # 记录 Langfuse 错误
            self._record_langfuse_error(trace, generation, str(e))

            # 返回错误响应
            return {
                "error": str(e),
                "choices": [{"message": {"content": f"Error: {str(e)}"}}]
            }

    def completion(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        trace_id: Optional[str] = None,
        trace_name: Optional[str] = None,
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """同步调用 LLM 完成请求

        Args:
            messages: 消息列表
            temperature: 温度参数，如果为 None 则使用默认值
            max_tokens: 最大 token 数，如果为 None 则使用默认值
            trace_id: Langfuse 跟踪 ID
            trace_name: Langfuse 跟踪名称
            model: 模型名称，如果为 None 则使用默认值

        Returns:
            LLM 响应
        """
        model_name = model or self._get_model_string()
        temp = temperature if temperature is not None else self.temperature
        tokens = max_tokens if max_tokens is not None else self.max_tokens

        log_msg = f"调用 LLM: {model_name}, 温度: {temp}, 最大 token: {tokens}"
        log_and_notify(log_msg, "info")

        start_time = time.time()
        trace, generation = self._create_langfuse_trace(trace_id, trace_name)

        try:
            # 创建 Langfuse 生成
            generation = self._create_langfuse_generation(
                trace, model_name, messages, temp, tokens
            )

            # 调用 LLM
            response = litellm.completion(
                model=model_name,
                messages=messages,
                temperature=temp,
                max_tokens=tokens
            )

            # 记录 Langfuse 结果
            self._record_langfuse_result(trace, generation, response)

            elapsed_time = time.time() - start_time
            log_and_notify(f"LLM 调用完成，耗时: {elapsed_time:.2f}s", "info")

            return response
        except Exception as e:
            elapsed_time = time.time() - start_time
            error_msg = f"LLM 调用失败: {str(e)}, 耗时: {elapsed_time:.2f}s"
            log_and_notify(error_msg, "error")

            # 记录 Langfuse 错误
            self._record_langfuse_error(trace, generation, str(e))

            # 返回错误响应
            return {
                "error": str(e),
                "choices": [{"message": {"content": f"Error: {str(e)}"}}]
            }

    def get_completion_content(self, response: Dict[str, Any]) -> str:
        """从 LLM 响应中获取内容

        Args:
            response: LLM 响应

        Returns:
            内容字符串
        """
        if "error" in response:
            return f"Error: {response['error']}"

        return self._get_content_from_response(response)
