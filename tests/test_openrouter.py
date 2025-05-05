"""测试 OpenRouter 连接的简单脚本"""

# 启用更详细的日志
import logging
import os
import sys
from typing import Any, Tuple

import litellm
from dotenv import load_dotenv

logging.basicConfig(level=logging.DEBUG)

# 加载环境变量
load_dotenv()


def setup_litellm() -> Tuple[str, str]:
    """设置 LiteLLM 客户端

    Returns:
        tuple[str, str]: 模型名称和 API 密钥
    """
    # 获取 API 密钥
    api_key = os.getenv("LLM_API_KEY")
    model = os.getenv("LLM_MODEL")

    if not api_key:
        print("错误: 未找到 LLM_API_KEY 环境变量")
        return "", ""

    if not model:
        print("错误: 未找到 LLM_MODEL 环境变量")
        return "", ""

    # 确保模型名称包含提供商前缀
    if model and "/" in model and not model.startswith("openrouter/"):
        model = f"openrouter/{model}"

    print(f"使用模型: {model}")
    print(f"API 密钥: {api_key[:8]}...{api_key[-4:]}")

    # 设置 litellm
    litellm.api_key = api_key

    # 添加更多调试信息
    print("\n调试信息:")
    print(f"Python 版本: {sys.version}")
    # 使用 getattr 安全地获取版本
    print(f"LiteLLM 版本: {getattr(litellm, '__version__', '未知')}")

    # 检查 OpenRouter 的 URL
    openrouter_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    print(f"OpenRouter URL: {openrouter_url}")

    # 设置 OpenRouter 的 URL
    litellm.api_base = openrouter_url

    # 设置 HTTP 头信息
    litellm.headers = {
        "HTTP-Referer": "http://localhost:3000",  # 你的网站 URL
        "X-Title": "Codebase Knowledge Builder",  # 你的应用名称
    }

    return model, api_key


def _extract_from_object(response: Any) -> str:
    """从对象类型的响应中提取内容

    Args:
        response: 对象类型的响应

    Returns:
        str: 提取的内容
    """
    content = ""
    if not hasattr(response, "choices"):
        return content

    choices = getattr(response, "choices", [])
    if not choices or len(choices) == 0:
        return content

    first_choice = choices[0]
    if hasattr(first_choice, "message") and hasattr(getattr(first_choice, "message", None), "content"):
        content = getattr(getattr(first_choice, "message"), "content", "")
    elif hasattr(first_choice, "text"):
        content = getattr(first_choice, "text", "")

    return content


def _extract_from_dict(response: dict) -> str:
    """从字典类型的响应中提取内容

    Args:
        response: 字典类型的响应

    Returns:
        str: 提取的内容
    """
    content = ""
    if not isinstance(response, dict) or "choices" not in response:
        return content

    choices = response.get("choices", [])
    if not choices or len(choices) == 0:
        return content

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        return content

    if "message" in first_choice and "content" in first_choice.get("message", {}):
        content = first_choice["message"]["content"]
    elif "text" in first_choice:
        content = first_choice["text"]

    return content


def extract_content_from_response(response: Any) -> str:
    """从响应中提取内容

    Args:
        response: LLM 响应

    Returns:
        str: 提取的内容
    """
    try:
        # 处理对象类型的响应
        if hasattr(response, "choices"):
            return _extract_from_object(response)

        # 处理字典类型的响应
        elif isinstance(response, dict):
            return _extract_from_dict(response)

    except Exception as e:
        print(f"解析响应时出错: {str(e)}")

    return ""


def test_openrouter_connection() -> bool:
    """测试 OpenRouter 连接

    Returns:
        bool: 连接是否成功
    """
    # 设置 LiteLLM
    model, api_key = setup_litellm()
    if not model or not api_key:
        return False

    try:
        # 尝试一个简单的调用
        messages = [{"role": "user", "content": "Hello, world!"}]

        print("\n尝试调用 OpenRouter API...")
        response = litellm.completion(model=model, messages=messages, max_tokens=10)

        print("API 调用成功!")
        print(f"响应类型: {type(response)}")
        print(f"响应内容: {response}")

        # 提取响应内容
        content = extract_content_from_response(response)
        if content:
            print(f"响应文本: {content}")
        else:
            print("无法从响应中提取文本内容")

        return True
    except Exception as e:
        print(f"API 调用失败: {str(e)}")
        return False


if __name__ == "__main__":
    success = test_openrouter_connection()
    sys.exit(0 if success else 1)
