"""APScheduler 定时任务：周期采样 + 周期告警检查。随 FastAPI 生命周期启停。"""
from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import settings

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(timezone="Asia/Shanghai", daemon=True)


def _job_sampling() -> None:
    from app.services.scraper import scraper_service

    try:
        result = scraper_service.run_due_tasks()
        logger.info("采样完成: %s", result)
    except Exception as exc:
        logger.error("周期采样失败: %s", exc)


def _job_alerts() -> None:
    from app.services.notifier import check_all_brands

    try:
        created = check_all_brands()
        logger.info("告警检查完成，新建告警品牌: %s", created)
    except Exception as exc:
        logger.error("告警检查失败: %s", exc)


def start_scheduler() -> None:
    if scheduler.running:
        return
    scheduler.add_job(_job_sampling, "interval", minutes=settings.sampling_interval_minutes,
                      id="geo_sampling", max_instances=1, coalesce=True)
    scheduler.add_job(_job_alerts, "interval", hours=6,
                      id="geo_alerts", max_instances=1, coalesce=True)
    scheduler.start()
    logger.info("调度器已启动")


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("调度器已停止")
