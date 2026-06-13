import sys
import tempfile
import unittest
from pathlib import Path

from sixseven_counter.models import ClipSegment
from sixseven_counter.render import (
    build_concat_command,
    build_normalize_command,
    build_ytdlp_command,
    render_supercut,
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

