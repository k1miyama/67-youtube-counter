import json
import tempfile
import unittest
from pathlib import Path

from sixseven_counter.errors import SixSevenError
from sixseven_counter.manifest import write_manifests
from sixseven_counter.models import Match
from sixseven_counter.selection import (
    choices_for_review,
    default_choices,
    load_selection,
    review_run,
    save_selection,
    select_matches,
)


def match(match_id, kind):
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


class SelectionTests(unittest.TestCase):
    def test_defaults_confirmed_yes_possible_no(self):
        matches = [match("confirmed_001", "confirmed"), match("possible_001", "possible")]
        self.assertEqual(
            default_choices(matches),
            {"confirmed_001": True, "possible_001": False},
        )

    def test_existing_selection_overrides_defaults(self):
        matches = [match("confirmed_001", "confirmed"), match("possible_001", "possible")]
        choices = choices_for_review(matches, {"confirmed_001": False, "possible_001": True})
        self.assertEqual(choices, {"confirmed_001": False, "possible_001": True})

    def test_saves_and_loads_selection(self):
        matches = [match("confirmed_001", "confirmed"), match("possible_001", "possible")]
        with tempfile.TemporaryDirectory() as tmp:
            path = save_selection(Path(tmp), matches, {"confirmed_001": True}, completed=True)
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["selected_ids"], ["confirmed_001"])
            self.assertEqual(load_selection(Path(tmp)), {"confirmed_001": True, "possible_001": False})

    def test_load_selection_requires_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SixSevenError):
                load_selection(Path(tmp))

    def test_select_matches(self):
        matches = [match("confirmed_001", "confirmed"), match("possible_001", "possible")]
        selected = select_matches(matches, {"confirmed_001": False, "possible_001": True})
        self.assertEqual([item.id for item in selected], ["possible_001"])

    def test_interactive_review_saves_quit_state(self):
        confirmed = match("confirmed_001", "confirmed")
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
            answers = iter(["n", "q"])
            review_run(run_dir, input_func=lambda _: next(answers), output_func=lambda _: None)
            self.assertEqual(load_selection(run_dir), {"confirmed_001": False, "possible_001": False})


if __name__ == "__main__":
    unittest.main()

