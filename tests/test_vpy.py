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
import os
import ast
import asyncio
import unittest
import textwrap
import threading
import contextlib

import vapoursynth

from vsengine._testutils import forcefully_unregister_policy
from vsengine._testutils import BLACKBOARD
from vsengine.policy import Policy, GlobalStore
from vsengine.loops import NO_LOOP, set_loop
from vsengine.adapters.asyncio import AsyncIOLoop
from vsengine.vpy import Script, script, code, chdir_runner, _load
from vsengine.vpy import inline_runner, ExecutionFailed


DIR = os.path.dirname(__file__)
PATH = os.path.join(DIR, "fixtures", "test.vpy")


@contextlib.contextmanager
def noop():
    yield


class TestException(Exception): pass


def wrap_test_for_asyncio(func):
    def test_case(self):
        async def _run():
            set_loop(AsyncIOLoop())
            await func(self)
        asyncio.run(_run())
    return test_case


def callback_script(func):
    def _script(ctx):
        with ctx:
            func()
    return _script


class ScriptTest(unittest.TestCase):

    def setUp(self) -> None:
        forcefully_unregister_policy()

    def tearDown(self) -> None:
        forcefully_unregister_policy()
        set_loop(NO_LOOP)

    def test_run_executes_successfully(self):
        run = False
        @callback_script
        def test_code():
            nonlocal run
            run = True

        with Policy(GlobalStore()) as p:
            with p.new_environment() as env:
                script = Script(test_code, env.vs_environment, inline_runner)
                script.run()
        self.assertTrue(run)

    def test_run_wraps_exception(self):
        @callback_script
        def test_code():
            raise TestException()

        with Policy(GlobalStore()) as p:
            with p.new_environment() as env:
                script = Script(test_code, env.vs_environment, inline_runner)
                fut = script.run()
                self.assertIsInstance(fut.exception(), ExecutionFailed)
                self.assertIsInstance(fut.exception().parent_error, TestException)

    def test_execute_resolves_immediately(self):
        run = False
        @callback_script
        def test_code():
            nonlocal run
            run = True

        with Policy(GlobalStore()) as p:
            with p.new_environment() as env:
                script = Script(test_code, env.vs_environment, inline_runner)
                script.execute()
        self.assertTrue(run)

    def test_execute_resolves_immediately_when_raising(self):
        @callback_script
        def test_code():
            raise TestException

        with Policy(GlobalStore()) as p:
            with p.new_environment() as env:
                script = Script(test_code, env.vs_environment, inline_runner)
                try:
                    script.execute()
                except ExecutionFailed as err:
                    self.assertIsInstance(err.parent_error, TestException)
                except Exception as e:
                    self.fail(f"Wrong exception: {e!r}")
                else:
                    self.fail("Test execution didn't fail properly.")

    @wrap_test_for_asyncio
    async def test_run_async(self):
        run = False
        @callback_script
        def test_code():
            nonlocal run
            run = True

        with Policy(GlobalStore()) as p:
            with p.new_environment() as env:
                script = Script(test_code, env.vs_environment, inline_runner)
                await script.run_async()
        self.assertTrue(run)

    @wrap_test_for_asyncio
    async def test_await_directly(self):
        run = False
        @callback_script
        def test_code():
            nonlocal run
            run = True

        with Policy(GlobalStore()) as p:
            with p.new_environment() as env:
                await Script(test_code, env.vs_environment, inline_runner)
        self.assertTrue(run)

    def test_cant_dispose_non_managed_environments(self):
        @callback_script
        def test_code():
            pass
        with Policy(GlobalStore()) as p:
            with p.new_environment() as env:
                script = Script(test_code, env.vs_environment, inline_runner)
                with self.assertRaises(ValueError):
                    script.dispose()

    def test_disposes_managed_environment(self):
        @callback_script
        def test_code():
            pass
        with Policy(GlobalStore()) as p:
            env = p.new_environment()
            script = Script(test_code, env, inline_runner)

            try:
                script.dispose()
            except:
                env.dispose()
                raise

    def test_noop_context_manager_for_non_managed_environments(self):
        @callback_script
        def test_code():
            pass
        with Policy(GlobalStore()) as p:
            with p.new_environment() as env:
                with Script(test_code, env.vs_environment, inline_runner) as s:
                    pass
                self.assertFalse(env.disposed)

    def test_disposing_context_manager_for_managed_environments(self):
        @callback_script
        def test_code():
            pass
        with Policy(GlobalStore()) as p:
            env = p.new_environment()
            with Script(test_code, env, inline_runner):
                pass
            try:
                self.assertTrue(env.disposed)
            except:
                env.dispose()
                raise

    def test_chdir_changes_chdir(self):
        curdir = None
        def test_code():
            nonlocal curdir
            curdir = os.getcwd()

        wrapped = chdir_runner(DIR, inline_runner)
        wrapped(test_code)
        self.assertEqual(curdir, DIR)

    def test_chdir_changes_chdir_back(self):
        def test_code():
            pass
        wrapped = chdir_runner(DIR, inline_runner)

        before = os.getcwd()
        wrapped(test_code)
        self.assertEqual(os.getcwd(), before)

    def test_load_uses_current_environment(self):
        vpy_env = None
        @callback_script
        def test_code():
            nonlocal vpy_env
            vpy_env = vapoursynth.get_current_environment()

        with Policy(GlobalStore()) as p:
            with p.new_environment() as env:
                with env.use():
                    _load(test_code, None, inline=False, chdir=None).execute()
                    self.assertEqual(vpy_env, env.vs_environment)

    def test_load_creates_new_environment(self):
        vpy_env = None
        @callback_script
        def test_code():
            nonlocal vpy_env
            vpy_env = vapoursynth.get_current_environment()

        with Policy(GlobalStore()) as p:
            script = _load(test_code, p, inline=True, chdir=None)
            try:
                script.execute()
                self.assertEqual(vpy_env, script.environment.vs_environment)
            finally:
                script.dispose()

    def test_load_runs_chdir(self):
        curdir = None
        @callback_script
        def test_code():
            nonlocal curdir
            curdir = os.getcwd()

        with Policy(GlobalStore()) as p:
            with p.new_environment() as env:
                with env.use():
                    previous = os.getcwd()
                    _load(test_code, None, inline=True, chdir=DIR).execute()
                    self.assertEqual(curdir, DIR)
                    self.assertEqual(os.getcwd(), previous)

    def test_load_runs_in_thread_when_requested(self):
        thread = None
        @callback_script
        def test_code():
            nonlocal thread
            thread = threading.current_thread()

        with Policy(GlobalStore()) as p:
            with p.new_environment() as env:
                with env.use():
                    _load(test_code, None, inline=False, chdir=None).execute()
                    self.assertIsNot(thread, threading.current_thread())

    def test_load_runs_inline_by_default(self):
        thread = None
        @callback_script
        def test_code():
            nonlocal thread
            thread = threading.current_thread()

        with Policy(GlobalStore()) as p:
            with p.new_environment() as env:
                with env.use():
                    _load(test_code, None, chdir=None).execute()
                    self.assertIs(thread, threading.current_thread())

    def test_code_runs_string(self):
        CODE = textwrap.dedent("""
            from vsengine._testutils import BLACKBOARD
            BLACKBOARD["vpy_test_runs_raw_code_str"] = True
        """)

        with Policy(GlobalStore()) as p:
            with p.new_environment() as env:
                with env.use():
                    code(CODE).execute()
                    self.assertEqual(BLACKBOARD.get("vpy_test_runs_raw_code_str"), True)

    def test_code_runs_bytes(self):
        CODE = textwrap.dedent("""
            # encoding: latin-1
            from vsengine._testutils import BLACKBOARD
            BLACKBOARD["vpy_test_runs_raw_code_bytes"] = True
        """).encode("latin-1")

        with Policy(GlobalStore()) as p:
            with p.new_environment() as env:
                with env.use():
                    code(CODE).execute()
                    self.assertEqual(BLACKBOARD.get("vpy_test_runs_raw_code_bytes"), True)

    def test_code_runs_ast(self):
        CODE = ast.parse(textwrap.dedent("""
            from vsengine._testutils import BLACKBOARD
            BLACKBOARD["vpy_test_runs_raw_code_ast"] = True
        """))

        with Policy(GlobalStore()) as p:
            with p.new_environment() as env:
                with env.use():
                    code(CODE).execute()
                    self.assertEqual(BLACKBOARD.get("vpy_test_runs_raw_code_ast"), True)

    def test_script_runs(self):
        with Policy(GlobalStore()) as p:
            with p.new_environment() as env:
                with env.use():
                    script(PATH).execute()
                    self.assertEqual(BLACKBOARD.get("vpy_run_script"), True)
