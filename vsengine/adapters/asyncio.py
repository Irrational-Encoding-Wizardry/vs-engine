# vs-engine
# Copyright (C) 2022  cid-chan
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
import typing as t
import asyncio
import contextlib
import contextvars
from concurrent.futures import Future

from vsengine.loops import EventLoop, Cancelled


T = t.TypeVar("T")


class AsyncIOLoop(EventLoop):
    """
    Bridges vs-engine to AsyncIO.
    """
    loop: asyncio.AbstractEventLoop

    def __init__(self, loop: t.Optional[asyncio.AbstractEventLoop] = None) -> None:
        if loop is None:
            loop = asyncio.get_event_loop()
        self.loop = loop

    def attach(self):
        pass

    def detach(self):
        pass

    def from_thread(
            self,
            func: t.Callable[..., T],
            *args: t.Any,
            **kwargs: t.Any
    ) -> Future[T]:
        future = Future()

        ctx = contextvars.copy_context()
        def _wrap():
            if not future.set_running_or_notify_cancel():
                return

            try:
                result = ctx.run(func, *args, **kwargs)
            except BaseException as e:
                future.set_exception(e)
            else:
                future.set_result(result)

        self.loop.call_soon_threadsafe(_wrap)
        return future

    def to_thread(self, func, *args, **kwargs):
        ctx = contextvars.copy_context()
        def _wrap():
            return ctx.run(func, *args, **kwargs)

        return asyncio.to_thread(_wrap)

    async def await_future(self, future: Future[T]) -> T:
        with self.wrap_cancelled():
            return await asyncio.wrap_future(future, loop=self.loop)

    def next_cycle(self) -> Future[None]:
        future = Future()
        task = asyncio.current_task()
        def continuation():
            if task is None or not task.cancelled():
                future.set_result(None)
            else:
                future.set_exception(Cancelled())
        self.loop.call_soon(continuation)
        return future

    @contextlib.contextmanager
    def wrap_cancelled(self):
        try:
            yield
        except Cancelled:
            raise asyncio.CancelledError() from None

