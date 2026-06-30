"""日志配置"""

import logging
import sys
from pathlib import Path

from config.settings import log_config, paths


def setup_logger(name: str = "worldcup") -> logging.Logger:
    """
    创建带控制台和文件输出的 logger。

    Args:
        name: logger 名称

    Returns:
        配置好的 Logger 实例
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, log_config.LEVEL.upper(), logging.INFO))

    # 格式
    formatter = logging.Formatter(
        log_config.FORMAT,
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 控制台 handler
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    logger.addHandler(console)

    # 文件 handler
    log_path = Path(log_config.FILE_PATH)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


def get_logger(name: str = "worldcup") -> logging.Logger:
    """获取已有的 logger，如不存在则创建"""
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger = setup_logger(name)
    return logger
