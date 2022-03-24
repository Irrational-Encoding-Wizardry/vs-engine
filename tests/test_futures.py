import unittest
import threading
import contextlib
import collections
from concurrent.futures import Future

from vsengine._testutils import wrap_test_for_asyncio
from vsengine._futures import UnifiedFuture, UnifiedIterable, unified


def resolve(value):
    fut = Future()
    fut.set_result(value)
    return fut

def reject(err):
    fut = Future()
    fut.set_exception(err)
    return fut


def contextmanager():
    @contextlib.contextmanager
    def noop():
        yield 1
    return resolve(noop())

def asynccontextmanager():
    @contextlib.asynccontextmanager
    async def noop():
        yield 2
    return resolve(noop())

def succeeds():
    return resolve(1)

def fails():
    return reject(RuntimeError())

def fails_early():
    raise RuntimeError()


def future_iterator():
    n = 0
    while True:
        yield resolve(n)
        n+=1


class WrappedUnifiedFuture(UnifiedFuture):
    pass


class WrappedUnifiedIterable(UnifiedIterable):
    pass


class TestUnifiedFuture(unittest.TestCase):
    
    @wrap_test_for_asyncio
    async def test_is_await(self):
        await UnifiedFuture.from_call(succeeds)

    @wrap_test_for_asyncio
    async def test_awaitable(self):
        await UnifiedFuture.from_call(succeeds).awaitable()

    @wrap_test_for_asyncio
    async def test_async_context_manager_async(self):
        async with UnifiedFuture.from_call(asynccontextmanager) as v:
            self.assertEqual(v, 2)

    @wrap_test_for_asyncio
    async def test_context_manager_async(self):
        async with UnifiedFuture.from_call(contextmanager) as v:
            self.assertEqual(v, 1)

    def test_context_manager(self):
        with UnifiedFuture.from_call(contextmanager) as v:
            self.assertEqual(v, 1)

    @wrap_test_for_asyncio
    async def test_add_loop_callback(self):
        def _init_thread(fut):
            fut.set_result(threading.current_thread())

        fut = Future()
        thr = threading.Thread(target=lambda:_init_thread(fut))
        def _wrapper():
            return fut

        fut = UnifiedFuture.from_call(_wrapper)

        loop_thread = None
        def _record_loop_thr(_):
            nonlocal loop_thread
            loop_thread = threading.current_thread()
        fut.add_loop_callback(_record_loop_thr)
        thr.start()
        cb_thread = await fut

        self.assertNotEqual(cb_thread, loop_thread)


class UnifiedIterableTest(unittest.TestCase):

    def test_can_iter_futures(self):
        n = 0
        for fut in UnifiedIterable.from_call(future_iterator).futures:
            self.assertEqual(n, fut.result())
            n+=1
            if n > 100:
                break

    def test_can_iter(self):
        n = 0
        for n2 in UnifiedIterable.from_call(future_iterator):
            self.assertEqual(n, n2)
            n+=1
            if n > 100:
                break

    @wrap_test_for_asyncio
    async def test_can_aiter(self):
        n = 0
        async for n2 in UnifiedIterable.from_call(future_iterator):
            self.assertEqual(n, n2)
            n+=1
            if n > 100:
                break


class UnifiedFunctionTest(unittest.TestCase):

    def test_unified_auto_future_return_a_unified_future(self):
        @unified()
        def test_func():
            return resolve(9999)

        f = test_func()
        self.assertIsInstance(f, UnifiedFuture)
        self.assertEqual(f.result(), 9999)

    def test_unified_auto_generator_return_a_unified_iterable(self):
        @unified()
        def test_func():
            yield resolve(1)
            yield resolve(2)

        f = test_func()
        self.assertIsInstance(f, UnifiedIterable)
        self.assertEqual(next(f), 1)
        self.assertEqual(next(f), 2)

    def test_unified_generator_accepts_other_iterables(self):
        @unified(type="generator")
        def test_func():
            return iter((resolve(1), resolve(2)))

        f = test_func()
        self.assertIsInstance(f, UnifiedIterable)
        self.assertEqual(next(f), 1)
        self.assertEqual(next(f), 2)

    def test_unified_custom_future(self):
        @unified(future_class=WrappedUnifiedFuture)
        def test_func():
            return resolve(9999)

        f = test_func()
        self.assertIsInstance(f, WrappedUnifiedFuture)

    def test_unified_custom_generator(self):
        @unified(iterable_class=WrappedUnifiedIterable)
        def test_func():
            yield resolve(9999)

        f = test_func()
        self.assertIsInstance(f, WrappedUnifiedIterable)
