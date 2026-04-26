from __future__ import annotations

import unittest
from datetime import datetime

from podcast_catalogue.models import Location, Podcast, TargetAudience


class PodcastModelTests(unittest.TestCase):
    def test_model_serialization_aliasing(self) -> None:
        """
        Verify that Pydantic properly aliases fields (e.g. age_groups -> ageGroups)
        when dumping via model_dump(by_alias=True).
        """
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

        data = podcast.model_dump(by_alias=True)
        
        # Check key aliasing
        self.assertIn("hostInformation", data)
        self.assertNotIn("host_information", data)
        
        self.assertIn("targetAudience", data)
        target = data["targetAudience"]
        self.assertIn("ageGroups", target)
        self.assertNotIn("age_groups", target)
        
        self.assertIn("isPopular", data)
        self.assertTrue(data["isPopular"])

    def test_exporter_integration(self):
        from podcast_catalogue.exporter import podcasts_to_typescript
        
        podcast = Podcast(title="Test", description="Test Desc")
        ts_output = podcasts_to_typescript([podcast], var_name="TEST_DATA")
        
        self.assertIn("export const TEST_DATA: Podcast[] =", ts_output)
        self.assertIn('"title": "Test"', ts_output)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
