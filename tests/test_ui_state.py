import tempfile
import unittest
from pathlib import Path

from sixseven_counter.manifest import write_manifests
from sixseven_counter.models import Match
from sixseven_counter.selection import save_selection
from sixseven_counter.ui_state import (
    build_match_rows,
    can_render,
    choices_from_rows,
    load_match_rows,
    save_rows_selection,
    selected_matches_from_rows,
    toggle_row,
)


def match(match_id, kind="confirmed"):
    return Match(
        id=match_id,
        kind=kind,
        pattern="numeric_67",
        text="67" if kind == "confirmed" else "six",
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


class UiStateTests(unittest.TestCase):
    def test_build_rows_uses_default_review_choices(self):
        rows = build_match_rows([match("confirmed_001")], [match("possible_001", "possible")])
        self.assertEqual(choices_from_rows(rows), {"confirmed_001": True, "possible_001": False})
        self.assertTrue(can_render(rows))

    def test_existing_selection_overrides_loaded_rows(self):
        confirmed = match("confirmed_001")
        possible = match("possible_001", "possible")
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            write_manifests(
                run_dir,
                video_id="dQw4w9WgXcQ",
                source_url="https://youtu.be/dQw4w9WgXcQ",
                metadata={},
                confirmed=[confirmed],
                possible=[possible],
                segments=[],
                options={},
            )
            save_selection(
                run_dir,
                [confirmed, possible],
                {"confirmed_001": False, "possible_001": True},
                completed=True,
            )
            _, rows = load_match_rows(run_dir)
            self.assertEqual(choices_from_rows(rows), {"confirmed_001": False, "possible_001": True})

    def test_toggle_and_selected_matches(self):
        rows = build_match_rows([match("confirmed_001")], [match("possible_001", "possible")])
        rows = toggle_row(rows, "confirmed_001")
        self.assertFalse(can_render(rows))
        rows = toggle_row(rows, "possible_001")
        selected = selected_matches_from_rows(rows)
        self.assertEqual([item.id for item in selected], ["possible_001"])

    def test_save_rows_selection(self):
        rows = build_match_rows([match("confirmed_001")], [match("possible_001", "possible")])
        with tempfile.TemporaryDirectory() as tmp:
            path = save_rows_selection(Path(tmp), rows)
            self.assertTrue(path.exists())


if __name__ == "__main__":
    unittest.main()

