"""workers/utils.py — Shared utilities for Celery task workers."""
from __future__ import annotations

import asyncio
import concurrent.futures


def run_async(coro, timeout: int = 30):
    """Run an async coroutine from a Celery task (sync or eager context).

    In eager mode (CELERY_TASK_ALWAYS_EAGER=True), tasks execute inside
    FastAPI's running event loop. Calling asyncio.run() there would raise
    'This event loop is already running', so we submit to a thread instead.
    """
    try:
        asyncio.get_running_loop()
        running = True
    except RuntimeError:
        running = False

    if running:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result(timeout=timeout)
    else:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
