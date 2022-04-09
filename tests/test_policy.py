import logging
# vs-engine
# Copyright (C) 2022  cid-chan
# This project is licensed under the EUPL-1.2
# SPDX-License-Identifier: EUPL-1.2
import unittest

import vapoursynth

from vsengine._testutils import forcefully_unregister_policy

from vsengine.policy import GlobalStore
from vsengine.policy import Policy


class PolicyTest(unittest.TestCase):

    def setUp(self) -> None:
        forcefully_unregister_policy()
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
        forcefully_unregister_policy()
        self.store = GlobalStore()
        self.policy = Policy(self.store)
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
        self.assertRaises(RuntimeError, lambda: env.use().__enter__())

    def test_new_environment_can_use_context(self):
        with self.policy.new_environment() as env:
            self.assertRaises(vapoursynth.Error, lambda: vapoursynth.core.std.BlankClip().set_output(0))

            with env.use():
                vapoursynth.core.std.BlankClip().set_output(0)

            self.assertRaises(vapoursynth.Error, lambda: vapoursynth.core.std.BlankClip().set_output(0))

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

    def test_environment_can_capture_cores(self):
        with self.policy.new_environment() as env1:
            with self.policy.new_environment() as env2:
                self.assertNotEqual(env1.core, env2.core)

    def test_inline_section_is_invisible(self):
        with self.policy.new_environment() as env1:
            with self.policy.new_environment() as env2:
                env1.switch()

                env_before = self.store.get_current_environment()

                with env2.inline_section():
                    self.assertNotEqual(vapoursynth.get_current_environment(), env1.vs_environment)
                    self.assertEqual(env_before, self.store.get_current_environment())

                self.assertEqual(vapoursynth.get_current_environment(), env1.vs_environment)
                self.assertEqual(env_before, self.store.get_current_environment())
