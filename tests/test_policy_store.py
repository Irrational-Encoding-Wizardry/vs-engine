import unittest

import concurrent.futures as futures
from concurrent.futures.thread import ThreadPoolExecutor

from contextvars import Context, copy_context

from vsengine.policy import GlobalStore, ThreadLocalStore, ContextVarStore 
from vsengine.policy import EnvironmentStore


class BaseStoreTest:

    def create_store(self) -> EnvironmentStore:
        raise NotImplementedError

    def setUp(self) -> None:
        self.store = self.create_store()

    def tearDown(self) -> None:
        self.store.set_current_environment(None)

    def test_basic_functionality(self):
        self.assertEqual(self.store.get_current_environment(), None)

        self.store.set_current_environment(1)
        self.assertEqual(self.store.get_current_environment(), 1)
        self.store.set_current_environment(2)
        self.assertEqual(self.store.get_current_environment(), 2)
        self.store.set_current_environment(None)
        self.assertEqual(self.store.get_current_environment(), None)


class TestGlobalStore(BaseStoreTest, unittest.TestCase):

    def create_store(self) -> EnvironmentStore:
        return GlobalStore()


class TestThreadLocalStore(BaseStoreTest, unittest.TestCase):

    def create_store(self) -> EnvironmentStore:
        return ThreadLocalStore()

    def test_threads_do_not_influence_each_other(self):
        def thread():
            self.assertEqual(self.store.get_current_environment(), None)
            self.store.set_current_environment(2)
            self.assertEqual(self.store.get_current_environment(), 2)

        with futures.ThreadPoolExecutor(max_workers=1) as e:
            self.store.set_current_environment(1)
            e.submit(thread).result()
            self.assertEqual(self.store.get_current_environment(), 1)


class TestContextVarStore(BaseStoreTest, unittest.TestCase):

    def create_store(self) -> EnvironmentStore:
        return ContextVarStore("store_test")

    def test_threads_do_not_influence_each_other(self):
        def thread():
            self.assertEqual(self.store.get_current_environment(), None)
            self.store.set_current_environment(2)
            self.assertEqual(self.store.get_current_environment(), 2)

        with futures.ThreadPoolExecutor(max_workers=1) as e:
            self.store.set_current_environment(1)
            e.submit(thread).result()
            self.assertEqual(self.store.get_current_environment(), 1)

    def test_contexts_do_not_influence_each_other(self):
        def context(p, n):
            self.assertEqual(self.store.get_current_environment(), p)
            self.store.set_current_environment(n)
            self.assertEqual(self.store.get_current_environment(), n)

        ctx = copy_context()
        ctx.run(context, None, 1)
        self.assertEqual(self.store.get_current_environment(), None)
        
        self.store.set_current_environment(2)
        self.assertEqual(self.store.get_current_environment(), 2)
        ctx.run(context, 1, 3)

        self.assertEqual(self.store.get_current_environment(), 2)
