"""
DaysHub 定时任务调度器 v1.3.0
- 每小时检查事件提醒（按每个事件单独的 advance_days）
- 自动备份与日志清理（支持动态时间与数量设置）
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from config import Config, load_backup_config
from logger import logger

import logging
logging.getLogger("apscheduler").setLevel(logging.WARNING)

_global_scheduler = None


def reschedule_backup(app):
    """根据最新配置重新调度每日备份任务"""
    global _global_scheduler
    if not _global_scheduler:
        return
    cfg = load_backup_config()
    job_id = "daily_maintenance"

    if not cfg.get("backup_enabled", True):
        try:
            _global_scheduler.remove_job(job_id)
            logger.info("自动备份已禁用，已移除调度任务")
        except Exception:
            pass
        return

    b_time = cfg.get("backup_time", "03:00")
    try:
        hour_s, min_s = b_time.split(":")
        hour, minute = int(hour_s), int(min_s)
    except Exception:
        hour, minute = 3, 0

    def daily_maintenance():
        with app.app_context():
            from models import backup_database, cleanup_old_logs
            c = load_backup_config()
            cnt = int(c.get("backup_count", 30))
            logger.info(f"执行每日维护任务：自动备份(保留{cnt}份)与日志清理...")
            backup_database(max_backups=cnt)
            deleted = cleanup_old_logs(retention_days=90)
            if deleted > 0:
                logger.info(f"清理了 {deleted} 条过期通知日志")

    _global_scheduler.add_job(
        daily_maintenance,
        CronTrigger(hour=hour, minute=minute),
        id=job_id,
        replace_existing=True
    )
    logger.info(f"自动备份任务已重新调度至每日 {hour:02d}:{minute:02d}")


def create_scheduler(app) -> BackgroundScheduler:
    global _global_scheduler
    scheduler = BackgroundScheduler(timezone=Config.TIMEZONE)
    _global_scheduler = scheduler

    def hourly_check():
        with app.app_context():
            from notifier import check_and_notify
            check_and_notify()

    # 1. 每小时检查一次是否有事件需要提醒
    scheduler.add_job(hourly_check, CronTrigger(minute=0),
                      id="hourly_check", replace_existing=True)

    # 2. 调度自动备份与维护
    reschedule_backup(app)

    scheduler.start()
    logger.info("调度器已启动 — 包含事件检查与自动备份")
    return scheduler