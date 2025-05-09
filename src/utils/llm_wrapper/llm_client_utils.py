"""LLM 客户端工具函数，提供各种辅助功能。"""

from typing import Any, Dict, List, Optional, cast

from ..logger import log_and_notify
from .token_utils import count_message_tokens, count_tokens, truncate_messages_if_needed


class LLMClientUtils:
    """LLM 客户端工具类，提供各种辅助功能"""

    def __init__(self, base_client: Any):
        """初始化 LLM 客户端工具类

        Args:
            base_client: 基础客户端实例
        """
        self.base_client = base_client

    def count_tokens(self, text: str) -> int:
        """计算文本的token数量

        使用token_utils.count_tokens函数计算token数量。

        Args:
            text: 要计算的文本

        Returns:
            token数量
        """
        model = self.base_client._get_model_string()
        return count_tokens(text, model)

    def count_message_tokens(self, messages: List[Dict[str, str]]) -> int:
        """计算消息列表的token数量

        使用token_utils.count_message_tokens函数计算token数量。

        Args:
            messages: 消息列表

        Returns:
            token数量
        """
        model = self.base_client._get_model_string()
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

    def _truncate_messages_if_needed(
        self, messages: List[Dict[str, str]], max_input_tokens: Optional[int] = None
    ) -> List[Dict[str, str]]:
        """如果需要，截断消息以适应最大输入token限制

        使用token_utils.truncate_messages_if_needed函数截断消息。
        如果max_input_tokens为None，则不进行截断。

        Args:
            messages: 消息列表
            max_input_tokens: 最大输入token数，如果为None则不进行截断

        Returns:
            可能被截断的消息列表
        """
        # 如果没有设置最大输入token数，直接返回原始消息
        if max_input_tokens is None:
            return messages

        model = self.base_client._get_model_string()
        return truncate_messages_if_needed(messages, max_input_tokens, model, self.split_text_to_chunks)

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
            return cast(str, choices[0].get("message", {}).get("content", ""))

        # 处理 LiteLLM 的 ModelResponse 类型
        try:
            # 尝试访问 choices 属性
            choices = getattr(response, "choices", [{}])
            if not choices:
                return ""
            message = getattr(choices[0], "message", {})
            return cast(str, getattr(message, "content", ""))
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
            return cast(str, choices[0].get("finish_reason", ""))

        # 处理 LiteLLM 的 ModelResponse 类型
        try:
            # 尝试访问 choices 属性
            choices = getattr(response, "choices", [{}])
            if not choices:
                return ""
            return cast(str, getattr(choices[0], "finish_reason", ""))
        except (AttributeError, IndexError):
            # 如果无法获取完成原因，返回空字符串
            return ""

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
