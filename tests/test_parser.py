from __future__ import annotations

import unittest
import json
from podcast_catalogue import parser

class ParserTests(unittest.TestCase):
    def test_parse_podcast_detail(self) -> None:
        # Mock the Next.js data structure
        next_data = {
            "props": {
                "pageProps": {
                    "pageAnalytics": {
                        "document": {
                            "program": {"title": "Sample Show"}
                        }
                    },
                    "heroImageWithCTAPrepared": {
                        "title": "Sample Show",
                        "heroImagePrepared": {"imgSrc": "https://abc.net.au/image.jpg"}
                    },
                    "headTagsPagePrepared": {
                        "description": "A sample description."
                    },
                    "programCollectionPrepared": {
                        "items": [
                            {
                                "cardTitle": "Episode 1",
                                "description": "Ep 1 desc",
                                "cardMediaIndicatorPrepared": {"duration": "300"},
                                "to": "/listen/programs/sample-show/ep1"
                            }
                        ]
                    }
                }
            }
        }
        
        # Create HTML with the script tag
        html = f"""
        <html>
            <body>
                <script id="__NEXT_DATA__" type="application/json">
                    {json.dumps(next_data)}
                </script>
                <a href="https://podcasts.apple.com/sample-show">Apple Podcasts</a>
            </body>
        </html>
        """

        podcast = parser.parse_podcast_detail(
            html,
            "https://www.abc.net.au/listen/programs/sample-show",
            flags=["Popular"],
        )
        
        self.assertEqual(podcast.title, "Sample Show")
        self.assertEqual(podcast.description, "A sample description.")
        self.assertEqual(podcast.image_url, "https://abc.net.au/image.jpg")
        self.assertTrue(podcast.is_popular)
        self.assertEqual(podcast.apple_podcast_page, "https://podcasts.apple.com/sample-show")
        
        # Check episodes
        self.assertEqual(len(podcast.episodes), 1)
        self.assertEqual(podcast.episodes[0].title, "Episode 1")
        self.assertEqual(podcast.episodes[0].duration, "300")
        self.assertEqual(podcast.episodes[0].url, "https://www.abc.net.au/listen/programs/sample-show/ep1")

if __name__ == "__main__":
    unittest.main()
