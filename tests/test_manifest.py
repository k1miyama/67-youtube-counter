import json
import tempfile
import unittest
from pathlib import Path

from sixseven_counter.manifest import write_manifests
from sixseven_counter.models import ClipSegment, Match


class ManifestTests(unittest.TestCase):
    def test_writes_json_and_csv(self):
        match = Match(
            id="confirmed_001",
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
        with tempfile.TemporaryDirectory() as tmp:
            json_path, csv_path = write_manifests(
                Path(tmp),
                video_id="dQw4w9WgXcQ",
                source_url="https://youtu.be/dQw4w9WgXcQ",
                metadata={"title": "Test"},
                confirmed=[match],
                possible=[],
                segments=[ClipSegment(index=1, start=0.0, end=4.0, match_ids=["confirmed_001"])],
                options={"padding": 2.0},
            )
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["counts"]["confirmed"], 1)
            self.assertIn("confirmed_001", csv_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

