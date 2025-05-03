"""Token 工具模块，提供 token 计数和处理相关功能。"""

from typing import Dict, List

import litellm

from ..logger import log_and_notify


def count_tokens(text: str, model: str) -> int:
    """计算文本的token数量

    完全依赖litellm的token计数功能，litellm会自动选择合适的tokenizer。

    Args:
        text: 要计算的文本
        model: 模型名称

    Returns:
        token数量
    """
    if not text:
        return 0

    try:
        # 使用litellm的token计数功能
        # 创建一个包含文本的消息列表
        messages = [{"role": "user", "content": text}]

        # 使用litellm的completion函数的_hidden_params来获取token数量
        # 设置max_tokens=1以最小化实际生成的token数量
        response = litellm.completion(
            model=model,
            messages=messages,
            max_tokens=1,
            mock_response="",  # 使用mock_response避免实际调用API
        )

        # 从响应中获取token数量
        usage = getattr(response, "usage", None)
        if usage:
            return usage.prompt_tokens

        # 如果无法获取token数量，使用备用方法
        raise Exception("无法从响应中获取token数量")
    except Exception as e:
        log_and_notify(f"计算token数失败: {str(e)}", "error")
        # 使用简单的估算方法作为后备
        # 注意：这只是一个粗略估计，不同语言和模型的token比例会有很大差异
        # 中文约为1个字符/token，英文约为4个字符/token
        is_mainly_chinese = len([c for c in text if "\u4e00" <= c <= "\u9fff"]) > len(text) / 3
        if is_mainly_chinese:
            return len(text)  # 中文大约1字符/token
        else:
            return len(text) // 4  # 英文大约4字符/token


def count_message_tokens(messages: List[Dict[str, str]], model: str) -> int:
    """计算消息列表的token数量

    完全依赖litellm的token计数功能，litellm会自动选择合适的tokenizer。

    Args:
        messages: 消息列表
        model: 模型名称

    Returns:
        token数量
    """
    if not messages:
        return 0

    try:
        # 使用litellm的completion函数的_hidden_params来获取token数量
        # 设置max_tokens=1以最小化实际生成的token数量
        response = litellm.completion(
            model=model,
            messages=messages,
            max_tokens=1,
            mock_response="",  # 使用mock_response避免实际调用API
        )

        # 从响应中获取token数量
        usage = getattr(response, "usage", None)
        if usage:
            return usage.prompt_tokens

        # 如果无法获取token数量，使用备用方法
        raise Exception("无法从响应中获取token数量")
    except Exception as e:
        log_and_notify(f"计算消息token数失败: {str(e)}", "error")
        # 使用简单的估算方法作为后备
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            # 检测是否主要是中文
            is_mainly_chinese = len([c for c in content if "\u4e00" <= c <= "\u9fff"]) > len(content) / 3
            if is_mainly_chinese:
                total += len(content)  # 中文大约1字符/token
            else:
                total += len(content) // 4  # 英文大约4字符/token
        # 添加消息格式开销
        total += 4 * len(messages)  # 每条消息有额外开销
        return total


def truncate_messages_if_needed(
    messages: List[Dict[str, str]], max_input_tokens: int, model: str, split_text_func=None
) -> List[Dict[str, str]]:
    """如果需要，截断消息以适应最大输入token限制

    使用简化的逻辑，保留系统消息和最新的非系统消息。

    Args:
        messages: 消息列表
        max_input_tokens: 最大输入token数
        model: 模型名称
        split_text_func: 文本分块函数，用于截断单条消息

    Returns:
        可能被截断的消息列表
    """
    if not messages:
        return []

    try:
        # 计算当前消息的token数
        total_tokens = count_message_tokens(messages, model)

        # 如果没有超过限制，直接返回原始消息
        if total_tokens <= max_input_tokens:
            return messages

        # 记录警告
        log_and_notify(f"输入token数({total_tokens})超过限制({max_input_tokens})，将进行截断", "warning")

        # 分离系统消息和非系统消息
        system_messages = [m for m in messages if m.get("role") == "system"]
        non_system_messages = [m for m in messages if m.get("role") != "system"]

        # 如果没有系统消息，只保留最新的非系统消息
        if not system_messages:
            return truncate_non_system_messages(non_system_messages, max_input_tokens, model, split_text_func)
        else:
            # 如果有系统消息，保留系统消息和尽可能多的最新非系统消息
            system_tokens = count_message_tokens(system_messages, model)
            remaining_tokens = max_input_tokens - system_tokens

            # 如果系统消息已经超过限制，只保留第一个系统消息
            if remaining_tokens <= 0:
                return [system_messages[0]]

            # 截断非系统消息
            truncated_non_system = truncate_non_system_messages(
                non_system_messages, remaining_tokens, model, split_text_func
            )
            return system_messages + truncated_non_system

    except Exception as e:
        # 如果token计数失败，记录错误并返回原始消息
        log_and_notify(f"计算token数失败: {str(e)}，将使用原始消息", "error")
        return messages


def truncate_non_system_messages(
    messages: List[Dict[str, str]], max_tokens: int, model: str, split_text_func=None
) -> List[Dict[str, str]]:
    """截断非系统消息

    从最新的消息开始保留，直到达到token限制。

    Args:
        messages: 非系统消息列表
        max_tokens: 最大token数
        model: 模型名称
        split_text_func: 文本分块函数，用于截断单条消息

    Returns:
        截断后的消息列表
    """
    if not messages:
        return []

    # 从最新的消息开始保留
    truncated_messages = []
    current_tokens = 0

    for msg in reversed(messages):
        msg_tokens = count_message_tokens([msg], model)

        # 如果添加这条消息不会超过限制
        if current_tokens + msg_tokens <= max_tokens:
            truncated_messages.insert(0, msg)
            current_tokens += msg_tokens
        else:
            # 如果单条消息就超过限制且还没有保留任何消息，则截断这条消息
            if not truncated_messages and split_text_func:
                content = msg.get("content", "")
                # 使用文本分块方法
                chunks = split_text_func(content, max_tokens)
                if chunks:
                    truncated_msg = msg.copy()
                    truncated_msg["content"] = chunks[0] + "...[内容已截断]"
                    truncated_messages.insert(0, truncated_msg)
            break

    return truncated_messages
