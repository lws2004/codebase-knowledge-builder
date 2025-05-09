"""测试配置文件，提供共享的fixture"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# 确保当前目录在 Python 路径中
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.utils.llm_wrapper.llm_client import LLMClient


@pytest.fixture
def mock_env_vars():
    """模拟环境变量"""
    with patch.dict(
        os.environ,
        {
            "LLM_PROVIDER": "openai",
            "LLM_MODEL": "gpt-4",
            "LLM_API_KEY": "test-key",
            "OPENAI_API_KEY": "test-key",
        },
        clear=True,
    ):
        yield


@pytest.fixture
def mock_litellm_completion():
    """模拟litellm.completion函数"""
    with patch("litellm.completion") as mock_completion:
        # 设置模拟响应
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "这是一个测试回答"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15
        mock_completion.return_value = mock_response
        yield mock_completion


@pytest.fixture
def mock_litellm_acompletion():
    """模拟litellm.acompletion函数"""
    with patch("litellm.acompletion") as mock_acompletion:
        # 设置模拟响应
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "这是一个测试回答"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15
        mock_acompletion.return_value = mock_response
        yield mock_acompletion


@pytest.fixture
def llm_client():
    """创建LLM客户端实例"""
    config = {
        "provider": "openai",
        "model": "gpt-4",
        "api_key": "test-key",
        "max_tokens": 1000,
        "max_input_tokens": 4000,
        "temperature": 0.7,
    }
    with patch("src.utils.llm_wrapper.llm_client.litellm"):
        with patch("src.utils.llm_wrapper.llm_client.Langfuse"):
            client = LLMClient(config)
            yield client


@pytest.fixture
def mock_token_counter():
    """模拟token计数函数"""
    with patch("src.utils.llm_wrapper.token_utils.count_tokens", return_value=10) as mock_count_tokens:
        with patch(
            "src.utils.llm_wrapper.token_utils.count_message_tokens", return_value=15
        ) as mock_count_message_tokens:
            yield mock_count_tokens, mock_count_message_tokens


@pytest.fixture
def test_messages():
    """测试消息列表"""
    return [
        {"role": "system", "content": "你是一个有用的助手"},
        {"role": "user", "content": "你好，请帮我解释一下Python中的装饰器"},
    ]


@pytest.fixture
def test_long_text():
    """测试长文本"""
    return """这是第一段落，用于测试文本分块功能。这段文字应该足够长，以便能够测试分块功能。

这是第二段落，它与第一段落之间有一个空行，这应该会影响分块的结果。我们希望测试工具能够正确处理段落之间的空行。

这是第三段落，它包含了一些代码示例：
```python
def hello_world():
    print("Hello, World!")
```

这段代码应该被视为一个整体，而不应该在代码块内部进行分割。"""


@pytest.fixture
def mock_config_loader():
    """模拟配置加载器"""
    mock_loader = MagicMock()
    mock_loader.get_config.return_value = {
        "app": {"name": "codebase-knowledge-builder"},
        "llm": {"provider": "openai", "model": "gpt-4"},
        "nodes": {
            "analyze_repo": {"max_files": 100},
            "analyze_history": {"max_commits": 50},
        },
    }
    mock_loader.get.side_effect = lambda key, default=None: {
        "app.name": "codebase-knowledge-builder",
        "llm.provider": "openai",
        "llm.model": "gpt-4",
    }.get(key, default)
    mock_loader.get_node_config.return_value = {"max_commits": 50}
    return mock_loader
