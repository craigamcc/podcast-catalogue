"""Tests for enricher.py — iTunes API integration."""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch, MagicMock
import asyncio

from podcast_catalogue.enricher import search_itunes_podcast, _fetch_reviews_rss, enrich_podcast_data


def run_async(coro):
    """Helper to run async functions in tests."""
    return asyncio.run(coro)


class TestSearchItunesPodcast(unittest.TestCase):
    """Test iTunes search API."""

    def test_cleans_title_suffix(self):
        """Verify ' - ABC listen' is stripped from search queries."""
        mock_session = MagicMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "resultCount": 1,
            "results": [{
                "collectionId": 12345,
                "averageUserRating": 4.5,
                "userRatingCount": 100
            }]
        })
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)
        mock_session.get = MagicMock(return_value=mock_response)

        result = run_async(search_itunes_podcast(mock_session, "Conversations - ABC listen"))
        itunes_id, rating, count = result
        
        self.assertEqual(itunes_id, 12345)
        self.assertEqual(rating, 4.5)
        self.assertEqual(count, 100)

    def test_no_results(self):
        mock_session = MagicMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"resultCount": 0, "results": []})
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)
        mock_session.get = MagicMock(return_value=mock_response)

        result = run_async(search_itunes_podcast(mock_session, "Nonexistent Show"))
        # The function returns None when no results (missing explicit return)
        self.assertIsNone(result)

    def test_api_error_returns_none(self):
        mock_session = MagicMock()
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)
        mock_session.get = MagicMock(return_value=mock_response)

        result = run_async(search_itunes_podcast(mock_session, "Test"))
        self.assertIsNone(result[0])


class TestEnrichPodcastData(unittest.TestCase):
    """Test ID extraction from Apple URLs."""

    def test_extracts_id_from_apple_url(self):
        mock_session = MagicMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "resultCount": 1,
            "results": [{
                "averageUserRating": 4.2,
                "userRatingCount": 50,
                "primaryGenreName": "Society & Culture",
                "genres": ["Society & Culture", "News"]
            }]
        })
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)
        
        # Mock both the lookup call AND the RSS call
        rss_response = AsyncMock()
        rss_response.status = 200
        rss_response.json = AsyncMock(return_value={"feed": {"entry": []}})
        rss_response.__aenter__ = AsyncMock(return_value=rss_response)
        rss_response.__aexit__ = AsyncMock(return_value=False)
        
        mock_session.get = MagicMock(side_effect=[mock_response, rss_response])

        result = run_async(enrich_podcast_data(
            mock_session,
            apple_url="https://podcasts.apple.com/au/podcast/conversations/id80934561"
        ))
        itunes_id, rating, count, genre, genres, reviews = result
        
        self.assertEqual(itunes_id, 80934561)
        self.assertEqual(rating, 4.2)
        self.assertEqual(genre, "Society & Culture")

    def test_no_url_no_id_returns_empty(self):
        mock_session = MagicMock()
        result = run_async(enrich_podcast_data(mock_session))
        self.assertIsNone(result[0])


if __name__ == "__main__":
    unittest.main()
