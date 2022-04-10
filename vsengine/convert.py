# vs-engine
# Copyright (C) 2022  cid-chan
# This project is licensed under the EUPL-1.2
# SPDX-License-Identifier: EUPL-1.2
import functools
import typing as t
import vapoursynth as vs

from vsengine._helpers import use_inline, wrap_variable_size, EnvironmentTypes


# The heuristics code for nodes.
# Usually the nodes are tagged so this heuristics code is not required.
@functools.lru_cache
def yuv_heuristic(width: int, height: int) -> t.Mapping[str, str]:
    result = {}

    if width >= 3840:
        result["matrix_in_s"] = "2020ncl"
    elif width >= 1280:
        result["matrix_in_s"] = "709"
    elif height == 576:
        result["matrix_in_s"] = "470bg"
    else:
        result["matrix_in_s"] = "170m"

    if width >= 3840:
        result["transfer_in_s"] = "st2084"
    elif width >= 1280:
        result["transfer_in_s"] = "709"
    elif height == 576:
        result["transfer_in_s"] = "470bg"
    else:
        result["transfer_in_s"] = "601"

    if width >= 3840:
        result["primaries_in_s"] = "2020"
    elif width >= 1280:
        result["primaries_in_s"] = "709"
    elif height == 576:
        result["primaries_in_s"] = "470bg"
    else:
        result["primaries_in_s"] = "170m"

    result["range_in_s"] = "limited"

    # ITU-T H.273 (07/2021), Note at the bottom of pg. 20
    if width >= 3840:
        result["chromaloc_in_s"] = "top_left"
    else:
        result["chromaloc_in_s"] = "left"

    return result


def to_rgb(
        clip: vs.VideoNode,
        env: t.Optional[EnvironmentTypes] = None,
        *,
        # Output: RGB bitdepth
        bits_per_sample: int = 8,

        # Input: YUV
        scaler: t.Union[str, t.Callable[..., vs.VideoNode]] = "Spline36",
        default_matrix: t.Optional[str] = None,
        default_transfer: t.Optional[str] = None,
        default_primaries: t.Optional[str] = None,
        default_range: t.Optional[str] = None,
        default_chromaloc: t.Optional[str] = None,
) -> vs.VideoNode:
    """
    This function converts a clip to RGB.

    :param clip: The clip to convert to RGB
    :param env: The environment the clip belongs to. (Optional if you don't use EnvironmentPolicies)
    :param bits_per_sample: The bits per sample the resulting RGB clip should have.
    :param scaler: The name scaler function in core.resize that should be used to convert YUV to RGB.
    :param default_*: Manually override the defaults predicted by the heuristics.
    :param yuv_heuristic: The heuristic function that takes the frame size and returns a set of yuv-metadata. (For test purposes)
    """
    with use_inline("to_rgb", env):
        core = vs.core.core
        real_rgb24 = core.get_video_format(vs.RGB24)
        target_rgb = real_rgb24.replace(bits_per_sample=bits_per_sample)

    def _convert_yuv(c: vs.VideoNode):
        # We make yuv_heuristic not configurable so the heuristic
        # 
        args = {
            **yuv_heuristic(c.width, c.height)
        }

        # Override heuristics with default values if specified.
        if default_matrix is not None:
            args["matrix_in_s"] = default_matrix
        if default_transfer is not None:
            args["transfer_in_s"] = default_transfer
        if default_primaries is not None:
            args["primaries_in_s"] = default_primaries
        if default_range is not None:
            args["range_in_s"] = default_range
        if default_chromaloc is not None:
            args["chromaloc_in_s"] = default_chromaloc

        # Detect subsampling
        if clip.format.subsampling_w != 0 or clip.format.subsampling_h != 0:
            # Allowing to manually specify a scaler function allows for testing of the args.
            resizer = getattr(core.resize, scaler) if isinstance(scaler, str) else scaler
        else:
            resizer = core.resize.Point

        return resizer(
            c,
            format=target_rgb,
            **args
        )

    def _actually_resize(c: vs.VideoNode) -> vs.VideoNode:
        if c.format.color_family == vs.YUV:
            c = _convert_yuv(c)

        if c.format == vs.GRAY:
            c = c.std.RemoveFrameProps("_Matrix")

        if c.format.color_family != vs.RGB or c.format.bits_per_sample != bits_per_sample:
            c = core.resize.Point(c, format=target_rgb)

        return c

    with use_inline("to_rgb", env):
        return wrap_variable_size(
            clip,
            force_assumed_format=target_rgb,
            func=_actually_resize
        )

