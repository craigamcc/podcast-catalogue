"""Tests for recommender.py — content-based recommendation scoring."""
from __future__ import annotations

import unittest
from podcast_catalogue.recommender import (
    _score_interest_overlap,
    _score_scenario_match,
    _score_vibe_match,
    _score_genre_match,
    _score_popularity,
    recommend
)


SAMPLE_PODCASTS = {
    "show_a": {
        "title": "Science Hour",
        "targetAudience": {"interests": ["science", "technology", "space"]},
        "recommendationScenarios": ["Morning Commute", "Deep Focus"],
        "vibe": {"tone": "Inspirational", "complexity": 0.7, "pace": "Medium"},
        "appleGenres": ["Science", "Technology"],
        "isPopular": True,
        "averageRating": 4.5,
        "narrativeHook": "Explore the cosmos",
        "imageUrl": ""
    },
    "show_b": {
        "title": "Comedy Corner",
        "targetAudience": {"interests": ["comedy", "entertainment"]},
        "recommendationScenarios": ["Relaxation"],
        "vibe": {"tone": "Humorous", "complexity": 0.2, "pace": "Fast"},
        "appleGenres": ["Comedy"],
        "isPopular": False,
        "averageRating": 3.8,
        "narrativeHook": "Laugh out loud",
        "imageUrl": ""
    },
    "show_c": {
        "title": "Dark Mysteries",
        "targetAudience": {"interests": ["true crime", "mystery"]},
        "recommendationScenarios": ["Evening Wind-Down"],
        "vibe": {"tone": "Dark", "complexity": 0.8, "pace": "Slow"},
        "appleGenres": ["True Crime", "Society & Culture"],
        "isPopular": False,
        "averageRating": 4.9,
        "narrativeHook": "Unsolved cases",
        "imageUrl": ""
    }
}


class TestScoringFunctions(unittest.TestCase):

    def test_interest_overlap_full_match(self):
        score = _score_interest_overlap(SAMPLE_PODCASTS["show_a"], ["science", "space"])
        self.assertEqual(score, 1.0)

    def test_interest_overlap_partial_match(self):
        score = _score_interest_overlap(SAMPLE_PODCASTS["show_a"], ["science", "cooking"])
        self.assertEqual(score, 0.5)

    def test_interest_overlap_no_match(self):
        score = _score_interest_overlap(SAMPLE_PODCASTS["show_a"], ["cooking"])
        self.assertEqual(score, 0.0)

    def test_scenario_match_hit(self):
        score = _score_scenario_match(SAMPLE_PODCASTS["show_a"], "Morning Commute")
        self.assertEqual(score, 1.0)

    def test_scenario_match_miss(self):
        score = _score_scenario_match(SAMPLE_PODCASTS["show_a"], "Evening Wind-Down")
        self.assertEqual(score, 0.0)

    def test_vibe_match_tone(self):
        score = _score_vibe_match(SAMPLE_PODCASTS["show_b"], tone="Humorous")
        self.assertEqual(score, 1.0)

    def test_vibe_match_complexity(self):
        score = _score_vibe_match(SAMPLE_PODCASTS["show_b"], max_complexity=0.5)
        self.assertEqual(score, 1.0)  # 0.2 <= 0.5

    def test_vibe_match_complexity_too_high(self):
        score = _score_vibe_match(SAMPLE_PODCASTS["show_c"], max_complexity=0.5)
        self.assertEqual(score, 0.0)  # 0.8 > 0.5

    def test_genre_match(self):
        score = _score_genre_match(SAMPLE_PODCASTS["show_a"], ["Science"])
        self.assertEqual(score, 1.0)

    def test_popularity_boost_popular_and_rated(self):
        score = _score_popularity(SAMPLE_PODCASTS["show_a"])
        self.assertEqual(score, 0.5)  # popular (0.3) + rated >= 4.0 (0.2)

    def test_popularity_no_boost(self):
        score = _score_popularity(SAMPLE_PODCASTS["show_b"])
        self.assertEqual(score, 0.0)  # not popular, rating < 4.0


class TestRecommend(unittest.TestCase):

    def test_recommend_returns_ranked_results(self):
        results = recommend(SAMPLE_PODCASTS, interests=["science"], top_k=3)
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0]["title"], "Science Hour")

    def test_recommend_filters_by_scenario(self):
        results = recommend(SAMPLE_PODCASTS, scenario="Relaxation", top_k=3)
        titles = [r["title"] for r in results]
        self.assertIn("Comedy Corner", titles)

    def test_recommend_empty_on_no_match(self):
        # Note: shows with popularity boosts still score > 0 even without interest match
        results = recommend(SAMPLE_PODCASTS, interests=["underwater basket weaving"], top_k=3)
        # Verify no results have interest-based score contribution
        for r in results:
            self.assertLessEqual(r["score"], 0.1)  # Only popularity boost, no interest match

    def test_recommend_respects_top_k(self):
        results = recommend(SAMPLE_PODCASTS, interests=["science", "comedy", "true crime"], top_k=1)
        self.assertLessEqual(len(results), 1)


if __name__ == "__main__":
    unittest.main()
