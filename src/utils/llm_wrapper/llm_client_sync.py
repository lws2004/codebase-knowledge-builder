"""LLM 客户端同步调用功能。"""

import json
import re
import time
from typing import Any, Dict, List, Optional, cast

import litellm

from ..logger import log_and_notify


class LLMClientSync:
    """LLM 客户端同步调用功能"""

    def __init__(self, base_client: Any, utils_client: Any, langfuse_client: Any):
        """初始化 LLM 客户端同步调用功能

        Args:
            base_client: 基础客户端实例
            utils_client: 工具客户端实例
            langfuse_client: Langfuse 客户端实例
        """
        self.base_client = base_client
        self.utils_client = utils_client
        self.langfuse_client = langfuse_client

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
        model_name = model or self.base_client._get_model_string()
        if not model_name:
            error_msg = "未提供有效的模型配置，请确保在环境变量或配置中设置LLM_MODEL"
            log_and_notify(error_msg, "error")
            return {"error": error_msg, "choices": [{"message": {"content": f"Error: {error_msg}"}}]}

        temp = temperature if temperature is not None else self.base_client.temperature
        tokens = max_tokens if max_tokens is not None else self.base_client.max_tokens
        input_tokens = max_input_tokens if max_input_tokens is not None else self.base_client.max_input_tokens

        # 构建日志消息，如果input_tokens为None则不显示最大输入token信息
        if input_tokens is not None:
            log_msg = f"调用 LLM: {model_name}, 温度: {temp}, 最大输出token: {tokens}, 最大输入token: {input_tokens}"
        else:
            log_msg = f"调用 LLM: {model_name}, 温度: {temp}, 最大输出token: {tokens}"
        log_and_notify(log_msg, "info")

        # 检查并可能截断输入消息
        truncated_messages = self.utils_client._truncate_messages_if_needed(messages, input_tokens)
        if len(truncated_messages) != len(messages):
            log_and_notify(f"消息已截断: 原始消息数={len(messages)}, 截断后消息数={len(truncated_messages)}", "warning")

        # 创建 Langfuse 跟踪
        trace, generation, start_time = self.langfuse_client.track_completion(
            model_name, messages, truncated_messages, temp, tokens, trace_id, trace_name
        )

        try:
            # 调用 LLM
            response = litellm.completion(
                model=model_name, messages=truncated_messages, temperature=temp, max_tokens=tokens
            )

            # 记录 Langfuse 结果
            self.langfuse_client.record_result(trace, generation, response)

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
                    self.langfuse_client.record_error(trace, generation, str(e))
                except Exception as langfuse_error:
                    log_and_notify(f"记录 Langfuse 错误失败: {str(langfuse_error)}", "error")

            # 返回错误响应
            return {"error": str(e), "choices": [{"message": {"content": f"Error: {str(e)}"}}]}

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

        # 调用LLM，明确设置max_input_tokens=None
        response = self.completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            trace_name=trace_name,
            model=model,
            max_input_tokens=None,
        )

        # 获取响应内容
        return cast(str, self.utils_client.get_completion_content(response))

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

        model_name = model or self.base_client._get_model_string()
        if not model_name:
            error_msg = "未提供有效的模型配置，请确保在环境变量或配置中设置LLM_MODEL"
            log_and_notify(error_msg, "error")
            return {"error": error_msg}

        temp = temperature if temperature is not None else self.base_client.temperature
        tokens = max_tokens if max_tokens is not None else self.base_client.max_tokens

        try:
            # 如果提供了schema，使用litellm的response_format参数
            if schema:
                # 使用litellm的JSON模式功能，不限制输入token数
                response = litellm.completion(
                    model=model_name,
                    messages=messages,
                    temperature=temp,
                    max_tokens=tokens,
                    response_format={"type": "json_object", "schema": schema},
                )
                content = self.utils_client.get_completion_content(response)
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
                return self._parse_json_response(response_text)
        except Exception as e:
            log_and_notify(f"解析JSON失败: {str(e)}", "error")
            # 返回原始文本作为错误信息
            return {
                "error": f"解析JSON失败: {str(e)}",
                "raw_text": prompt,
            }

    def _parse_json_response(self, response_text: str) -> Any:
        """解析JSON响应

        Args:
            response_text: 响应文本

        Returns:
            解析后的JSON对象
        """
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
