"""日志记录模块，提供统一的日志记录和用户通知机制。"""

# 导入日志配置
from ..logging_config import configure_logging

# 配置日志并获取应用程序日志记录器
logger = configure_logging()


def log_and_notify(message: str, level: str = "info", notify: bool = False) -> None:
    """记录日志并可选择通知用户

    Args:
        message: 消息内容
        level: 日志级别 (info, warning, error)
        notify: 是否通知用户
    """
    # 根据级别记录日志
    if level == "warning":
        logger.warning(message)
    elif level == "error":
        logger.error(message)
    else:
        logger.info(message)

    # 如果需要通知用户，可以在这里实现
    if notify:
        # 这里可以实现用户通知逻辑，如发送邮件、显示通知等
        print(f"[通知] {message}")
