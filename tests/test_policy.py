import logging
import unittest

import vapoursynth

from vsengine._testutils import forcefully_unregister_policy

from vsengine.policy import GlobalStore
from vsengine.policy import Policy, ManagedEnvironment
from vsengine.policy import _ManagedPolicy


class PolicyTest(unittest.TestCase):

    def setUp(self) -> None:
        self.policy = Policy(GlobalStore())

    def tearDown(self) -> None:
        forcefully_unregister_policy()

    def test_register(self):
        self.policy.register()
        try:
            self.assertIsNotNone(self.policy.api)
        finally:
            self.policy.unregister()

    def test_unregister(self):
        self.policy.register()
        self.policy.unregister()

        with self.assertRaises(RuntimeError):
            self.policy.api.create_environment()

    def test_context_manager(self):
        with self.policy:
            self.policy.api.create_environment()

        with self.assertRaises(RuntimeError):
            self.policy.api.create_environment()

    def test_context_manager_on_error(self):
        try:
            with self.policy:
                raise RuntimeError()
        except RuntimeError:
            pass

        self.assertRaises(RuntimeError, lambda: self.policy.api.create_environment())

        try:
            self.policy.unregister()
        except:
            pass


class ManagedEnvironmentTest(unittest.TestCase):

    def setUp(self) -> None:
        self.policy = Policy(GlobalStore())
        self.policy.register()

    def tearDown(self) -> None:
        self.policy.unregister()

    def test_new_environment_warns_on_del(self):
        env = self.policy.new_environment()
        with self.assertWarns(ResourceWarning):
            del env

    def test_new_environment_can_dispose(self):
        env = self.policy.new_environment()
        env.dispose()
        with self.assertRaises(RuntimeError):
            env.use().__enter__()

    def test_new_environment_can_use_context(self):
        with self.policy.new_environment() as env:
            with self.assertRaises(vapoursynth.Error):
                vapoursynth.core.std.BlankClip().set_output(0)

            with env.use():
                vapoursynth.core.std.BlankClip().set_output(0)

            with self.assertRaises(vapoursynth.Error):
                vapoursynth.core.std.BlankClip().set_output(0)

    def test_environment_can_switch(self):
        env = self.policy.new_environment()
        self.assertRaises(vapoursynth.Error, lambda: vapoursynth.core.std.BlankClip().set_output(0))
        env.switch()
        vapoursynth.core.std.BlankClip().set_output(0)
        env.dispose()

    def test_environment_can_capture_outputs(self):
        with self.policy.new_environment() as env1:
            with self.policy.new_environment() as env2:
                with env1.use():
                    vapoursynth.core.std.BlankClip().set_output(0)

                self.assertEqual(len(env1.outputs), 1)
                self.assertEqual(len(env2.outputs), 0)
