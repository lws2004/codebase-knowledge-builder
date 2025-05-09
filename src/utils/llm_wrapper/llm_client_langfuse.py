"""LLM 客户端 Langfuse 集成，提供跟踪和监控功能。"""

import time
from typing import Any, Dict, List, Optional, Tuple

from langfuse.client import Langfuse  # type: ignore[import-untyped]

from ..logger import log_and_notify


class LLMClientLangfuse:
    """LLM 客户端 Langfuse 集成，提供跟踪和监控功能"""

    def __init__(self, base_client: Any, utils_client: Any):
        """初始化 LLM 客户端 Langfuse 集成

        Args:
            base_client: 基础客户端实例
            utils_client: 工具客户端实例
        """
        self.base_client = base_client
        self.utils_client = utils_client
        self._init_langfuse()

    def _init_langfuse(self) -> None:
        """初始化 Langfuse"""
        if not (
            self.base_client.langfuse_enabled
            and self.base_client.langfuse_config.get("public_key")
            and self.base_client.langfuse_config.get("secret_key")
        ):
            return

        try:
            self._create_langfuse_client()
            log_and_notify("Langfuse 初始化成功", "info")
        except Exception as e:
            log_and_notify(f"Langfuse 初始化失败: {str(e)}", "error")
            self.base_client.langfuse_enabled = False

    def _create_langfuse_client(self) -> None:
        """创建 Langfuse 客户端"""
        # 创建 Langfuse 客户端
        self.base_client.langfuse = Langfuse(
            public_key=self.base_client.langfuse_config.get("public_key", ""),
            secret_key=self.base_client.langfuse_config.get("secret_key", ""),
            host=self.base_client.langfuse_config.get("host", "https://cloud.langfuse.com"),
        )

    def create_trace(self, trace_id: Optional[str], trace_name: Optional[str]) -> Tuple[Any, Any]:
        """创建 Langfuse 跟踪

        Args:
            trace_id: 跟踪 ID
            trace_name: 跟踪名称

        Returns:
            跟踪对象和生成对象
        """
        if not (self.base_client.langfuse_enabled and self.base_client.langfuse):
            return None, None

        # 创建跟踪
        if trace_id:
            trace = self.base_client.langfuse.trace(id=trace_id, name=trace_name or "LLM 调用")
        else:
            trace = self.base_client.langfuse.trace(name=trace_name or "LLM 调用")

        return trace, None

    def create_generation(
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

    def record_result(self, trace: Any, generation: Any, response: Any) -> None:
        """记录 Langfuse 结果

        Args:
            trace: 跟踪对象
            generation: 生成对象
            response: LLM 响应
        """
        if not (trace and generation and self.base_client.langfuse_enabled):
            return

        generation.end(
            output=self.utils_client._get_content_from_response(response),
            metadata={
                "finish_reason": self.utils_client._get_finish_reason(response),
                "usage": getattr(response, "usage", response.get("usage", {})),
            },
        )

    def record_error(self, trace: Any, generation: Any, error: str) -> None:
        """记录 Langfuse 错误

        Args:
            trace: 跟踪对象
            generation: 生成对象
            error: 错误信息
        """
        if not (trace and generation and self.base_client.langfuse_enabled):
            return

        generation.end(error=error)

    def track_completion(
        self,
        model_name: str,
        messages: List[Dict[str, str]],
        truncated_messages: List[Dict[str, str]],
        temp: float,
        tokens: int,
        trace_id: Optional[str] = None,
        trace_name: Optional[str] = None,
    ) -> Tuple[Any, Any, float]:
        """跟踪 LLM 完成请求

        Args:
            model_name: 模型名称
            messages: 原始消息列表
            truncated_messages: 截断后的消息列表
            temp: 温度
            tokens: 最大 token 数
            trace_id: Langfuse 跟踪 ID
            trace_name: Langfuse 跟踪名称

        Returns:
            跟踪对象、生成对象和开始时间
        """
        start_time = time.time()
        trace, generation = self.create_trace(trace_id, trace_name)
        generation = self.create_generation(trace, model_name, truncated_messages, temp, tokens)

        return trace, generation, start_time
