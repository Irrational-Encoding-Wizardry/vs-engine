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
from concurrent.futures import Future, CancelledError
import contextlib
import typing as t

import vapoursynth


T = t.TypeVar("T")
T_co = t.TypeVar("T_co", covariant=True)


__all__ = [
    "EventLoop", "Cancelled",
    "get_loop", "set_loop", "run_in_loop"
]


class Cancelled(Exception): pass


@contextlib.contextmanager
def _noop():
    yield


class EventLoop:
    """
    These functions must be implemented to bridge VapourSynth
    with the event-loop of your choice.
    """

    def attach(self) -> None:
        """
        Called when set_loop is run.
        """
        ...

    def detach(self) -> None:
        """
        Called when another event-loop should take over.
        """
        ...

    def from_thread(
            self,
            func: t.Callable[..., T],
            *args: t.Any,
            **kwargs: t.Any
    ) -> Future[T]:
        """
        Ran from vapoursynth threads to move data to the event loop.
        """
        ...

    def await_future(self, future: Future[T]) -> t.Awaitable[T]:
        """
        Await a concurrent future.

        This function does not need to be implemented if the event-loop
        does not support async and await.
        """
        raise NotImplementedError

    def to_thread(self, func: t.Callable[..., t.Any], *args: t.Any, **kwargs: t.Any) -> t.Any:
        """
        Run this function in a worker thread.
        """
        fut = Future()
        def wrapper():
            try:
                fut.set_running_or_notify_cancel()
            except CancelledError:
                pass

            try:
                result = func(*args, **kwargs)
            except BaseException as e:
                fut.set_exception(e)
            else:
                fut.set_result(result)

        import threading
        threading.Thread(target=wrapper).start()
        return fut

    def throw_if_cancelled(self) -> None:
        """
        Throw vsengine.loops.Cancelled if the current context has been
        cancelled.

        If cancellation is not natively supported, this function is a no-op.
        """
        pass

    @contextlib.contextmanager
    def wrap_cancelled(self):
        """
        Wraps vsengine.loops.Cancelled into the native cancellation error.
        """
        try:
            yield
        except Cancelled:
            raise CancelledError from None


class _NoEventLoop(EventLoop):
    """
    This is the default event-loop used by 
    """

    def attach(self) -> None:
        pass

    def detach(self) -> None:
        pass

    def from_thread(
            self,
            func: t.Callable[..., T],
            *args: t.Any,
            **kwargs: t.Any
    ) -> Future[T]:
        fut = Future()
        try:
            result = func(*args, **kwargs)
        except BaseException as e:
            fut.set_exception(e)
        else:
            fut.set_result(result)
        return fut


NO_LOOP = _NoEventLoop()
current_loop = NO_LOOP


def get_loop() -> EventLoop:
    """
    :return: The currently running loop.
    """
    return current_loop

def set_loop(loop: EventLoop) -> None:
    """
    Sets the currently running loop.

    It will detach the previous loop first. If attaching fails,
    it will revert to the NoLoop-implementation which runs everything inline

    :param loop: The event-loop instance that implements features.
    """
    global current_loop
    current_loop.detach()
    try:
        current_loop = loop
        loop.attach()
    except:
        current_loop = NO_LOOP
        raise


def from_thread(func: t.Callable[..., T], *args: t.Any, **kwargs: t.Any) -> Future[T]:
    """
    Runs a function inside the current event-loop, preserving the currently running
    vapoursynth environment (if any).

    .. note:: Be aware that the function might be called inline!

    :param func: A function to call inside the current event loop.
    :param args: The arguments for the function.
    :param kwargs: The keyword arguments to pass to the function.
    :return: A future that resolves and reject depending on the outcome.
    """
    try:
        environment = vapoursynth.get_current_environment().use()
    except RuntimeError:
        environment = _noop()

    def _wrapper():
        with environment:
            return func(*args, **kwargs)

    return get_loop().from_thread(_wrapper)


def to_thread(func: t.Callable[..., t.Any], *args: t.Any, **kwargs: t.Any) -> t.Any:
    """
    Runs a function in a dedicated thread or worker, preserving the currently running
    vapoursynth environment (if any).

    :param func: A function to call inside the current event loop.
    :param args: The arguments for the function.
    :param kwargs: The keyword arguments to pass to the function.
    :return: An loop-specific object.
    """
    try:
        environment = vapoursynth.get_current_environment().use()
    except RuntimeError:
        environment = _noop()

    def _wrapper():
        with environment:
            return func(*args, **kwargs)
    
    return get_loop().to_thread(_wrapper)


async def make_awaitable(future: Future[T]) -> T:
    return t.cast(T, await get_loop().await_future(future))

