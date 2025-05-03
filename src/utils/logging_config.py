"""日志配置模块，用于配置日志级别和格式。"""

import logging


def configure_logging():
    """配置日志级别和格式"""
    # 配置根日志记录器
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # 设置LiteLLM日志级别为WARNING，禁用INFO级别日志
    # 尝试多种可能的日志记录器名称，确保覆盖所有情况
    logging.getLogger("litellm").setLevel(logging.WARNING)
    logging.getLogger("LiteLLM").setLevel(logging.WARNING)
    logging.getLogger("litellm.llms").setLevel(logging.WARNING)
    logging.getLogger("litellm.utils").setLevel(logging.WARNING)

    # 设置httpx日志级别为WARNING，禁用INFO级别日志
    logging.getLogger("httpx").setLevel(logging.WARNING)

    # 设置其他可能的日志记录器级别
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("anthropic").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    # 获取应用程序日志记录器
    logger = logging.getLogger("codebase-knowledge-builder")

    return logger
