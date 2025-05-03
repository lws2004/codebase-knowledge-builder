"""LLM 客户端，提供统一的 LLM 调用接口。"""

import json
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import litellm
from langfuse.client import Langfuse

from ..logger import log_and_notify
from .token_utils import count_message_tokens, count_tokens, truncate_messages_if_needed


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
        self.max_input_tokens = config.get("max_input_tokens", 8000)
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

        if not (
            self.langfuse_enabled and self.langfuse_config.get("public_key") and self.langfuse_config.get("secret_key")
        ):
            return

        try:
            self._create_langfuse_client()
            log_and_notify("Langfuse 初始化成功", "info")
        except Exception as e:
            log_and_notify(f"Langfuse 初始化失败: {str(e)}", "error")
            self.langfuse_enabled = False

    def _create_langfuse_client(self) -> None:
        """创建 Langfuse 客户端"""
        # 创建 Langfuse 客户端
        self.langfuse = Langfuse(
            public_key=self.langfuse_config.get("public_key", ""),
            secret_key=self.langfuse_config.get("secret_key", ""),
            host=self.langfuse_config.get("host", "https://cloud.langfuse.com"),
        )

    def _configure_litellm(self) -> None:
        """配置 LiteLLM"""
        # 设置 API 密钥
        provider_env = f"{self.provider.upper()}_API_KEY"
        litellm.api_key = self.api_key or os.getenv(provider_env, "")

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
            litellm.headers = headers

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

        # 记录当前的提供商和模型
        log_and_notify(f"处理模型字符串: provider={self.provider}, model={self.model}", "debug")

        # 如果模型已经包含提供商前缀，直接使用
        if "/" in self.model:
            model_string = self.model
        else:
            # 组合提供商和模型
            model_string = f"{self.provider.lower()}/{self.model}"

        log_and_notify(f"最终模型字符串: {model_string}", "debug")
        return model_string

    def count_tokens(self, text: str) -> int:
        """计算文本的token数量

        使用token_utils.count_tokens函数计算token数量。

        Args:
            text: 要计算的文本

        Returns:
            token数量
        """
        model = self._get_model_string()
        return count_tokens(text, model)

    def count_message_tokens(self, messages: List[Dict[str, str]]) -> int:
        """计算消息列表的token数量

        使用token_utils.count_message_tokens函数计算token数量。

        Args:
            messages: 消息列表

        Returns:
            token数量
        """
        model = self._get_model_string()
        return count_message_tokens(messages, model)

    def split_text_to_chunks(self, text: str, max_tokens: int) -> List[str]:
        """将文本分割成不超过最大token数的块

        使用token感知的分块策略，调用rag_utils.chunk_text进行实际分块。

        Args:
            text: 要分割的文本
            max_tokens: 每个块的最大token数

        Returns:
            文本块列表
        """
        try:
            from ..rag_utils import chunk_text

            # 如果文本为空，直接返回空列表
            if not text:
                return []

            # 如果整个文本的token数小于max_tokens，直接返回
            total_tokens = self.count_tokens(text)
            if total_tokens <= max_tokens:
                return [text]

            # 估算字符数与token数的比例
            char_per_token = len(text) / total_tokens if total_tokens > 0 else 4

            # 将token数转换为近似字符数
            approx_chars = int(max_tokens * char_per_token)

            # 使用rag_utils.chunk_text进行分块，启用智能分块
            char_chunks = chunk_text(text, chunk_size=approx_chars, overlap=approx_chars // 5, smart_chunking=True)

            # 检查每个块的token数，如果超过限制则进一步分割
            token_chunks = []
            for chunk in char_chunks:
                chunk_tokens = self.count_tokens(chunk)
                if chunk_tokens <= max_tokens:
                    token_chunks.append(chunk)
                else:
                    # 如果单个块超过token限制，递归分割
                    sub_chunks = self.split_text_to_chunks(chunk, max_tokens)
                    token_chunks.extend(sub_chunks)

            return token_chunks
        except Exception as e:
            log_and_notify(f"文本分块失败: {str(e)}", "error")
            # 如果分块失败，至少返回原始文本的一部分
            return [text[: len(text) // 2]]

    def _create_langfuse_trace(self, trace_id: Optional[str], trace_name: Optional[str]) -> Tuple[Any, Any]:
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
            trace = self.langfuse.trace(id=trace_id, name=trace_name or "LLM 调用")
        else:
            trace = self.langfuse.trace(name=trace_name or "LLM 调用")

        return trace, None

    def _create_langfuse_generation(
        self, trace: Any, model: str, messages: List[Dict[str, str]], temp: float, tokens: int
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
            name="LLM 请求", model=model, input=messages, metadata={"temperature": temp, "max_tokens": tokens}
        )

    def _record_langfuse_result(self, trace: Any, generation: Any, response: Any) -> None:
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
                "usage": getattr(response, "usage", response.get("usage", {})),
            },
        )

    def _get_content_from_response(self, response: Any) -> str:
        """从响应中获取内容

        Args:
            response: LLM 响应

        Returns:
            内容字符串
        """
        # 处理字典类型的响应
        if isinstance(response, dict):
            choices = response.get("choices", [{}])
            if not choices:
                return ""
            return choices[0].get("message", {}).get("content", "")

        # 处理 LiteLLM 的 ModelResponse 类型
        try:
            # 尝试访问 choices 属性
            choices = getattr(response, "choices", [{}])
            if not choices:
                return ""
            message = getattr(choices[0], "message", {})
            return getattr(message, "content", "")
        except (AttributeError, IndexError):
            # 如果无法获取内容，返回空字符串
            return ""

    def _get_finish_reason(self, response: Any) -> str:
        """从响应中获取完成原因

        Args:
            response: LLM 响应

        Returns:
            完成原因
        """
        # 处理字典类型的响应
        if isinstance(response, dict):
            choices = response.get("choices", [{}])
            if not choices:
                return ""
            return choices[0].get("finish_reason", "")

        # 处理 LiteLLM 的 ModelResponse 类型
        try:
            # 尝试访问 choices 属性
            choices = getattr(response, "choices", [{}])
            if not choices:
                return ""
            return getattr(choices[0], "finish_reason", "")
        except (AttributeError, IndexError):
            # 如果无法获取完成原因，返回空字符串
            return ""

    def _record_langfuse_error(self, trace: Any, generation: Any, error: str) -> None:
        """记录 Langfuse 错误

        Args:
            trace: 跟踪对象
            generation: 生成对象
            error: 错误信息
        """
        if not (trace and generation and self.langfuse_enabled):
            return

        generation.end(error=error)

    def _truncate_messages_if_needed(
        self, messages: List[Dict[str, str]], max_input_tokens: int
    ) -> List[Dict[str, str]]:
        """如果需要，截断消息以适应最大输入token限制

        使用token_utils.truncate_messages_if_needed函数截断消息。

        Args:
            messages: 消息列表
            max_input_tokens: 最大输入token数

        Returns:
            可能被截断的消息列表
        """
        model = self._get_model_string()
        return truncate_messages_if_needed(messages, max_input_tokens, model, self.split_text_to_chunks)

    async def acompletion(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        trace_id: Optional[str] = None,
        trace_name: Optional[str] = None,
        model: Optional[str] = None,
        max_input_tokens: Optional[int] = None,
    ) -> Any:
        """异步调用 LLM 完成请求

        Args:
            messages: 消息列表
            temperature: 温度参数，如果为 None 则使用默认值
            max_tokens: 最大 token 数，如果为 None 则使用默认值
            trace_id: Langfuse 跟踪 ID
            trace_name: Langfuse 跟踪名称
            model: 模型名称，如果为 None 则使用默认值
            max_input_tokens: 最大输入token数，如果为 None 则使用默认值

        Returns:
            LLM 响应
        """
        model_name = model or self._get_model_string()
        temp = temperature if temperature is not None else self.temperature
        tokens = max_tokens if max_tokens is not None else self.max_tokens
        input_tokens = max_input_tokens if max_input_tokens is not None else self.max_input_tokens

        log_msg = f"调用 LLM: {model_name}, 温度: {temp}, 最大输出token: {tokens}, 最大输入token: {input_tokens}"
        log_and_notify(log_msg, "info")

        # 检查并可能截断输入消息
        truncated_messages = self._truncate_messages_if_needed(messages, input_tokens)
        if len(truncated_messages) != len(messages):
            log_and_notify(f"消息已截断: 原始消息数={len(messages)}, 截断后消息数={len(truncated_messages)}", "warning")

        start_time = time.time()
        trace, generation = self._create_langfuse_trace(trace_id, trace_name)

        try:
            # 创建 Langfuse 生成
            generation = self._create_langfuse_generation(trace, model_name, truncated_messages, temp, tokens)

            # 调用 LLM
            response = await litellm.acompletion(
                model=model_name, messages=truncated_messages, temperature=temp, max_tokens=tokens
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
            if trace and generation:
                try:
                    self._record_langfuse_error(trace, generation, str(e))
                except Exception as langfuse_error:
                    log_and_notify(f"记录 Langfuse 错误失败: {str(langfuse_error)}", "error")

            # 返回错误响应
            return {"error": str(e), "choices": [{"message": {"content": f"Error: {str(e)}"}}]}

    def completion(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        trace_id: Optional[str] = None,
        trace_name: Optional[str] = None,
        model: Optional[str] = None,
        max_input_tokens: Optional[int] = None,
    ) -> Any:
        """同步调用 LLM 完成请求

        Args:
            messages: 消息列表
            temperature: 温度参数，如果为 None 则使用默认值
            max_tokens: 最大 token 数，如果为 None 则使用默认值
            trace_id: Langfuse 跟踪 ID
            trace_name: Langfuse 跟踪名称
            model: 模型名称，如果为 None 则使用默认值
            max_input_tokens: 最大输入token数，如果为 None 则使用默认值

        Returns:
            LLM 响应
        """
        model_name = model or self._get_model_string()
        temp = temperature if temperature is not None else self.temperature
        tokens = max_tokens if max_tokens is not None else self.max_tokens
        input_tokens = max_input_tokens if max_input_tokens is not None else self.max_input_tokens

        log_msg = f"调用 LLM: {model_name}, 温度: {temp}, 最大输出token: {tokens}, 最大输入token: {input_tokens}"
        log_and_notify(log_msg, "info")

        # 检查并可能截断输入消息
        truncated_messages = self._truncate_messages_if_needed(messages, input_tokens)
        if len(truncated_messages) != len(messages):
            log_and_notify(f"消息已截断: 原始消息数={len(messages)}, 截断后消息数={len(truncated_messages)}", "warning")

        start_time = time.time()
        trace, generation = self._create_langfuse_trace(trace_id, trace_name)

        try:
            # 创建 Langfuse 生成
            generation = self._create_langfuse_generation(trace, model_name, truncated_messages, temp, tokens)

            # 调用 LLM
            response = litellm.completion(
                model=model_name, messages=truncated_messages, temperature=temp, max_tokens=tokens
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
            if trace and generation:
                try:
                    self._record_langfuse_error(trace, generation, str(e))
                except Exception as langfuse_error:
                    log_and_notify(f"记录 Langfuse 错误失败: {str(langfuse_error)}", "error")

            # 返回错误响应
            return {"error": str(e), "choices": [{"message": {"content": f"Error: {str(e)}"}}]}

    def get_completion_content(self, response: Any) -> str:
        """从 LLM 响应中获取内容

        Args:
            response: LLM 响应

        Returns:
            内容字符串
        """
        # 处理字典类型的响应
        if isinstance(response, dict) and "error" in response:
            return f"Error: {response['error']}"

        # 处理 LiteLLM 的 ModelResponse 类型
        try:
            if hasattr(response, "error"):
                return f"Error: {getattr(response, 'error', '')}"
        except AttributeError:
            pass

        return self._get_content_from_response(response)

    def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        trace_name: Optional[str] = None,
        model: Optional[str] = None,
    ) -> str:
        """简化的文本生成方法，适用于简单的文本生成任务

        Args:
            prompt: 用户提示
            system_prompt: 系统提示，如果为None则不使用系统提示
            temperature: 温度参数，如果为None则使用默认值
            max_tokens: 最大token数，如果为None则使用默认值
            trace_name: Langfuse跟踪名称
            model: 模型名称，如果为None则使用默认值

        Returns:
            生成的文本
        """
        # 准备消息
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # 调用LLM
        response = self.completion(
            messages=messages, temperature=temperature, max_tokens=max_tokens, trace_name=trace_name, model=model
        )

        # 获取响应内容
        return self.get_completion_content(response)

    def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = 0.1,  # 默认使用较低的温度以获得更确定性的输出
        max_tokens: Optional[int] = None,
        trace_name: Optional[str] = None,
        model: Optional[str] = None,
        schema: Optional[Dict[str, Any]] = None,  # 可选的JSON schema
    ) -> Any:
        """生成JSON格式的响应

        使用litellm的JSON模式功能，确保生成的JSON符合预期格式。

        Args:
            prompt: 用户提示
            system_prompt: 系统提示，如果为None则使用默认系统提示
            temperature: 温度参数，默认为0.1以获得更确定性的输出
            max_tokens: 最大token数，如果为None则使用默认值
            trace_name: Langfuse跟踪名称
            model: 模型名称，如果为None则使用默认值
            schema: JSON schema，用于验证生成的JSON

        Returns:
            解析后的JSON对象
        """
        # 如果没有提供系统提示，使用默认的JSON生成提示
        if not system_prompt:
            system_prompt = """你是一个JSON生成专家。你的任务是生成有效的JSON格式数据。
请确保你的响应是有效的JSON格式，不要包含任何其他文本或解释。
不要使用Markdown代码块，直接输出JSON。"""

        # 准备消息
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        model_name = model or self._get_model_string()
        temp = temperature if temperature is not None else self.temperature
        tokens = max_tokens if max_tokens is not None else self.max_tokens

        try:
            # 如果提供了schema，使用litellm的response_format参数
            if schema:
                # 使用litellm的JSON模式功能
                response = litellm.completion(
                    model=model_name,
                    messages=messages,
                    temperature=temp,
                    max_tokens=tokens,
                    response_format={"type": "json_object", "schema": schema},
                )
                content = self.get_completion_content(response)
                return json.loads(content)
            else:
                # 没有提供schema，使用普通的文本生成然后解析
                response_text = self.generate_text(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    trace_name=trace_name or "生成JSON",
                    model=model,
                )

                # 尝试解析JSON
                # 首先尝试直接解析
                try:
                    return json.loads(response_text)
                except json.JSONDecodeError:
                    # 如果直接解析失败，尝试从可能的Markdown代码块中提取JSON
                    json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", response_text)
                    if json_match:
                        json_str = json_match.group(1)
                    else:
                        json_str = response_text

                    # 清理可能的前缀和后缀
                    json_str = re.sub(r"^[\s\S]*?(\{|\[)", r"\1", json_str)
                    json_str = re.sub(r"(\}|\])[\s\S]*$", r"\1", json_str)

                    # 解析JSON
                    return json.loads(json_str)
        except Exception as e:
            log_and_notify(f"解析JSON失败: {str(e)}", "error")
            # 返回原始文本作为错误信息
            return {
                "error": f"解析JSON失败: {str(e)}",
                "raw_text": response_text if "response_text" in locals() else str(e),
            }
