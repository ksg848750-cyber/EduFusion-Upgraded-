import asyncio
import sys


def selector_loop_factory() -> asyncio.AbstractEventLoop:
    """Return a SelectorEventLoop, required by psycopg's async pool on Windows.

    Uvicorn 0.36+ invokes this through `--loop app.loop:selector_loop_factory`
    (see backend/run.py). On non-Windows platforms the default loop is already
    compatible, so we delegate to asyncio's normal factory.
    """
    if sys.platform == "win32":
        return asyncio.SelectorEventLoop()
    return asyncio.new_event_loop()