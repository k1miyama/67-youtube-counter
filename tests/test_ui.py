import argparse
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sixseven_counter.cli import render_reviewed_run, scan_video
from sixseven_counter.manifest import write_manifests
from sixseven_counter.models import Match, TranscriptSnippet
from sixseven_counter.selection import save_selection


def match(match_id):
    return Match(
        id=match_id,
        kind="confirmed",
        pattern="numeric_67",
        text="67",
        transcript_text="that was 67",
        start=1.0,
        end=2.0,
        token_start_index=0,
        token_end_index=0,
        snippet_start_index=0,
        snippet_end_index=0,
        clip_start=0.0,
        clip_end=4.0,
    )


class UiWorkflowTests(unittest.TestCase):
    def test_scan_video_progress_callback(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = argparse.Namespace(
                url="https://youtu.be/dQw4w9WgXcQ",
                out=Path(tmp),
                padding=2.0,
                lang="en",
                quality=720,
                cookies=None,
            )
            messages = []
            with patch("sixseven_counter.cli.fetch_video_metadata") as metadata, patch(
                "sixseven_counter.cli.fetch_english_transcript"
            ) as transcript:
                metadata.return_value = {"id": "dQw4w9WgXcQ", "duration": 10}
                transcript.return_value = [TranscriptSnippet("that was 67", 1.0, 1.0)]
                result = scan_video(args, progress=messages.append)
            self.assertTrue((result.run_dir / "matches.json").exists())
            self.assertTrue(any("Reading metadata" in message for message in messages))

    def test_render_reviewed_run_progress_callback(self):
        selected = match("confirmed_001")
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            write_manifests(
                run_dir,
                video_id="dQw4w9WgXcQ",
                source_url="https://youtu.be/dQw4w9WgXcQ",
                metadata={},
                confirmed=[selected],
                possible=[],
                segments=[],
                options={},
            )
            save_selection(run_dir, [selected], {"confirmed_001": True}, completed=True)
            args = argparse.Namespace(
                run_dir=run_dir,
                quality=720,
                cookies=None,
                keep_clips=False,
                dry_run=True,
            )
            messages = []
            render_reviewed_run(args, ffmpeg_path="ffmpeg", progress=messages.append)
            self.assertTrue((run_dir / "render_commands.txt").exists())
            self.assertTrue(any("Rendering 1 selected" in message for message in messages))

    def test_tkinter_app_constructs_without_mainloop(self):
        try:
            import tkinter as tk
            from sixseven_counter.ui import SixSevenApp

            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk is not available: {exc}")

        try:
            root.withdraw()
            app = SixSevenApp(root, start_polling=False)
            self.assertEqual(app.root.title(), "67 Counter")
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()

