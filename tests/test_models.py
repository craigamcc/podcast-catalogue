from __future__ import annotations

import unittest

from podcast_catalogue.models import Location, Podcast, TargetAudience


class PodcastModelTests(unittest.TestCase):
    def test_to_typescript_matches_expected_shape(self) -> None:
        podcast = Podcast(
            title="Example",
            host_information="Host",
            description="Desc",
            genres=["News", "Analysis"],
            language="English",
            target_audience=TargetAudience(
                interests=["news"],
                age_groups=["Adults"],
                location=Location(country="Australia"),
            ),
            recommendation_scenarios=["Commute"],
            recommendation_reasons=["Reason"],
            abc_podcast_page="https://abc",
            apple_podcast_page="https://apple",
            is_popular=True,
            is_award_winning=False,
        )

        expected = (
            "{\n"
            "    title: \"Example\",\n"
            "    hostInformation: \"Host\",\n"
            "    description: \"Desc\",\n"
            "    genre: \"News, Analysis\",\n"
            "    language: \"English\",\n"
            "    targetAudience: {\n"
            "      interests: [\"news\"],\n"
            "      ageGroups: [\"Adults\"],\n"
            "      location: { country: \"Australia\", state: null, city: null }\n"
            "    },\n"
            "    recommendationScenarios: [\"Commute\"],\n"
            "    recommendationReasons: [\"Reason\"],\n"
            "    abcPodcastPage: \"https://abc\",\n"
            "    applePodcastPage: \"https://apple\",\n"
            "    isPopular: true,\n"
            "    isAwardWinning: false\n"
            "  }"
        )

        self.assertEqual(podcast.to_typescript(), expected)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
