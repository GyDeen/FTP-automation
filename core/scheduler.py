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
        if seconds <= 0:
            raise ValueError("Interval must be greater than zero seconds")
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
        self._validate_cron(expr)
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
                now = time.monotonic()
                dt = datetime.now()
                minute_key = (dt.year, dt.month, dt.day, dt.hour, dt.minute)
                for task in self._tasks:
                    if task["type"] == "interval":
                        if now - task.get("last_run", 0) >= task["interval"]:
                            task["last_run"] = now
                            self._run(task)
                    elif task["type"] == "cron":
                        if (self._match_cron(task["expr"], dt)
                                and task.get("_last_cron_minute") != minute_key):
                            task["_last_cron_minute"] = minute_key
                            self._run(task)
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        self._running = False
        logger.info("Scheduler stopped")

    def _run(self, task: dict):
        try:
            logger.info("Running task: %s", task["name"])
            task["action"]()
        except Exception as exc:
            logger.error("Task %s failed: %s", task["name"], exc)

    @staticmethod
    def _match_cron(expr: str, dt: datetime) -> bool:
        """Match five space-separated fields, with * matching any value."""
        parts = expr.strip().split()
        if len(parts) != 5:
            return False
        fields = [dt.minute, dt.hour, dt.day, dt.month, dt.isoweekday() % 7]
        for index, (spec, val) in enumerate(zip(parts, fields)):
            if spec == "*":
                continue
            expected = int(spec)
            if index == 4 and expected == 7:
                expected = 0
            if expected != val:
                return False
        return True

    @staticmethod
    def _validate_cron(expr: str) -> None:
        parts = expr.strip().split()
        if len(parts) != 5:
            raise ValueError("Cron expression must contain five fields")
        ranges = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 7)]
        for spec, (minimum, maximum) in zip(parts, ranges):
            if spec == "*":
                continue
            try:
                value = int(spec)
            except ValueError as exc:
                raise ValueError(
                    "Cron fields support only '*' or a single integer"
                ) from exc
            if not minimum <= value <= maximum:
                raise ValueError(f"Cron field {value} is outside {minimum}-{maximum}")
