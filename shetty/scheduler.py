from __future__ import annotations

import asyncio
import logging

from .db import Store
from .tools import ToolError, Tools

logger = logging.getLogger(__name__)


async def tick(store: Store, tools: Tools) -> int:
    due = store.claim_due_tasks()
    for task in due:
        try:
            await tools.notify(task["title"])
        except ToolError:
            store.event("error", "Desktop notification unavailable", "Your reminder is still visible in Tasks and Activity.")
    return len(due)


async def run_scheduler(store: Store, tools: Tools, interval: float) -> None:
    while True:
        try:
            await tick(store, tools)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Reminder tick failed; the next tick will retry unclaimed reminders")
        await asyncio.sleep(interval)
