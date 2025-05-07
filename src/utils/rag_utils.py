"""RAG 工具模块，提供检索增强生成相关的工具函数。"""

from typing import List

from .logger import log_and_notify


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200, smart_chunking: bool = True) -> List[str]:
    """将文本分割成适合嵌入和检索的块

    Args:
        text: 要分割的文本
        chunk_size: 块大小（字符数）
        overlap: 块重叠大小（字符数）
        smart_chunking: 是否使用智能分块（尊重代码和文档的自然边界）

    Returns:
        文本块列表
    """
    # 如果文本为空，直接返回空列表
    if not text:
        return []

    # 如果文本长度小于块大小，直接返回
    if len(text) <= chunk_size:
        return [text]

    chunks = []

    # 根据是否启用智能分块选择不同的分块策略
    if smart_chunking:
        # 智能分块：尊重代码和文档的自然边界
        chunks = _smart_chunk_text(text, chunk_size, overlap)
    else:
        # 简单分块：按固定大小分割
        chunks = _simple_chunk_text(text, chunk_size, overlap)

    return chunks


def _smart_chunk_text(text: str, chunk_size: int, overlap: int) -> List[str]:
    """智能分块：尊重代码和文档的自然边界

    Args:
        text: 要分割的文本
        chunk_size: 块大小
        overlap: 块重叠大小

    Returns:
        文本块列表
    """
    chunks = []

    # 首先按段落分割，保持文本的自然结构
    paragraphs = text.split("\n\n")
    current_chunk = []
    current_size = 0

    for para in paragraphs:
        para_size = len(para)

        # 如果单个段落就超过了限制
        if para_size > chunk_size:
            # 先添加当前块（如果有）
            if current_chunk:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = []
                current_size = 0

            # 记录这个大段落需要单独处理
            log_and_notify(f"段落过长 ({para_size} 字符)，将被分割", "warning")

            # 处理大段落：按句子分割
            para_chunks = _split_paragraph_by_sentences(para, chunk_size)
            chunks.extend(para_chunks)
        else:
            # 检查添加这个段落是否会超过限制
            if current_size + para_size > chunk_size:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = [para]
                current_size = para_size
            else:
                current_chunk.append(para)
                current_size += para_size

    # 添加最后一个块
    if current_chunk:
        chunks.append("\n\n".join(current_chunk))

    return chunks


def _split_paragraph_by_sentences(paragraph: str, chunk_size: int) -> List[str]:
    """将段落按句子分割

    Args:
        paragraph: 要分割的段落
        chunk_size: 块大小

    Returns:
        分割后的文本块列表
    """
    # 按句子分割
    sentences = paragraph.split(". ")
    chunks = []
    current_chunk = []
    current_size = 0

    for sentence in sentences:
        sentence_size = len(sentence)

        if current_size + sentence_size <= chunk_size:
            current_chunk.append(sentence)
            current_size += sentence_size
        else:
            if current_chunk:
                chunks.append(". ".join(current_chunk) + ".")
                current_chunk = [sentence]
                current_size = sentence_size
            else:
                # 单个句子就超过了限制，只能截断
                log_and_notify(f"句子过长 ({sentence_size} 字符)，将被截断", "warning")
                # 使用简单的截断策略
                truncated = sentence[: int(chunk_size * 0.9)]
                chunks.append(truncated + "...")

    # 添加最后一个块
    if current_chunk:
        chunks.append(". ".join(current_chunk) + ".")

    return chunks


def _simple_chunk_text(text: str, chunk_size: int, overlap: int) -> List[str]:
    """简单分块：按固定大小分割

    Args:
        text: 要分割的文本
        chunk_size: 块大小
        overlap: 块重叠大小

    Returns:
        文本块列表
    """
    chunks = []
    start = 0

    while start < len(text):
        # 计算当前块的结束位置
        end = min(start + chunk_size, len(text))

        # 如果不是最后一个块，尝试在一个合适的位置（如换行符）结束
        if end < len(text):
            # 从 end 向前查找换行符
            pos = text.rfind("\n", start, end)
            if pos > start:
                end = pos + 1  # 包含换行符

        # 添加当前块
        chunks.append(text[start:end])

        # 更新起始位置，考虑重叠
        start = max(start + 1, end - overlap)

    return chunks
