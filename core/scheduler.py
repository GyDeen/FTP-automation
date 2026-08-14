"""
Task scheduler — runs actions by cron expression or fixed interval.
"""
import time
from datetime import datetime
from typing import Callable
from utils.logger import get_logger

logger = get_logger("scheduler")


class TaskScheduler:
    """Lightweight task scheduler with cron-style and interval modes."""

    def __init__(self):
        self._tasks: list[dict] = []
        self._running = False

    def every(self, seconds: float, action: Callable, name: str = ""):
        """Schedule an action at a fixed interval."""
        self._tasks.append({
            "type": "interval",
            "interval": seconds,
            "action": action,
            "name": name or f"task-{len(self._tasks)}",
            "last_run": 0.0,
        })
        return self

    def cron(self, expr: str, action: Callable, name: str = ""):
        """Schedule an action using a simple cron expression (minute hour day month weekday)."""
        self._tasks.append({
            "type": "cron",
            "expr": expr,
            "action": action,
            "name": name or f"task-{len(self._tasks)}",
        })
        return self

    def start(self):
        """Start the scheduler synchronously and block until stopped."""
        self._running = True
        logger.info("Scheduler started with %d task(s)", len(self._tasks))
        try:
            while self._running:
                now = time.time()
                dt = datetime.now()
                for task in self._tasks:
                    if task["type"] == "interval":
                        if now - task.get("last_run", 0) >= task["interval"]:
                            self._run(task)
                    elif task["type"] == "cron":
                        if self._match_cron(task["expr"], dt):
                            if not task.get("_ran_this_minute"):
                                self._run(task)
                                task["_ran_this_minute"] = True
                    time.sleep(0)
                time.sleep(1)
                # Reset the per-minute execution marker.
                if dt.second == 0:
                    for t in self._tasks:
                        t["_ran_this_minute"] = False
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        self._running = False
        logger.info("Scheduler stopped")

    def _run(self, task: dict):
        try:
            logger.info("Running task: %s", task["name"])
            task["action"]()
            task["last_run"] = time.time()
        except Exception as exc:
            logger.error("Task %s failed: %s", task["name"], exc)

    @staticmethod
    def _match_cron(expr: str, dt: datetime) -> bool:
        """Match five space-separated fields, with * matching any value."""
        parts = expr.strip().split()
        if len(parts) != 5:
            return False
        fields = [dt.minute, dt.hour, dt.day, dt.month, dt.isoweekday()]
        for spec, val in zip(parts, fields):
            if spec != "*" and spec != str(val):
                return False
        return True
