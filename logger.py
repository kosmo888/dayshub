"""
DaysHub 日志框架 — 替换所有 print
"""
import logging
import sys
from config import Config

logger = logging.getLogger("dayshub")
logger.setLevel(logging.DEBUG if not Config.is_production() else logging.INFO)

if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        "[%(asctime)s] %(levelname)s %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))
    logger.addHandler(handler)