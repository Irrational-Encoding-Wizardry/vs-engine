from concurrent.futures import Future
from math import inf
import typing as t
import contextlib

from trio import Cancelled as TrioCancelled
from trio import current_effective_deadline
from trio import CapacityLimiter
from trio import Nursery
from trio import to_thread
from trio import Event
from trio.lowlevel import current_trio_token

from vsengine.loops import Cancelled, EventLoop


T = t.TypeVar("T")


class TrioEventLoop(EventLoop):
    _scope: Nursery

    def __init__(
            self,
            nursery: Nursery,
            limiter: CapacityLimiter|None=None
    ) -> None:
        if limiter is None:
            limiter = t.cast(CapacityLimiter, to_thread.current_default_thread_limiter())

        self.nursery = nursery
        self.limiter = limiter
        self._token = None

    def attach(self) -> None:
        """
        Called when set_loop is run.
        """
        self._token = current_trio_token()

    def detach(self) -> None:
        """
        Called when another event-loop should take over.
        """
        self.nursery.cancel_scope.cancel()

    def from_thread(
            self,
            func: t.Callable[..., T],
            *args: t.Any,
            **kwargs: t.Any
    ) -> Future[T]:
        """
        Ran from vapoursynth threads to move data to the event loop.
        """
        assert self._token is not None

        fut = Future()
        def _executor():
            if not fut.set_running_or_notify_cancel():
                return

            try:
                self.throw_if_cancelled()
            except Cancelled:
                fut.set_exception(Cancelled())
                return


            try:
                result = func(*args, **kwargs)
            except BaseException as e:
                fut.set_exception(e)
            else:
                fut.set_result(result)
            
        self._token.run_sync_soon(_executor)
        return fut

    async def await_future(self, future: Future[T]) -> T:
        """
        Await a concurrent future.

        This function does not need to be implemented if the event-loop
        does not support async and await.
        """
        event = Event()

        result: T|None = None
        error: BaseException|None = None
        def _when_done(_):
            nonlocal error, result
            if (error := future.exception()) is not None:
                pass
            else:
                result = future.result()
            self.from_thread(event.set)

        future.add_done_callback(_when_done)
        try:
            await event.wait()
        except TrioCancelled:
            raise

        if error is not None:
            raise t.cast(BaseException, error)
        else:
            return t.cast(T, result)


    async def to_thread(self, func: t.Callable[..., t.Any], *args: t.Any, **kwargs: t.Any):
        """
        Run this function in a worker thread.
        """
        result = None
        error: BaseException|None = None
        def _executor():
            nonlocal result, error
            try:
                result = func(*args, **kwargs)
            except BaseException as e:
                error = e

        await to_thread.run_sync(_executor, limiter=self.limiter)
        if error is not None:
            assert isinstance(error, BaseException)
            raise t.cast(BaseException, error)
        else:
            return result

    def throw_if_cancelled(self) -> None:
        """
        Throw vsengine.loops.Cancelled if the current context has been
        cancelled.

        If cancellation is not natively supported, this function is a no-op.
        """
        if current_effective_deadline() == -inf:
            raise Cancelled

    @contextlib.contextmanager
    def wrap_cancelled(self):
        """
        Wraps vsengine.loops.Cancelled into the native cancellation error.
        """
        try:
            yield
        except Cancelled:
            raise TrioCancelled.__new__(TrioCancelled) from None
