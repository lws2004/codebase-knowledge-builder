"""
LLM 客户端，用于调用 LLM API。

此模块重新导出 llm_wrapper.llm_client 中的 LLMClient 类，
以保持向后兼容性，同时避免代码重复。
"""
from .llm_wrapper.llm_client import LLMClient

__all__ = ["LLMClient"]
