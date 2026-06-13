import unittest

from sixseven_counter.matcher import find_sixseven_matches
from sixseven_counter.models import TranscriptSnippet


def snippet(text, start):
    return TranscriptSnippet(text=text, start=start, duration=1.0)


class MatcherTests(unittest.TestCase):
    def test_finds_confirmed_forms(self):
        result = find_sixseven_matches(
            [
                snippet("that was 67", 0),
                snippet("six seven", 2),
                snippet("six-seven", 4),
                snippet("sixty seven", 6),
                snippet("6 7", 8),
            ]
        )
        self.assertEqual(
            [match.pattern for match in result.confirmed],
            ["numeric_67", "six_seven", "six_seven", "sixty_seven", "numeric_6_7"],
        )
        self.assertEqual(result.possible, [])

    def test_finds_cross_snippet_match(self):
        result = find_sixseven_matches([snippet("six", 0), snippet("seven", 1)])
        self.assertEqual(len(result.confirmed), 1)
        self.assertEqual(result.confirmed[0].start, 0)
        self.assertEqual(result.confirmed[0].end, 2)

    def test_possible_matches_exclude_confirmed_tokens(self):
        result = find_sixseven_matches([snippet("six ideas and seven more then six seven", 0)])
        self.assertEqual(len(result.confirmed), 1)
        self.assertEqual([match.text.lower() for match in result.possible], ["six", "seven"])

    def test_case_and_punctuation(self):
        result = find_sixseven_matches([snippet("SIX, SEVEN!", 0)])
        self.assertEqual(len(result.confirmed), 1)
        self.assertEqual(result.confirmed[0].pattern, "six_seven")


if __name__ == "__main__":
    unittest.main()

