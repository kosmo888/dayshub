"""
DaysHub 日志框架 — 控制台输出 + 持久化运行日志轮转
"""
import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from config import Config

logger = logging.getLogger("dayshub")
logger.setLevel(logging.DEBUG if not Config.is_production() else logging.INFO)

if not logger.handlers:
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 1. 控制台标准输出
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)
    logger.addHandler(stdout_handler)

    # 2. 持久化文件日志 (写入 data/dayshub.log，单文件上限 5MB，自动保留 3 个备份)
    try:
        os.makedirs(Config.DATA_DIR, exist_ok=True)
        log_file = os.path.join(Config.DATA_DIR, "dayshub.log")
        file_handler = RotatingFileHandler(
            log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"[LOGGER INIT ERROR] 无法初始化文件日志: {e}")
