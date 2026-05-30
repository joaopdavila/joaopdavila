from __future__ import annotations

"""Scheduler unificado (APScheduler). Registra os jobs garmin_* no fuso
configurado. Outros domínios (checkin/fechamento/revisão) entram aqui nas
próximas fases."""

import argparse
import asyncio
import logging
from dataclasses import dataclass
from typing import Awaitable, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import Settings
from app.jobs import (
    garmin_alerts,
    garmin_evening_report,
    garmin_morning_report,
    garmin_sync_morning,
    garmin_weekly,
)

log = logging.getLogger(__name__)

JobFn = Callable[[object, Settings], Awaitable[None]]


@dataclass(frozen=True)
class JobSpec:
    name: str
    fn: JobFn
    trigger_kwargs: dict


def _job_specs() -> list[JobSpec]:
    return [
        JobSpec("garmin_sync_morning", garmin_sync_morning.run, {"hour": 6, "minute": 30}),
        JobSpec("garmin_morning_report", garmin_morning_report.run, {"hour": 7, "minute": 30}),
        JobSpec("garmin_evening_report", garmin_evening_report.run, {"hour": 19, "minute": 0}),
        JobSpec("garmin_alerts", garmin_alerts.run, {"hour": "8,14,20", "minute": 0}),
        JobSpec("garmin_weekly", garmin_weekly.run, {"day_of_week": "sun", "hour": 17, "minute": 55}),
    ]


def build_scheduler(application, settings: Settings) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=settings.timezone)
    for spec in _job_specs():
        trigger = CronTrigger(timezone=settings.timezone, **spec.trigger_kwargs)
        scheduler.add_job(
            spec.fn,
            trigger=trigger,
            args=[application, settings],
            id=spec.name,
            name=spec.name,
            misfire_grace_time=600,
            coalesce=True,
        )
    log.info("scheduler configured with %d jobs", len(_job_specs()))
    return scheduler


def list_jobs() -> list[str]:
    return [s.name for s in _job_specs()]


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="cpf-assistant scheduler tools")
    parser.add_argument("--list", action="store_true", help="list configured jobs")
    parser.add_argument("--run", metavar="JOB", help="run one job once and exit")
    args = parser.parse_args(argv)

    settings = Settings.load()
    logging.basicConfig(level=getattr(logging, settings.log_level, logging.INFO))

    if args.list:
        for spec in _job_specs():
            print(f"{spec.name}: {spec.trigger_kwargs}")
        return 0

    if args.run:
        spec = next((s for s in _job_specs() if s.name == args.run), None)
        if spec is None:
            print(f"unknown job: {args.run}. available: {', '.join(list_jobs())}")
            return 2
        from app.bot import build_application

        async def _run_once() -> None:
            application = build_application(settings)
            await application.initialize()
            try:
                await spec.fn(application, settings)
            finally:
                await application.shutdown()

        asyncio.run(_run_once())
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
