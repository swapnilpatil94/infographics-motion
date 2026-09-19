"""Delivery derivatives from the 9:16 master.

HONEST LIMITATION: the art (sets, rigs) is authored portrait-native, so a true 16:9 *composition* (re-staged, re-framed sets) is not
implemented. `reframe_16x9` is the best fallback: the vertical film, full height, centred over a blurred + darkened + slightly
zoomed copy of itself (the standard 'blur-pad' pillarbox). It is labelled `*_16x9_blurpad.mp4` everywhere so nobody mistakes it
for a native widescreen render.
"""
import subprocess


def reframe_16x9(src, dst, w=1920, h=1080):
    fg_w = int(h * 9 / 16) // 2 * 2
    vf = (f"[0:v]split=2[a][b];"
          f"[a]scale={w}:{w * 16 // 9}:force_original_aspect_ratio=increase,crop={w}:{h},gblur=sigma=38,eq=brightness=-0.16:saturation=0.85[bg];"
          f"[b]scale={fg_w}:{h}[fg];"
          f"[bg][fg]overlay=(W-w)/2:0,format=yuv420p[v]")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-filter_complex", vf, "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
           "-c:a", "copy", "-movflags", "+faststart", dst]
    subprocess.run(cmd, check=True)
    return dst


def reframe_vertical_window(src, dst, t0, t1):
    """Cut a standalone vertical Short out of the master (stream copy would drift on non-keyframes, so re-encode)."""
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-ss", str(t0), "-t", str(t1 - t0), "-i", src, "-c:v", "libx264", "-preset", "medium", "-crf", "20",
           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", dst]
    subprocess.run(cmd, check=True)
    return dst
