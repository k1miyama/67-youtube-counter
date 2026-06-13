import sys
import tempfile
import unittest
from pathlib import Path

from sixseven_counter.models import ClipSegment
from sixseven_counter.render import (
    build_concat_command,
    build_normalize_command,
    build_ytdlp_command,
    build_ytdlp_options,
    render_supercut,
    reset_ytdlp_ffmpeg_location,
    set_ytdlp_ffmpeg_location,
)


class RenderTests(unittest.TestCase):
    def test_builds_ytdlp_section_command(self):
        segment = ClipSegment(index=1, start=1.25, end=3.5, match_ids=["confirmed_001"])
        command = build_ytdlp_command(
            url="https://youtu.be/dQw4w9WgXcQ",
            segment=segment,
            output_template=Path("clips/clip_001.%(ext)s"),
            quality=720,
            ffmpeg_path="ffmpeg",
        )
        self.assertEqual(command[:3], [sys.executable, "-m", "yt_dlp"])
        self.assertIn("--download-sections", command)
        self.assertIn("*1.250-3.500", command)
        self.assertIn("bv*[height<=720]+ba/b[height<=720]/best", command)

    def test_builds_ffmpeg_commands(self):
        normalize = build_normalize_command(Path("in.webm"), Path("out.mp4"), "ffmpeg")
        self.assertIn("libx264", normalize)
        concat = build_concat_command(Path("concat.txt"), Path("67_supercut.mp4"), "ffmpeg")
        self.assertEqual(concat[:4], ["ffmpeg", "-y", "-f", "concat"])

    def test_builds_ytdlp_options_for_in_process_download(self):
        segment = ClipSegment(index=1, start=1.25, end=3.5, match_ids=["confirmed_001"])

        def fake_range_func(chapters, ranges):
            return {"chapters": chapters, "ranges": ranges}

        opts = build_ytdlp_options(
            segment=segment,
            output_template=Path("clips/clip_001.%(ext)s"),
            quality=720,
            ffmpeg_path="ffmpeg",
            download_range_func=fake_range_func,
        )
        self.assertEqual(opts["format"], "bv*[height<=720]+ba/b[height<=720]/best")
        self.assertEqual(opts["download_ranges"], {"chapters": [], "ranges": [[1.25, 3.5]]})
        self.assertEqual(opts["outtmpl"], {"default": "clips\\clip_001.%(ext)s" if sys.platform == "win32" else "clips/clip_001.%(ext)s"})
        self.assertTrue(opts["force_keyframes_at_cuts"])

    def test_sets_and_resets_ytdlp_ffmpeg_location(self):
        class FakeLocation:
            value = None
            reset_token = None

            @classmethod
            def set(cls, value):
                cls.value = value
                return "token"

            @classmethod
            def reset(cls, token):
                cls.reset_token = token

        class FakeFFmpegPostProcessor:
            _ffmpeg_location = FakeLocation

        token = set_ytdlp_ffmpeg_location("ffmpeg-path", FakeFFmpegPostProcessor)
        reset_ytdlp_ffmpeg_location(token, FakeFFmpegPostProcessor)

        self.assertEqual(FakeLocation.value, "ffmpeg-path")
        self.assertEqual(FakeLocation.reset_token, "token")

    def test_dry_run_writes_command_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = render_supercut(
                url="https://youtu.be/dQw4w9WgXcQ",
                segments=[ClipSegment(index=1, start=1.0, end=2.0, match_ids=["confirmed_001"])],
                run_dir=Path(tmp),
                quality=720,
                dry_run=True,
                ffmpeg_path="ffmpeg",
            )
            self.assertEqual(result.output_path, Path(tmp) / "67_supercut.mp4")
            self.assertTrue((Path(tmp) / "render_commands.txt").exists())


if __name__ == "__main__":
    unittest.main()
