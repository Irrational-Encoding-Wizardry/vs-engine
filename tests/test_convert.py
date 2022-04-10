import os
import json
import unittest

from vapoursynth import core
import vapoursynth as vs

from vsengine._testutils import forcefully_unregister_policy, use_standalone_policy
from vsengine.convert import to_rgb, yuv_heuristic


DIR = os.path.dirname(__file__)
# Generated with 
# mediainfo -Output=JOSN -Full [Filenames]
# | jq '.media.track[] | select(."@type" == "Video") | {matrix: .matrix_coefficients, width: .Width, height: .Height, primaries: .colour_primaries, transfer: .transfer_characteristics, chromaloc: .ChromaSubsampling_Position} | select(.matrix)' | jq -s
#
# or (if the previous jq command does not work)
#
# mediainfo -Output=JOSN -Full [Filenames]
# | jq '.[].media.track[] | select(."@type" == "Video") | {matrix: .matrix_coefficients, width: .Width, height: .Height, primaries: .colour_primaries, transfer: .transfer_characteristics, chromaloc: .ChromaSubsampling_Position} | select(.matrix)' | jq -s
PATH = os.path.join(DIR, "fixtures", "heuristic_examples.json")
with open(PATH, "r") as h:
    HEURISTIC_EXAMPLES = json.load(h)

MATRIX_MAPPING = {
    "BT.2020 non-constant": "2020ncl",
    "BT.709": "709",
    "BT.470 System B/G": "470bg",
    "BT.601": "170m"
}
TRANSFER_MAPPING = {
    "PQ": "st2084",
    "BT.709": "709",
    "BT.470 System B/G": "470bg",
    "BT.601": "601"
}
PRIMARIES_MAPPING = {
    "BT.2020": "2020",
    "BT.709": "709",
    "BT.601 PAL": "470bg",
    "BT.601 NTSC": "170m"
}
CHROMALOC_MAPPING = {
    None: "left",
    "Type 2": "top_left"
}


class TestToRGB(unittest.TestCase):
    def setUp(self) -> None:
        forcefully_unregister_policy()
        use_standalone_policy()

    def tearDown(self) -> None:
        forcefully_unregister_policy()

    def test_heuristics_provides_all_arguments(self):
        yuv = core.std.BlankClip(format=vs.YUV420P8)
        def _pseudo_scaler(c, **args):
            self.assertTrue("chromaloc_in_s" in args)
            self.assertTrue("range_in_s" in args)
            self.assertTrue("transfer_in_s" in args)
            self.assertTrue("primaries_in_s" in args)
            self.assertTrue("matrix_in_s" in args)
            return core.resize.Point(c, **args)

        to_rgb(yuv, scaler=_pseudo_scaler)

    def test_heuristics_with_examples(self):
        count_hits = 0
        count_misses = 0

        for example in HEURISTIC_EXAMPLES:
            w = int(example["width"])
            h = int(example["height"])

            result = yuv_heuristic(w, h)
            raw_primary = result["primaries_in_s"]
            raw_transfer = result["transfer_in_s"]
            raw_matrix = result["matrix_in_s"]
            raw_chromaloc = result["chromaloc_in_s"]

            if raw_primary != PRIMARIES_MAPPING[example["primaries"]]:
                count_misses += 1
            elif raw_transfer != TRANSFER_MAPPING[example["transfer"]]:
                count_misses += 1
            elif raw_matrix != MATRIX_MAPPING[example["matrix"]]:
                count_misses += 1
            elif raw_chromaloc != CHROMALOC_MAPPING[example["chromaloc"]]:
                count_misses += 1
            else:
                count_hits += 1

        self.assertGreaterEqual(count_hits, count_misses)

    def test_converts_to_rgb24(self):
        # Should be sufficiently untagged. lel
        yuv8 = core.std.BlankClip(format=vs.YUV420P8)
        gray = core.std.BlankClip(format=vs.GRAY8)
        rgb = core.std.BlankClip(format=vs.RGB24)

        yuv16 = core.std.BlankClip(format=vs.YUV420P16)

        for clip in [yuv8, gray, rgb, yuv16]:
            self.assertEqual(int(to_rgb(clip).format), vs.RGB24)
            self.assertEqual(int(to_rgb(clip, bits_per_sample=16).format), vs.RGB48)

