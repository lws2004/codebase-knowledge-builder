"""
LLM 客户端，提供统一的 LLM 调用接口。
"""
import json
import time
from typing import Dict, List, Any, Optional, Union
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
        self.langfuse_config = config.get("langfuse", {})
        self.langfuse_enabled = self.langfuse_config.get("enabled", False)
        self.langfuse = None

        if self.langfuse_enabled and self.langfuse_config.get("public_key") and self.langfuse_config.get("secret_key"):
            try:
                # Langfuse 初始化参数根据版本不同可能有所变化
                # 尝试使用 project 参数
                try:
                    self.langfuse = Langfuse(
                        public_key=self.langfuse_config.get("public_key", ""),
                        secret_key=self.langfuse_config.get("secret_key", ""),
                        host=self.langfuse_config.get("host", "https://cloud.langfuse.com"),
                        project=self.langfuse_config.get("project_name", "codebase-knowledge-builder")
                    )
                except TypeError:
                    # 如果失败，尝试使用 project_name 参数
                    self.langfuse = Langfuse(
                        public_key=self.langfuse_config.get("public_key", ""),
                        secret_key=self.langfuse_config.get("secret_key", ""),
                        host=self.langfuse_config.get("host", "https://cloud.langfuse.com")
                    )
                log_and_notify("Langfuse 初始化成功", "info")
            except Exception as e:
                log_and_notify(f"Langfuse 初始化失败: {str(e)}", "error")
                self.langfuse_enabled = False

        # 配置 LiteLLM
        litellm.api_key = self.api_key
        if self.base_url:
            litellm.api_base = self.base_url

        # 特定提供商的配置
        if self.provider == "openrouter":
            litellm.headers = {
                "HTTP-Referer": self.config.get("app_url", ""),
                "X-Title": self.config.get("app_name", "Code Tutorial Generator")
            }

        log_and_notify(f"初始化 LLM 客户端: {self.provider}/{self.model}", "info")

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

    async def acompletion(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        trace_id: Optional[str] = None,
        trace_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """异步调用 LLM 完成请求

        Args:
            messages: 消息列表
            temperature: 温度参数，如果为 None 则使用默认值
            max_tokens: 最大 token 数，如果为 None 则使用默认值
            trace_id: Langfuse 跟踪 ID
            trace_name: Langfuse 跟踪名称

        Returns:
            LLM 响应
        """
        model = self._get_model_string()
        temp = temperature if temperature is not None else self.temperature
        tokens = max_tokens if max_tokens is not None else self.max_tokens

        log_and_notify(f"调用 LLM: {model}, 温度: {temp}, 最大 token: {tokens}", "info")

        start_time = time.time()
        langfuse_trace = None

        try:
            # 创建 Langfuse 跟踪
            if self.langfuse_enabled and self.langfuse:
                if trace_id:
                    langfuse_trace = self.langfuse.trace(
                        id=trace_id,
                        name=trace_name or "LLM 调用"
                    )
                else:
                    langfuse_trace = self.langfuse.trace(
                        name=trace_name or "LLM 调用"
                    )

                # 创建 Langfuse 生成
                generation = langfuse_trace.generation(
                    name="LLM 请求",
                    model=model,
                    input=messages,
                    metadata={
                        "temperature": temp,
                        "max_tokens": tokens
                    }
                )

            # 调用 LLM
            response = await litellm.acompletion(
                model=model,
                messages=messages,
                temperature=temp,
                max_tokens=tokens
            )

            # 记录 Langfuse 结果
            if langfuse_trace and self.langfuse_enabled and 'generation' in locals():
                generation.end(
                    output=response.get("choices", [{}])[0].get("message", {}).get("content", ""),
                    metadata={
                        "finish_reason": response.get("choices", [{}])[0].get("finish_reason", ""),
                        "usage": response.get("usage", {})
                    }
                )

            elapsed_time = time.time() - start_time
            log_and_notify(f"LLM 调用完成，耗时: {elapsed_time:.2f}s", "info")

            return response
        except Exception as e:
            elapsed_time = time.time() - start_time
            error_msg = f"LLM 调用失败: {str(e)}, 耗时: {elapsed_time:.2f}s"
            log_and_notify(error_msg, "error")

            # 记录 Langfuse 错误
            if langfuse_trace and self.langfuse_enabled and 'generation' in locals():
                generation.end(
                    error=str(e)
                )

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
        trace_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """同步调用 LLM 完成请求

        Args:
            messages: 消息列表
            temperature: 温度参数，如果为 None 则使用默认值
            max_tokens: 最大 token 数，如果为 None 则使用默认值
            trace_id: Langfuse 跟踪 ID
            trace_name: Langfuse 跟踪名称

        Returns:
            LLM 响应
        """
        model = self._get_model_string()
        temp = temperature if temperature is not None else self.temperature
        tokens = max_tokens if max_tokens is not None else self.max_tokens

        log_and_notify(f"调用 LLM: {model}, 温度: {temp}, 最大 token: {tokens}", "info")

        start_time = time.time()
        langfuse_trace = None

        try:
            # 创建 Langfuse 跟踪
            if self.langfuse_enabled and self.langfuse:
                if trace_id:
                    langfuse_trace = self.langfuse.trace(
                        id=trace_id,
                        name=trace_name or "LLM 调用"
                    )
                else:
                    langfuse_trace = self.langfuse.trace(
                        name=trace_name or "LLM 调用"
                    )

                # 创建 Langfuse 生成
                generation = langfuse_trace.generation(
                    name="LLM 请求",
                    model=model,
                    input=messages,
                    metadata={
                        "temperature": temp,
                        "max_tokens": tokens
                    }
                )

            # 调用 LLM
            response = litellm.completion(
                model=model,
                messages=messages,
                temperature=temp,
                max_tokens=tokens
            )

            # 记录 Langfuse 结果
            if langfuse_trace and self.langfuse_enabled and 'generation' in locals():
                generation.end(
                    output=response.get("choices", [{}])[0].get("message", {}).get("content", ""),
                    metadata={
                        "finish_reason": response.get("choices", [{}])[0].get("finish_reason", ""),
                        "usage": response.get("usage", {})
                    }
                )

            elapsed_time = time.time() - start_time
            log_and_notify(f"LLM 调用完成，耗时: {elapsed_time:.2f}s", "info")

            return response
        except Exception as e:
            elapsed_time = time.time() - start_time
            error_msg = f"LLM 调用失败: {str(e)}, 耗时: {elapsed_time:.2f}s"
            log_and_notify(error_msg, "error")

            # 记录 Langfuse 错误
            if langfuse_trace and self.langfuse_enabled and 'generation' in locals():
                generation.end(
                    error=str(e)
                )

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

        if "choices" not in response or len(response["choices"]) == 0:
            return ""

        return response["choices"][0]["message"]["content"]
