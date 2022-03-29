import gc
import weakref
import logging
import unittest

from vsengine._hospice import admit_environment


class Obj: pass


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
