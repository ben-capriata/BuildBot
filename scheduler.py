import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from handlers.plan import generate_plan_for_scheduler

logger = logging.getLogger(__name__)


def start_scheduler(bot, chat_id):
    """Start the APScheduler with a daily 18:30 AST cron job."""
    scheduler = AsyncIOScheduler()

    def _run_plan():
        asyncio.get_event_loop().create_task(
            generate_plan_for_scheduler(bot, chat_id)
        )

    scheduler.add_job(
        _run_plan,
        CronTrigger(hour=18, minute=30, timezone="America/Port_of_Spain"),
        id="daily_plan",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started — daily plan at 18:30 AST")
    return scheduler
