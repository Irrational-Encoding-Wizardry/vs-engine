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
import types
import unittest
import textwrap
import threading
import contextlib

import vapoursynth

from vsengine._testutils import forcefully_unregister_policy
from vsengine._testutils import BLACKBOARD, wrap_test_for_asyncio
from vsengine.policy import Policy, GlobalStore
from vsengine.loops import NO_LOOP, set_loop
from vsengine.vpy import Script, script, code, variables, chdir_runner, _load
from vsengine.vpy import inline_runner, ExecutionFailed, WrapAllErrors


DIR = os.path.dirname(__file__)
PATH = os.path.join(DIR, "fixtures", "test.vpy")


@contextlib.contextmanager
def noop():
    yield


class TestException(Exception): pass


def callback_script(func):
    def _script(ctx, module):
        with ctx:
            func(module)
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
        def test_code(_):
            nonlocal run
            run = True

        with Policy(GlobalStore()) as p:
            with p.new_environment() as env:
                script = Script(test_code, types.ModuleType("__test__"), env.vs_environment, inline_runner)
                script.run()
        self.assertTrue(run)

    def test_run_wraps_exception(self):
        @callback_script
        def test_code(_):
            raise TestException()

        with Policy(GlobalStore()) as p:
            with p.new_environment() as env:
                script = Script(test_code, types.ModuleType("__test__"), env.vs_environment, inline_runner)
                fut = script.run()
                self.assertIsInstance(fut.exception(), ExecutionFailed)
                self.assertIsInstance(fut.exception().parent_error, TestException)

    def test_execute_resolves_immediately(self):
        run = False
        @callback_script
        def test_code(_):
            nonlocal run
            run = True

        with Policy(GlobalStore()) as p:
            with p.new_environment() as env:
                script = Script(test_code, types.ModuleType("__test__"), env.vs_environment, inline_runner)
                script.result()
        self.assertTrue(run)

    def test_execute_resolves_to_script(self):
        @callback_script
        def test_code(_):
            pass

        with Policy(GlobalStore()) as p:
            with p.new_environment() as env:
                script = Script(test_code, types.ModuleType("__test__"), env.vs_environment, inline_runner)
                self.assertIs(script.result(), script)

    def test_execute_resolves_immediately_when_raising(self):
        @callback_script
        def test_code(_):
            raise TestException

        with Policy(GlobalStore()) as p:
            with p.new_environment() as env:
                script = Script(test_code, types.ModuleType("__test__"), env.vs_environment, inline_runner)
                try:
                    script.result()
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
        def test_code(_):
            nonlocal run
            run = True

        with Policy(GlobalStore()) as p:
            with p.new_environment() as env:
                script = Script(test_code, types.ModuleType("__test__"), env.vs_environment, inline_runner)
                await script.run_async()
        self.assertTrue(run)

    @wrap_test_for_asyncio
    async def test_await_directly(self):
        run = False
        @callback_script
        def test_code(_):
            nonlocal run
            run = True

        with Policy(GlobalStore()) as p:
            with p.new_environment() as env:
                await Script(test_code, types.ModuleType("__test__"), env.vs_environment, inline_runner)
        self.assertTrue(run)

    def test_cant_dispose_non_managed_environments(self):
        @callback_script
        def test_code(_):
            pass
        with Policy(GlobalStore()) as p:
            with p.new_environment() as env:
                script = Script(test_code, types.ModuleType("__test__"), env.vs_environment, inline_runner)
                with self.assertRaises(ValueError):
                    script.dispose()

    def test_disposes_managed_environment(self):
        @callback_script
        def test_code(_):
            pass
        with Policy(GlobalStore()) as p:
            env = p.new_environment()
            script = Script(test_code, types.ModuleType("__test__"), env, inline_runner)

            try:
                script.dispose()
            except:
                env.dispose()
                raise

    def test_noop_context_manager_for_non_managed_environments(self):
        @callback_script
        def test_code(_):
            pass
        with Policy(GlobalStore()) as p:
            with p.new_environment() as env:
                with Script(test_code, types.ModuleType("__test__"), env.vs_environment, inline_runner) as s:
                    pass
                self.assertFalse(env.disposed)

    def test_disposing_context_manager_for_managed_environments(self):
        @callback_script
        def test_code(_):
            pass
        with Policy(GlobalStore()) as p:
            env = p.new_environment()
            with Script(test_code, types.ModuleType("__test__"), env, inline_runner):
                pass
            try:
                self.assertTrue(env.disposed)
            except:
                env.dispose()
                raise

    def test_chdir_changes_chdir(self):
        curdir = None
        @callback_script
        def test_code(_):
            nonlocal curdir
            curdir = os.getcwd()

        wrapped = chdir_runner(DIR, inline_runner)
        wrapped(test_code, noop(), 2)
        self.assertEqual(curdir, DIR)

    def test_chdir_changes_chdir_back(self):
        @callback_script
        def test_code(_):
            pass
        wrapped = chdir_runner(DIR, inline_runner)

        before = os.getcwd()
        wrapped(test_code, noop(), None)
        self.assertEqual(os.getcwd(), before)

    def test_load_uses_current_environment(self):
        vpy_env = None
        @callback_script
        def test_code(_):
            nonlocal vpy_env
            vpy_env = vapoursynth.get_current_environment()

        with Policy(GlobalStore()) as p:
            with p.new_environment() as env:
                with env.use():
                    _load(test_code, None, inline=False, chdir=None).result()
                    self.assertEqual(vpy_env, env.vs_environment)

    def test_load_creates_new_environment(self):
        vpy_env = None
        @callback_script
        def test_code(_):
            nonlocal vpy_env
            vpy_env = vapoursynth.get_current_environment()

        with Policy(GlobalStore()) as p:
            script = _load(test_code, p, inline=True, chdir=None)
            try:
                script.result()
                self.assertEqual(vpy_env, script.environment.vs_environment)
            finally:
                script.dispose()

    def test_load_chains_script(self):
        @callback_script
        def test_code_1(module):
            self.assertFalse(hasattr(module, "test"))
            module.test = True

        @callback_script
        def test_code_2(module):
            self.assertEqual(module.test, True)

        with Policy(GlobalStore()) as p:
            script1 = _load(test_code_1, p, inline=True, chdir=None)
            env = script1.environment
            try:
                script1.result()
                script2 = _load(test_code_2, script1, inline=True, chdir=None)
                script2.result()
            finally:
                env.dispose()

    def test_load_with_custom_name(self):
        @callback_script
        def test_code_1(module):
            self.assertEqual(module.__name__, "__test_1__")

        @callback_script
        def test_code_2(module):
            self.assertEqual(module.__name__, "__test_2__")

        with Policy(GlobalStore()) as p:
            try:
                script1 = _load(test_code_1, p, module_name="__test_1__")
                script1.result()
            finally:
                script1.dispose()

            try:
                script2 = _load(test_code_2, p, module_name="__test_2__")
                script2.result()
            finally:
                script2.dispose()

    def test_load_runs_chdir(self):
        curdir = None
        @callback_script
        def test_code(_):
            nonlocal curdir
            curdir = os.getcwd()

        with Policy(GlobalStore()) as p:
            with p.new_environment() as env:
                with env.use():
                    previous = os.getcwd()
                    _load(test_code, None, inline=True, chdir=DIR).result()
                    self.assertEqual(curdir, DIR)
                    self.assertEqual(os.getcwd(), previous)

    def test_load_runs_in_thread_when_requested(self):
        thread = None
        @callback_script
        def test_code(_):
            nonlocal thread
            thread = threading.current_thread()

        with Policy(GlobalStore()) as p:
            with p.new_environment() as env:
                with env.use():
                    _load(test_code, None, inline=False, chdir=None).result()
                    self.assertIsNot(thread, threading.current_thread())

    def test_load_runs_inline_by_default(self):
        thread = None
        @callback_script
        def test_code(_):
            nonlocal thread
            thread = threading.current_thread()

        with Policy(GlobalStore()) as p:
            with p.new_environment() as env:
                with env.use():
                    _load(test_code, None, chdir=None).result()
                    self.assertIs(thread, threading.current_thread())

    def test_code_runs_string(self):
        CODE = textwrap.dedent("""
            from vsengine._testutils import BLACKBOARD
            BLACKBOARD["vpy_test_runs_raw_code_str"] = True
        """)

        with Policy(GlobalStore()) as p:
            with p.new_environment() as env:
                with env.use():
                    code(CODE).result()
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
                    code(CODE).result()
                    self.assertEqual(BLACKBOARD.get("vpy_test_runs_raw_code_bytes"), True)

    def test_code_runs_ast(self):
        CODE = ast.parse(textwrap.dedent("""
            from vsengine._testutils import BLACKBOARD
            BLACKBOARD["vpy_test_runs_raw_code_ast"] = True
        """))

        with Policy(GlobalStore()) as p:
            with p.new_environment() as env:
                with env.use():
                    code(CODE).result()
                    self.assertEqual(BLACKBOARD.get("vpy_test_runs_raw_code_ast"), True)

    def test_script_runs(self):
        BLACKBOARD.clear()
        with Policy(GlobalStore()) as p:
            with p.new_environment() as env:
                with env.use():
                    script(PATH).result()
                    self.assertEqual(BLACKBOARD.get("vpy_run_script"), True)

    def test_script_runs_with_custom_name(self):
        BLACKBOARD.clear()
        with Policy(GlobalStore()) as p:
            with p.new_environment() as env:
                with env.use():
                    script(PATH, module_name="__test__").result()
                    self.assertEqual(BLACKBOARD.get("vpy_run_script_name"), "__test__")

    def test_can_get_and_set_variables(self):
        with Policy(GlobalStore()) as p:
            with p.new_environment() as env:
                with env.use():
                    script = variables({"a": 1})
                    script.result()
                    self.assertEqual(script.get_variable("a").result(), 1)

    def test_wrap_exceptions_wraps_exception(self):
        err = RuntimeError()
        try:
            with WrapAllErrors():
                raise err
        except ExecutionFailed as e:
            self.assertIs(e.parent_error, err)
        else:
            self.fail("Wrap all errors swallowed the exception")
