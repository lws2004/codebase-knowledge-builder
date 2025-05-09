"""LLM 客户端异步调用功能。"""

import time
from typing import Any, Dict, List, Optional

import litellm

from ..logger import log_and_notify


class LLMClientAsync:
    """LLM 客户端异步调用功能"""

    def __init__(self, base_client: Any, utils_client: Any, langfuse_client: Any):
        """初始化 LLM 客户端异步调用功能

        Args:
            base_client: 基础客户端实例
            utils_client: 工具客户端实例
            langfuse_client: Langfuse 客户端实例
        """
        self.base_client = base_client
        self.utils_client = utils_client
        self.langfuse_client = langfuse_client

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
            response = await litellm.acompletion(
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
