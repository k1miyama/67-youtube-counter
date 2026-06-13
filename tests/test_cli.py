import tempfile
import unittest
from pathlib import Path

from sixseven_counter.cli import parse_cli_args, render_reviewed_run
from sixseven_counter.errors import SixSevenError
from sixseven_counter.manifest import write_manifests
from sixseven_counter.models import Match
from sixseven_counter.selection import save_selection


def match(match_id, kind="confirmed", clip_start=0.0, clip_end=4.0):
    return Match(
        id=match_id,
        kind=kind,
        pattern="numeric_67",
        text="67",
        transcript_text="that was 67",
        start=1.0,
        end=2.0,
        token_start_index=0,
        token_end_index=0,
        snippet_start_index=0,
        snippet_end_index=0,
        clip_start=clip_start,
        clip_end=clip_end,
    )


class CliTests(unittest.TestCase):
    def test_parses_subcommands(self):
        self.assertEqual(parse_cli_args(["scan", "https://youtu.be/dQw4w9WgXcQ"]).command, "scan")
        self.assertEqual(parse_cli_args(["review", "runs/dQw4w9WgXcQ"]).command, "review")
        args = parse_cli_args(["render", "runs/dQw4w9WgXcQ", "--quality", "480"])
        self.assertEqual(args.command, "render")
        self.assertEqual(args.quality, 480)

    def test_parses_legacy_url_invocation(self):
        args = parse_cli_args(["https://youtu.be/dQw4w9WgXcQ", "--padding", "1"])
        self.assertEqual(args.command, "legacy")
        self.assertEqual(args.padding, 1.0)

    def test_render_requires_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            write_manifests(
                run_dir,
                video_id="dQw4w9WgXcQ",
                source_url="https://youtu.be/dQw4w9WgXcQ",
                metadata={},
                confirmed=[match("confirmed_001")],
                possible=[],
                segments=[],
                options={},
            )
            args = parse_cli_args(["render", str(run_dir), "--dry-run"])
            with self.assertRaises(SixSevenError):
                render_reviewed_run(args)

    def test_render_from_selection_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            selected_match = match("confirmed_001")
            write_manifests(
                run_dir,
                video_id="dQw4w9WgXcQ",
                source_url="https://youtu.be/dQw4w9WgXcQ",
                metadata={},
                confirmed=[selected_match],
                possible=[],
                segments=[],
                options={},
            )
            save_selection(run_dir, [selected_match], {"confirmed_001": True}, completed=True)
            args = parse_cli_args(["render", str(run_dir), "--dry-run"])
            render_reviewed_run(args, ffmpeg_path="ffmpeg")
            self.assertTrue((run_dir / "render_commands.txt").exists())

    def test_render_empty_selection_skips_mp4(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            selected_match = match("confirmed_001")
            write_manifests(
                run_dir,
                video_id="dQw4w9WgXcQ",
                source_url="https://youtu.be/dQw4w9WgXcQ",
                metadata={},
                confirmed=[selected_match],
                possible=[],
                segments=[],
                options={},
            )
            save_selection(run_dir, [selected_match], {"confirmed_001": False}, completed=True)
            args = parse_cli_args(["render", str(run_dir), "--dry-run"])
            render_reviewed_run(args)
            self.assertFalse((run_dir / "render_commands.txt").exists())


if __name__ == "__main__":
    unittest.main()
