import unittest
import threading
import contextlib
from concurrent.futures import Future

from vsengine._testutils import wrap_test_for_asyncio
from vsengine._futures import UnifiedFuture, UnifiedIterator, unified
from vsengine.loops import set_loop, NO_LOOP


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


class WrappedUnifiedIterable(UnifiedIterator):
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

    def test_map(self):
        def _crash(v):
            raise RuntimeError(str(v))

        future = UnifiedFuture.from_call(succeeds)
        new_future = future.map(lambda v: str(v))
        self.assertEqual(new_future.result(), "1")

        new_future = future.map(_crash)
        self.assertIsInstance(new_future.exception(), RuntimeError)

        future = UnifiedFuture.from_call(fails)
        new_future = future.map(lambda v: str(v))
        self.assertIsInstance(new_future.exception(), RuntimeError)

    def test_catch(self):
        def _crash(_):
            raise RuntimeError("test")

        future = UnifiedFuture.from_call(fails)
        new_future = future.catch(lambda e: e.__class__.__name__)
        self.assertEqual(new_future.result(), "RuntimeError")

        new_future = future.catch(_crash)
        self.assertIsInstance(new_future.exception(), RuntimeError)

        future = UnifiedFuture.from_call(succeeds)
        new_future = future.catch(lambda v: str(v))
        self.assertEqual(new_future.result(), 1)

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


class UnifiedIteratorTest(unittest.TestCase):

    def test_run_as_completed_succeeds(self):
        set_loop(NO_LOOP)
        my_futures = [Future(), Future()]
        results = []
        def _add_to_result(f):
            results.append(f.result())
        state = UnifiedIterator(iter(my_futures)).run_as_completed(_add_to_result)
        self.assertFalse(state.done())
        my_futures[1].set_result(2)
        self.assertFalse(state.done())
        my_futures[0].set_result(1)
        self.assertTrue(state.done())
        self.assertIs(state.result(), None)
        self.assertEqual(results, [1, 2])

    def test_run_as_completed_forwards_errors(self):
        set_loop(NO_LOOP)
        my_futures = [Future(), Future()]
        results = []
        errors = []
        def _add_to_result(f):
            if (exc := f.exception()):
                errors.append(exc)
            else:
                results.append(f.result())

        iterator = iter(my_futures)
        state = UnifiedIterator(iterator).run_as_completed(_add_to_result)
        self.assertFalse(state.done())
        my_futures[0].set_exception(RuntimeError())
        self.assertFalse(state.done())
        my_futures[1].set_result(2)
        self.assertTrue(state.done())
        self.assertIs(state.result(), None)

        self.assertEqual(results, [2])
        self.assertEqual(len(errors), 1)

    def test_run_as_completed_cancels(self):
        set_loop(NO_LOOP)
        my_futures = [Future(), Future()]
        results = []
        def _add_to_result(f):
            results.append(f.result())
            return False

        iterator = iter(my_futures)
        state = UnifiedIterator(iterator).run_as_completed(_add_to_result)
        self.assertFalse(state.done())
        my_futures[0].set_result(1)
        self.assertTrue(state.done())
        self.assertIs(state.result(), None)
        self.assertEqual(results, [1])

    def test_run_as_completed_cancels_on_crash(self):
        set_loop(NO_LOOP)
        my_futures = [Future(), Future()]
        err = RuntimeError("test")
        def _crash(_):
            raise err

        iterator = iter(my_futures)
        state = UnifiedIterator(iterator).run_as_completed(_crash)
        self.assertFalse(state.done())
        my_futures[0].set_result(1)
        self.assertTrue(state.done())
        self.assertIs(state.exception(), err)
        self.assertIsNotNone(next(iterator))

    def test_run_as_completed_cancels_on_iterator_crash(self):
        err = RuntimeError("test")
        def _it():
            if False:
                yield Future()
            raise err
        def _noop(_):
            pass
        state = UnifiedIterator(_it()).run_as_completed(_noop)
        self.assertTrue(state.done())
        self.assertIs(state.exception(), err)

    def test_can_iter_futures(self):
        n = 0
        for fut in UnifiedIterator.from_call(future_iterator).futures:
            self.assertEqual(n, fut.result())
            n+=1
            if n > 100:
                break

    def test_can_iter(self):
        n = 0
        for n2 in UnifiedIterator.from_call(future_iterator):
            self.assertEqual(n, n2)
            n+=1
            if n > 100:
                break

    @wrap_test_for_asyncio
    async def test_can_aiter(self):
        n = 0
        async for n2 in UnifiedIterator.from_call(future_iterator):
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
        self.assertIsInstance(f, UnifiedIterator)
        self.assertEqual(next(f), 1)
        self.assertEqual(next(f), 2)

    def test_unified_generator_accepts_other_iterables(self):
        @unified(type="generator")
        def test_func():
            return iter((resolve(1), resolve(2)))

        f = test_func()
        self.assertIsInstance(f, UnifiedIterator)
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
