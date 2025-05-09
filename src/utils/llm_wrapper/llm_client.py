"""LLM 客户端，提供统一的 LLM 调用接口。"""

import os  # For __main__ example
from typing import Any, Dict, List, Optional, cast

from .llm_client_async import LLMClientAsync
from .llm_client_base import LLMClientBase
from .llm_client_langfuse import LLMClientLangfuse
from .llm_client_sync import LLMClientSync
from .llm_client_utils import LLMClientUtils

# Attempt to import for __main__ block. This might require path adjustments or a mock.
# If this util is run standalone, relative imports for logger/config might fail.
# We will use a simple print logger in __main__ to avoid this complexity for demonstration.
# from ...utils.logger import log_and_notify
# from ...utils.env_manager import get_llm_config


class LLMClient:
    """LLM 客户端，提供统一的 LLM 调用接口"""

    def __init__(self, config: Dict[str, Any]):
        """初始化 LLM 客户端

        Args:
            config: LLM 配置
        """
        # 初始化各个组件
        self.base = LLMClientBase(config)
        self.utils = LLMClientUtils(self.base)
        self.langfuse = LLMClientLangfuse(self.base, self.utils)
        self.sync = LLMClientSync(self.base, self.utils, self.langfuse)
        self.async_client = LLMClientAsync(self.base, self.utils, self.langfuse)

    # 代理方法 - 基础功能
    def _get_model_string(self) -> str:
        """获取模型字符串"""
        return self.base._get_model_string()

    # 代理方法 - 工具功能
    def count_tokens(self, text: str) -> int:
        """计算文本的token数量"""
        return self.utils.count_tokens(text)

    def count_message_tokens(self, messages: List[Dict[str, str]]) -> int:
        """计算消息列表的token数量"""
        return self.utils.count_message_tokens(messages)

    def split_text_to_chunks(self, text: str, max_tokens: int) -> List[str]:
        """将文本分割成不超过最大token数的块"""
        return self.utils.split_text_to_chunks(text, max_tokens)

    def get_completion_content(self, response: Any) -> str:
        """从 LLM 响应中获取内容"""
        return self.utils.get_completion_content(response)

    # 代理方法 - 同步调用
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
        """同步调用 LLM 完成请求"""
        return self.sync.completion(messages, temperature, max_tokens, trace_id, trace_name, model, max_input_tokens)

    def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        trace_name: Optional[str] = None,
        model: Optional[str] = None,
    ) -> str:
        """简化的文本生成方法，适用于简单的文本生成任务"""
        return self.sync.generate_text(prompt, system_prompt, temperature, max_tokens, trace_name, model)

    def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = 0.1,
        max_tokens: Optional[int] = None,
        trace_name: Optional[str] = None,
        model: Optional[str] = None,
        schema: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """生成JSON格式的响应"""
        return self.sync.generate_json(prompt, system_prompt, temperature, max_tokens, trace_name, model, schema)

    # 代理方法 - 异步调用
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
        """异步调用 LLM 完成请求"""
        return await self.async_client.acompletion(
            messages, temperature, max_tokens, trace_id, trace_name, model, max_input_tokens
        )


if __name__ == "__main__":
    import asyncio
    import os  # For __main__ example

    # --- Mock/Simplified Dependencies for standalone testing ---
    # This avoids needing the full project structure (config files, .env, actual logger)
    # when just demonstrating LLMClient.

    # Simplified logger for this test
    def test_logger(message: str, level: str = "info", notify: bool = False) -> None:
        """测试用的简单日志打印函数。"""
        print(f"[LLMClientTest][{level.upper()}] {message}")

    # Mock LLM Configuration (replace with actual get_llm_config for integration test)
    mock_llm_config = {
        "provider": os.getenv("TEST_LLM_PROVIDER", "openai"),  # Default to openai for mock
        "model": os.getenv("TEST_LLM_MODEL", "gpt-3.5-turbo"),
        "api_key": os.getenv("TEST_OPENAI_API_KEY", "sk-testkeyLLMClientMain"),  # Use a distinct test key
        "temperature": 0.7,
        "max_tokens": 150,
        "max_input_tokens": 2000,
        "cache": {"enabled": False, "ttl": 3600, "dir": ".cache/test_llm_client"},
        "langfuse": {"enabled": False},
        "logger_instance": test_logger,
    }

    print("--- LLMClient Test --- CWD:", os.getcwd())
    print(f"Using mock LLM config: {mock_llm_config['provider']}/{mock_llm_config['model']}")

    # Ensure a directory for cache if any sub-component tries to create it, even if disabled
    cache_config = cast(Dict[str, Any], mock_llm_config.get("cache", {}))
    cache_dir = cast(str, cache_config.get("dir", ".cache/test_llm_client"))
    os.makedirs(cache_dir, exist_ok=True)

    try:
        llm_client = LLMClient(config=mock_llm_config)
        test_logger("LLMClient initialized.", "info")

        # 1. Test count_tokens
        text_to_count = "Hello world, this is a test."
        token_count = llm_client.count_tokens(text_to_count)
        test_logger(f"Token count for '{text_to_count}': {token_count}", "info")
        assert token_count > 0, "Token count should be positive"

        # 2. Test generate_text (sync)
        test_logger("Attempting generate_text (sync)...", "info")
        try:
            response_text = llm_client.generate_text("What is the capital of France?", trace_name="test.generate_text")
            test_logger(f"generate_text response: {response_text}", "info")
        except Exception as e:
            test_logger(f"generate_text call failed as expected without real API/mock: {e}", "warning")

        # 3. Test acompletion (async)
        async def run_acompletion_test() -> None:
            """运行异步补全测试的辅助函数。"""
            test_logger("Attempting acompletion (async)...", "info")
            messages = [{"role": "user", "content": "Briefly, what is a large language model?"}]
            try:
                response_async = await llm_client.acompletion(messages, trace_name="test.acompletion")
                content = llm_client.get_completion_content(response_async)
                test_logger(f"acompletion response content: {content}", "info")
            except Exception as e:
                test_logger(f"acompletion call failed as expected without real API/mock: {e}", "warning")

        asyncio.run(run_acompletion_test())

    except Exception as e:
        test_logger(f"Error during LLMClient test setup or basic calls: {e}", "error")
        import traceback

        traceback.print_exc()

    print("--- LLMClient Test End ---")
