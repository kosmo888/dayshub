"""
DaysHub 定时任务调度器 v1.2.0
- 每小时检查事件提醒（按每个事件单独的 advance_days）
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from config import Config
from logger import logger

import logging
logging.getLogger("apscheduler").setLevel(logging.WARNING)


def create_scheduler(app) -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone=Config.TIMEZONE)

    def hourly_check():
        with app.app_context():
            from notifier import check_and_notify
            check_and_notify()

    # 每小时检查一次是否有事件需要提醒
    scheduler.add_job(hourly_check, CronTrigger(minute=0),
                      id="hourly_check", replace_existing=True)

    scheduler.start()
    logger.info("调度器已启动 — 每小时检查事件提醒")
    return scheduler