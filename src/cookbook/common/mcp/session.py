"""Run sync service code for a tool, with its own session, in a worker thread.

Services are synchronous; calling them on the event loop would block every
other request. Each call gets a fresh session that is always closed, which
rolls back anything the service didn't commit.
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Concatenate

import anyio.to_thread
from sqlalchemy.orm import Session, sessionmaker


class Sessions:
    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    async def run[**P, T](
        self, fn: Callable[Concatenate[Session, P], T], *args: P.args, **kwargs: P.kwargs
    ) -> T:
        """``fn(session, *args, **kwargs)`` in a worker thread."""
        return await anyio.to_thread.run_sync(functools.partial(self._call, fn, *args, **kwargs))

    def _call[**P, T](
        self, fn: Callable[Concatenate[Session, P], T], *args: P.args, **kwargs: P.kwargs
    ) -> T:
        with self._factory() as session:
            return fn(session, *args, **kwargs)
