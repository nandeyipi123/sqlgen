"""
轻量日志模块
============
所有模块通过 get_logger(__name__) 获取 logger，
日志统一写入 app/app.log。
"""
import logging
import os
import sys

_LOG_DIR = os.path.dirname(os.path.abspath(__file__))
_LOG_FILE = os.path.join(_LOG_DIR, "app.log")


def get_logger(name: str) -> logging.Logger:
    """获取模块级 logger，同时输出到文件和 stderr"""
    logger = logging.getLogger(name)

    # 防止重复添加 handler
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # 文件 handler
    fh = logging.FileHandler(_LOG_FILE, encoding='utf-8')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)-5s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    logger.addHandler(fh)

    # 控制台 handler (WARNING 以上)
    ch = logging.StreamHandler(sys.stderr)
    ch.setLevel(logging.WARNING)
    ch.setFormatter(logging.Formatter(
        '[%(levelname)s] %(name)s: %(message)s'
    ))
    logger.addHandler(ch)

    return logger


def get_log_path() -> str:
    """返回日志文件路径，方便调试"""
    return _LOG_FILE
