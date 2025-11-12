from __future__ import annotations

import pathlib
import unittest

from podcast_catalogue import parser

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


class ParserTests(unittest.TestCase):
    def test_parse_podcast_links(self) -> None:
        index_html = (FIXTURES / "index.html").read_text(encoding="utf-8")
        links = parser.parse_podcast_links(index_html, "https://www.abc.net.au/listen/podcasts/a-z-podcasts")
        self.assertEqual(
            links,
            [
                "https://www.abc.net.au/listen/programs/another-show",
                "https://www.abc.net.au/listen/programs/external-show",
                "https://www.abc.net.au/listen/programs/sample-show",
            ],
        )

    def test_parse_flag_sections(self) -> None:
        flags_html = (FIXTURES / "flags.html").read_text(encoding="utf-8")
        flag_map = parser.parse_flag_sections(flags_html, "https://www.abc.net.au/listen/podcasts")
        self.assertEqual(
            flag_map,
            {
                "https://www.abc.net.au/listen/programs/sample-show": ["Popular"],
                "https://www.abc.net.au/listen/programs/other-show": ["Popular"],
                "https://www.abc.net.au/listen/programs/another-show": ["Award Winning"],
            },
        )

    def test_parse_podcast_detail(self) -> None:
        detail_html = (FIXTURES / "detail.html").read_text(encoding="utf-8")
        podcast = parser.parse_podcast_detail(
            detail_html,
            "https://www.abc.net.au/listen/programs/sample-show",
            flags=["Popular"],
        )
        self.assertEqual(podcast.title, "Sample Show")
        self.assertEqual(podcast.host_information, "Dr. Jane Doe")
        self.assertIn("Science", podcast.genres)
        self.assertTrue(podcast.is_popular)
        self.assertFalse(podcast.is_award_winning)
        self.assertEqual(podcast.apple_podcast_page, "https://podcasts.apple.com/sample-show")
        self.assertEqual(podcast.spotify_podcast_page, "https://open.spotify.com/show/sample")
        self.assertIn("Learning", podcast.recommendation_scenarios)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
