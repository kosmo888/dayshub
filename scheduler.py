"""
DaysHub 定时任务调度器 v1.4.0
- 每小时检查事件提醒（按每个事件单独的 advance_days）
- 自动备份与日志清理（支持动态时间、数量与备份间隔天数设置）
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from config import Config, load_backup_config
from logger import logger

import logging
logging.getLogger("apscheduler").setLevel(logging.WARNING)

_global_scheduler = None


def _backup_due(app) -> bool:
    """判断今天是否到达备份日（间隔天数逻辑）"""
    with app.app_context():
        from models import get_setting
        from datetime import date
        try:
            interval = int(get_setting("backup_interval_days", "1") or 1)
        except (ValueError, TypeError):
            interval = 1
        if interval <= 1:
            return True
        last_str = get_setting("last_auto_backup_date", "")
        today = date.today()
        if not last_str:
            return True
        try:
            from datetime import datetime
            last_date = datetime.strptime(str(last_str), "%Y-%m-%d").date()
            return (today - last_date).days >= interval
        except ValueError:
            return True


def reschedule_backup(app):
    """根据最新配置重新调度自动备份任务（支持每 N 天备份一次）"""
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
    interval_days = int(cfg.get("backup_interval_days", 1) or 1)
    try:
        hour_s, min_s = b_time.split(":")
        hour, minute = int(hour_s), int(min_s)
    except Exception:
        hour, minute = 3, 0

    def daily_maintenance():
        with app.app_context():
            from models import backup_database, cleanup_old_logs, set_setting
            c = load_backup_config()
            cnt = int(c.get("backup_count", 30))
            interval = int(c.get("backup_interval_days", 1) or 1)

            # 间隔天数判定：非备份日仅执行日志清理，跳过备份
            if interval > 1:
                from models import get_setting
                from datetime import date, datetime
                last_str = get_setting("last_auto_backup_date", "")
                today = date.today()
                skip = False
                if last_str:
                    try:
                        last_date = datetime.strptime(str(last_str), "%Y-%m-%d").date()
                        if (today - last_date).days < interval:
                            skip = True
                    except ValueError:
                        pass
                if skip:
                    deleted = cleanup_old_logs(retention_days=90)
                    if deleted > 0:
                        logger.info(f"今日非备份日(每{interval}天一次)，仅清理 {deleted} 条过期日志")
                    else:
                        logger.info(f"今日非备份日(每{interval}天一次)，跳过自动备份")
                    return

            logger.info(f"执行自动维护任务：自动备份(保留{cnt}份)与日志清理...")
            backup_database(max_backups=cnt)
            from datetime import date as _date
            set_setting("last_auto_backup_date", _date.today().strftime("%Y-%m-%d"))
            deleted = cleanup_old_logs(retention_days=90)
            if deleted > 0:
                logger.info(f"清理了 {deleted} 条过期通知日志")

    _global_scheduler.add_job(
        daily_maintenance,
        CronTrigger(hour=hour, minute=minute),
        id=job_id,
        replace_existing=True
    )
    if interval_days > 1:
        logger.info(f"自动备份任务已重新调度：每日 {hour:02d}:{minute:02d} 触发，每 {interval_days} 天实际备份一次")
    else:
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