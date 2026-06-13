import unittest

from sixseven_counter.errors import SixSevenError
from sixseven_counter.youtube import parse_youtube_video_id


class ParseYoutubeVideoIdTests(unittest.TestCase):
    def test_parses_common_urls(self):
        cases = {
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ": "dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ?t=12": "dQw4w9WgXcQ",
            "https://m.youtube.com/shorts/dQw4w9WgXcQ": "dQw4w9WgXcQ",
            "https://www.youtube.com/live/dQw4w9WgXcQ": "dQw4w9WgXcQ",
            "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ": "dQw4w9WgXcQ",
            "dQw4w9WgXcQ": "dQw4w9WgXcQ",
        }
        for url, expected in cases.items():
            with self.subTest(url=url):
                self.assertEqual(parse_youtube_video_id(url), expected)

    def test_rejects_invalid_url(self):
        with self.assertRaises(SixSevenError):
            parse_youtube_video_id("https://example.com/watch?v=dQw4w9WgXcQ")


if __name__ == "__main__":
    unittest.main()

