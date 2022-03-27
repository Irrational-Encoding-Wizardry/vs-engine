import contextlib
import threading
import unittest

import asyncio

from concurrent.futures import Future, CancelledError

from vsengine.loops import EventLoop, get_loop, set_loop, Cancelled
from vsengine.loops import NO_LOOP, _NoEventLoop
from vsengine.adapters.asyncio import AsyncIOLoop


def make_async(func):
    def _wrapped(self, *args, **kwargs):
        return self.run_within_loop(func, args, kwargs)
    return _wrapped

def is_async(func):
    def _wrapped(self, *args, **kwargs):
        return self.run_within_loop_async(func, args, kwargs)
    return _wrapped


class AdapterTest:
    @contextlib.contextmanager
    def with_loop(self):
        loop = self.make_loop()
        set_loop(loop)
        try:
            yield loop
        finally:
            set_loop(NO_LOOP)

    def make_loop(self) -> EventLoop:
        raise NotImplementedError

    def run_within_loop(self, func, args, kwargs):
        raise NotImplementedError

    def resolve_to_thread_future(self, fut):
        raise NotImplementedError

    @contextlib.contextmanager
    def assertCancelled(self):
        raise NotImplementedError

    @make_async
    def test_wrap_cancelled_without_cancellation(self):
        with self.with_loop() as loop:
            with loop.wrap_cancelled():
                pass

    @make_async
    def test_wrap_cancelled_with_cancellation(self):
        with self.with_loop() as loop:
            with self.assertCancelled():
                with loop.wrap_cancelled():
                    raise Cancelled

    @make_async
    def test_wrap_cancelled_with_other_exception(self):
        with self.with_loop() as loop:
            with self.assertRaises(RuntimeError):
                with loop.wrap_cancelled():
                    raise RuntimeError()

    @make_async
    def test_next_cycle_doesnt_throw_when_not_cancelled(self):
        with self.with_loop() as loop:
            fut = loop.next_cycle()
            yield
            self.assertTrue(fut.done())
            self.assertIs(fut.result(), None)

    @make_async
    def test_from_thread_with_success(self) -> None:
        def test_func():
            return self
        
        with self.with_loop() as loop:
            fut = loop.from_thread(test_func)
            yield
            self.assertIs(fut.result(timeout=0.5), self)

    @make_async
    def test_from_thread_with_failure(self) -> None:
        def test_func():
            raise RuntimeError
        
        with self.with_loop() as loop:
            fut = loop.from_thread(test_func)
            yield
            self.assertRaises(RuntimeError, lambda: fut.result(timeout=0.5))

    @make_async
    def test_from_thread_forwards_correctly(self) -> None:
        a = None
        k = None
        def test_func(*args, **kwargs):
            nonlocal a, k
            a = args
            k = kwargs

        with self.with_loop() as loop:
            fut = loop.from_thread(test_func, 1, 2, 3, a="b", c="d")
            yield
            fut.result(timeout=0.5)
            self.assertEqual(a, (1,2,3))
            self.assertEqual(k, {"a": "b", "c": "d"})

    @make_async
    def test_to_thread_spawns_a_new_thread(self):
        def test_func():
            return threading.current_thread()

        with self.with_loop() as loop:
            t2 = yield from self.resolve_to_thread_future(loop.to_thread(test_func))
            self.assertNotEqual(threading.current_thread(), t2)


    @make_async
    def test_to_thread_runs_inline_with_failure(self) -> None:
        def test_func():
            raise RuntimeError
        
        with self.with_loop() as loop:
            with self.assertRaises(RuntimeError):
                yield from self.resolve_to_thread_future(loop.to_thread(test_func))

    @make_async
    def test_to_thread_forwards_correctly(self) -> None:
        a = None
        k = None
        def test_func(*args, **kwargs):
            nonlocal a, k
            a = args
            k = kwargs

        with self.with_loop() as loop:
            yield from self.resolve_to_thread_future(loop.to_thread(test_func, 1, 2, 3, a="b", c="d"))
            self.assertEqual(a, (1,2,3))
            self.assertEqual(k, {"a": "b", "c": "d"})


class AsyncAdapterTest(AdapterTest):

    def run_within_loop(self, func, args, kwargs):
        async def wrapped(_):
            result = func(self, *args, **kwargs)
            if hasattr(result, "__iter__"):
                for _ in result:
                    await self.next_cycle()

        self.run_within_loop_async(wrapped, (), {})

    def run_within_loop_async(self, func, args, kwargs):
        raise NotImplementedError

    async def wait_for(self, coro, timeout):
        raise NotImplementedError

    async def next_cycle(self):
        pass
    
    @is_async
    async def test_await_future_success(self):
        with self.with_loop() as loop:
            fut = Future()
            def _setter():
                fut.set_result(1)
            threading.Thread(target=_setter).start()
            self.assertEqual(
                await self.wait_for(loop.await_future(fut), 0.5),
                1
            )

    @is_async
    async def test_await_future_failure(self):
        with self.with_loop() as loop:
            fut = Future()
            def _setter():
                fut.set_exception(RuntimeError())

            threading.Thread(target=_setter).start()
            with self.assertRaises(RuntimeError):
                await self.wait_for(loop.await_future(fut), 0.5)



class NoLoopTest(AdapterTest, unittest.TestCase):

    def make_loop(self) -> EventLoop:
        return _NoEventLoop()

    def run_within_loop(self, func, args, kwargs):
        result = func(self, *args, **kwargs)
        if hasattr(result, "__iter__"):
            for _ in result: pass

    @contextlib.contextmanager
    def assertCancelled(self):
        with self.assertRaises(CancelledError):
            yield

    def resolve_to_thread_future(self, fut):
        if False: yield
        return fut.result(timeout=0.5)
            

class AsyncIOTest(AsyncAdapterTest, unittest.TestCase):
    def make_loop(self) -> AsyncIOLoop:
        return AsyncIOLoop()

    def run_within_loop_async(self, func, args, kwargs):
        async def wrapped():
            await func(self, *args, **kwargs)
        asyncio.run(wrapped())

    async def next_cycle(self):
        await asyncio.sleep(0.01)

    async def wait_for(self, coro, timeout):
        return await asyncio.wait_for(coro, timeout)

    @contextlib.contextmanager
    def assertCancelled(self):
        with self.assertRaises(asyncio.CancelledError):
            yield

    def resolve_to_thread_future(self, fut):
        fut = asyncio.ensure_future(fut)
        while not fut.done():
            yield
        return fut.result()


try:
    import trio
except ImportError:
    print("Skipping trio")
else:
    from vsengine.adapters.trio import TrioEventLoop
    class TrioTest(AsyncAdapterTest, unittest.TestCase):
        def make_loop(self) -> AsyncIOLoop:
            return TrioEventLoop(self.nursery)

        async def next_cycle(self):
            await trio.sleep(0.01)

        def run_within_loop_async(self, func, args, kwargs):
            async def wrapped():
                async with trio.open_nursery() as nursery:
                    self.nursery = nursery
                    await func(self, *args, **kwargs)
            trio.run(wrapped)

        def resolve_to_thread_future(self, fut):
            done = False
            result = None
            error = None
            async def _awaiter():
                nonlocal done, error, result
                try:
                    result = await fut
                except BaseException as e:
                    error = e
                finally:
                    done = True

            self.nursery.start_soon(_awaiter)

            while not done:
                yield

            if error is not None:
                raise error
            else:
                return result

        async def wait_for(self, coro, timeout):
            with trio.fail_after(timeout):
                return await coro

        @contextlib.contextmanager
        def assertCancelled(self):
            with self.assertRaises(trio.Cancelled):
                yield

