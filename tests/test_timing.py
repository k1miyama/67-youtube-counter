import unittest

from sixseven_counter.models import Match
from sixseven_counter.timing import assign_clip_bounds, merge_clip_segments


def match(match_id, start, end):
    return Match(
        id=match_id,
        kind="confirmed",
        pattern="numeric_67",
        text="67",
        transcript_text="67",
        start=start,
        end=end,
        token_start_index=0,
        token_end_index=0,
        snippet_start_index=0,
        snippet_end_index=0,
    )


class TimingTests(unittest.TestCase):
    def test_assigns_padding_and_clamps(self):
        bounded = assign_clip_bounds([match("confirmed_001", 1.0, 2.0)], 2.0, video_duration=3.0)
        self.assertEqual(bounded[0].clip_start, 0.0)
        self.assertEqual(bounded[0].clip_end, 3.0)

    def test_merges_overlapping_segments(self):
        bounded = assign_clip_bounds(
            [match("confirmed_001", 5, 6), match("confirmed_002", 7, 8), match("confirmed_003", 20, 21)],
            2,
        )
        segments = merge_clip_segments(bounded)
        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0].start, 3)
        self.assertEqual(segments[0].end, 10)
        self.assertEqual(segments[0].match_ids, ["confirmed_001", "confirmed_002"])


if __name__ == "__main__":
    unittest.main()

