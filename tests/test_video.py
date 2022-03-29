import typing as t
import unittest

from vsengine._testutils import forcefully_unregister_policy, use_standalone_policy

from vapoursynth import core, PresetFormat, VideoFormat, GRAY8
from vapoursynth import VideoNode, VideoFrame

from vsengine.video import frame, frames, render


AnyFormat = t.Union[PresetFormat, VideoFormat]


class TestVideo(unittest.TestCase):
    def setUp(self) -> None:
        forcefully_unregister_policy()
        use_standalone_policy()

    def tearDown(self) -> None:
        forcefully_unregister_policy()

    @staticmethod
    def generate_video(length: int = 3, width: int = 1, height: int = 1, format: AnyFormat = GRAY8) -> VideoNode:
        clip = core.std.BlankClip(length=length, width=width, height=height, format=format, fpsden=1001, fpsnum=24000)
        def _add_frameno(n: int, f: VideoFrame) -> VideoFrame:
            fout = f.copy()
            fout.props["FrameNumber"] = n
            return fout
        clip = core.std.ModifyFrame(clip=clip, clips=clip, selector=_add_frameno)
        return clip

    def test_single_frame(self):
        clip = self.generate_video()
        with frame(clip, 0).result(timeout=0.1) as f:
            self.assertEqual(f.props["FrameNumber"], 0)

        with frame(clip, 1).result(timeout=0.1) as f:
            self.assertEqual(f.props["FrameNumber"], 1)
        
        with frame(clip, 2).result(timeout=0.1) as f:
            self.assertEqual(f.props["FrameNumber"], 2)

    def test_multiple_frames(self):
        clip = self.generate_video()
        for nf, f in enumerate(frames(clip)):
            self.assertEqual(f.props["FrameNumber"], nf)

    def test_multiple_frames_closes_after_iteration(self):
        clip = self.generate_video()

        it = iter(frames(clip))
        f1 = next(it)

        try:
            f2 = next(it)
        except:
            f1.close()
            raise

        try:
            with self.assertRaises(RuntimeError):
                f1.props
        finally:
            f2.close()
            next(it).close()
    
    def test_multiple_frames_without_closing(self):
        clip = self.generate_video()
        for nf, f in enumerate(frames(clip, close=False)):
            self.assertEqual(f.props["FrameNumber"], nf)
            f.close()

    def test_render(self):
        clip = self.generate_video()
        data = b"".join((f[1] for f in render(clip)))
        self.assertEqual(data, b"\0\0\0")

    def test_render_y4m(self):
        clip = self.generate_video()
        data = b"".join((f[1] for f in render(clip, y4m=True)))
        self.assertEqual(data, b"YUV4MPEG2 Cmono W1 H1 F24000:1001 Ip A0:0 XLENGTH=3\nFRAME\n\0FRAME\n\0FRAME\n\0")
