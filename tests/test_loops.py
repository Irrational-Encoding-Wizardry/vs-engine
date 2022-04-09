# vs-engine
# Copyright (C) 2022  cid-chan
# This project is licensed under the EUPL-1.2
# SPDX-License-Identifier: EUPL-1.2

import queue
import unittest
import threading
from concurrent.futures import Future, CancelledError

import vapoursynth

from vsengine._testutils import forcefully_unregister_policy
from vsengine.policy import Policy, ThreadLocalStore

from vsengine.loops import _NoEventLoop, Cancelled, from_thread, get_loop, set_loop
from vsengine.loops import to_thread, from_thread
from vsengine.loops import EventLoop


class FailingEventLoop:
    def attach(self):
        raise RuntimeError()


class SomeOtherLoop:
    def attach(self):
        pass

    def detach(self):
        pass

class SpinLoop(EventLoop):
    def __init__(self) -> None:
        self.queue = queue.Queue()

    def attach(self) -> None:
        pass

    def detach(self) -> None:
        pass

    def run(self):
        while (value := self.queue.get()) is not None:
            future, func, args, kwargs = value
            try:
                result = func(*args, **kwargs)
            except BaseException as e:
                future.set_exception(e)
            else:
                future.set_result(result)

    def stop(self):
        self.queue.put(None)

    def from_thread(self, func, *args, **kwargs):
        fut = Future()
        self.queue.put((fut, func, args, kwargs))
        return fut


class NoLoopTest(unittest.TestCase):


    def test_wrap_cancelled_converts_the_exception(self) -> None:
        loop = _NoEventLoop()
        with self.assertRaises(CancelledError):
            with loop.wrap_cancelled():
                raise Cancelled


class LoopApiTest(unittest.TestCase):

    def tearDown(self) -> None:
        forcefully_unregister_policy()

    def test_loop_can_override(self):
        loop = _NoEventLoop()
        set_loop(loop)
        self.assertIs(get_loop(), loop)

    def test_loop_reverts_to_no_on_error(self):
        try:
            set_loop(SomeOtherLoop())
            loop = FailingEventLoop()
            try:
                set_loop(loop)
            except RuntimeError:
                pass

            self.assertIsInstance(get_loop(), _NoEventLoop)
        finally:
            set_loop(_NoEventLoop())

    def test_loop_from_thread_retains_environment(self):
        loop = SpinLoop()
        set_loop(loop)
        thr = threading.Thread(target=loop.run)
        thr.start()

        def test():
            return vapoursynth.get_current_environment()

        try:
            with Policy(ThreadLocalStore()) as p:
                with p.new_environment() as env1:
                    with env1.use():
                        fut = from_thread(test)
                    self.assertEqual(fut.result(timeout=0.1), env1.vs_environment)
        finally:
            loop.stop()
            thr.join()
            set_loop(_NoEventLoop())

    def test_loop_from_thread_does_not_require_environment(self):
        loop = SpinLoop()
        set_loop(loop)
        thr = threading.Thread(target=loop.run)
        thr.start()

        def test():
            pass

        try:
            from_thread(test).result(timeout=0.1)
        finally:
            loop.stop()
            thr.join()
            set_loop(_NoEventLoop())

    def test_loop_to_thread_retains_environment(self):
        def test():
            return vapoursynth.get_current_environment()

        with Policy(ThreadLocalStore()) as p:
            with p.new_environment() as env1:
                with env1.use():
                    fut = to_thread(test)
                self.assertEqual(fut.result(timeout=0.1), env1.vs_environment)

    def test_loop_to_thread_does_not_require_environment(self):
        def test():
            pass

        fut = to_thread(test)
        fut.result(timeout=0.1)

