# vs-engine
# Copyright (C) 2022  cid-chan
# This project is licensed under the EUPL-1.2
# SPDX-License-Identifier: EUPL-1.2

import gc
import weakref
import logging
import contextlib
import unittest

from vsengine._hospice import admit_environment, any_alive, freeze, unfreeze


class Obj: pass


@contextlib.contextmanager
def hide_logs():
    logging.disable(logging.CRITICAL)
    try:
        yield
    finally:
        logging.disable(logging.NOTSET)

class HospiceTest(unittest.TestCase):

    def test_hospice_delays_connection(self):
        o1 = Obj()
        o2 = Obj()
        o2r = weakref.ref(o2)

        admit_environment(o1, o2)
        del o2
        del o1

        self.assertIsNotNone(o2r())

        gc.collect()
        self.assertIsNotNone(o2r())

        # Stage-2 add-queue + Stage 2 proper
        gc.collect()
        gc.collect()

        self.assertIsNone(o2r())

    def test_hospice_is_delayed_on_alive_objects(self):
        o1 = Obj()
        o2 = Obj()
        o2r = weakref.ref(o2)

        admit_environment(o1, o2)
        del o1

        with self.assertLogs("vsengine._hospice", level=logging.WARN):
            gc.collect()
            gc.collect()

        del o2
        self.assertIsNotNone(o2r())
        gc.collect()
        gc.collect()
        gc.collect()

        self.assertIsNone(o2r())

    def test_hospice_reports_alive_objects_correctly(self):
        o1 = Obj()
        o2 = Obj()
        admit_environment(o1, o2)
        del o1

        with hide_logs():
            self.assertTrue(any_alive(), "The hospice did report that all objects are not alive anymore. This is obviously not true.")
        del o2

        self.assertFalse(any_alive(), "The hospice did report that there are some objects left alive. This is obviously not true.")

    def test_hospice_can_forget_about_cores_safely(self):
        o1 = Obj()
        o2 = Obj()
        admit_environment(o1, o2)
        del o1

        with hide_logs():
            self.assertTrue(any_alive(), "The hospice did report that all objects are not alive anymore. This is obviously not true.")
        freeze()
        self.assertFalse(any_alive(), "The hospice did report that there are some objects left alive. This is obviously not true.")

        unfreeze()
        with hide_logs():
            self.assertTrue(any_alive(), "The hospice did report that all objects are not alive anymore. This is obviously not true.")
        del o2

        gc.collect()
        gc.collect()
