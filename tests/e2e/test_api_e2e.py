"""
PRISM HTTP API — End-to-End Tests.

Tests all FastAPI endpoints with proper isolation via the seeded_store fixture.
Covers happy paths, edge cases, validation, and error handling.
"""
import pytest

pytest.importorskip("fastapi", reason="prism_http requires the optional 'http' extra (pip install -e .[http])")

from fastapi.testclient import TestClient
from podcast_catalogue.prism_http import app

client = TestClient(app)


# ── Root Endpoint ──────────────────────────────────────────────────────────

class TestRootEndpoint:
    def test_returns_online_status(self):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "online"
        assert data["service"] == "PRISM Intelligence Engine"
        assert "total_podcasts" in data["stats"]
        assert "total_episodes" in data["stats"]

    def test_stats_reflect_empty_catalogue(self):
        """With autouse reset_store, the catalogue should be empty."""
        response = client.get("/")
        data = response.json()
        assert data["stats"]["total_podcasts"] == 0
        assert data["stats"]["total_episodes"] == 0


# ── Shows Endpoints ────────────────────────────────────────────────────────

class TestShowsEndpoint:
    def test_list_shows_empty(self):
        response = client.get("/api/v1/shows")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_shows_with_data(self, seeded_store):
        response = client.get("/api/v1/shows")
        assert response.status_code == 200
        shows = response.json()
        assert len(shows) == 2
        titles = [s["title"] for s in shows]
        assert "Conversations" in titles
        assert "Background Briefing" in titles

    def test_list_shows_filter_popular(self, seeded_store):
        response = client.get("/api/v1/shows?popular=true")
        assert response.status_code == 200
        shows = response.json()
        assert len(shows) == 1
        assert shows[0]["title"] == "Conversations"

    def test_list_shows_filter_genre(self, seeded_store):
        response = client.get("/api/v1/shows?genre=News")
        assert response.status_code == 200
        shows = response.json()
        assert len(shows) == 1
        assert shows[0]["title"] == "Background Briefing"

    def test_list_shows_filter_min_rating(self, seeded_store):
        response = client.get("/api/v1/shows?min_rating=4.6")
        assert response.status_code == 200
        shows = response.json()
        assert len(shows) == 1
        assert shows[0]["title"] == "Conversations"

    def test_list_shows_sorted_by_rating(self, seeded_store):
        response = client.get("/api/v1/shows")
        shows = response.json()
        ratings = [s.get("rating") or 0 for s in shows]
        assert ratings == sorted(ratings, reverse=True)

    def test_get_show_details_found(self, seeded_store):
        response = client.get("/api/v1/shows/conversations")
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Conversations"
        assert "jtbd_affinities" in data

    def test_get_show_details_not_found(self, seeded_store):
        response = client.get("/api/v1/shows/nonexistent-show-xyz")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


# ── Search Endpoint ────────────────────────────────────────────────────────

class TestSearchEndpoint:
    def test_search_with_results(self, seeded_store):
        response = client.get("/api/v1/search?q=Conversations")
        assert response.status_code == 200
        results = response.json()
        assert len(results) >= 1
        assert results[0]["title"] == "Conversations"

    def test_search_no_results(self, seeded_store):
        response = client.get("/api/v1/search?q=zzzznonexistenttopiczzz")
        assert response.status_code == 200
        results = response.json()
        assert len(results) == 0

    def test_search_min_length_validation(self):
        response = client.get("/api/v1/search?q=x")
        assert response.status_code == 422  # FastAPI validation error

    def test_search_missing_query(self):
        response = client.get("/api/v1/search")
        assert response.status_code == 422


# ── Ingest Endpoint ────────────────────────────────────────────────────────

class TestIngestEndpoint:
    def test_ingest_empty_body(self):
        response = client.post("/api/v1/ingest", json={})
        assert response.status_code == 400
        assert "url" in response.json()["detail"].lower() or "content" in response.json()["detail"].lower()

    def test_ingest_snipd_markdown(self):
        content = "---\nshow_title: Test Show\nepisode_title: Test Episode\n---\n### [Snip 1](http://example.com)\nSome content."
        response = client.post("/api/v1/ingest", json={"content": content})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ingestion_triggered"
        assert data["type"] == "snipd_markdown"

    def test_ingest_url_trigger(self):
        response = client.post("/api/v1/ingest", json={"url": "https://example.com/feed"})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ingestion_triggered"
        assert data["url"] == "https://example.com/feed"


# ── Recommend Endpoint ─────────────────────────────────────────────────────

class TestRecommendEndpoint:
    def test_recommend_returns_list(self, seeded_store):
        response = client.get("/api/v1/recommend")
        assert response.status_code == 200
        # Should return a list (possibly empty)
        assert isinstance(response.json(), list)


# ── Regional Pulse Endpoint ────────────────────────────────────────────────

class TestRegionalPulseEndpoint:
    def test_regional_pulse_not_found(self):
        response = client.get("/api/v1/pulse/regional/nonexistent_region")
        assert response.status_code == 404


# ── DataStore Internal Tests ───────────────────────────────────────────────

class TestDataStoreInternal:
    def test_hallucination_shield_clean(self, seeded_store):
        """Valid transcripts should pass the hallucination check."""
        from podcast_catalogue.server import store
        assert store._is_transcript_valid("This is a normal transcript with varied words.") is True

    def test_hallucination_shield_looped(self, seeded_store):
        """Repeated-word transcripts (Whisper hallucination) should be flagged."""
        from podcast_catalogue.server import store
        looped = " ".join(["the"] * 20)
        assert store._is_transcript_valid(looped) is False

    def test_hallucination_shield_empty(self, seeded_store):
        from podcast_catalogue.server import store
        assert store._is_transcript_valid("") is True
        assert store._is_transcript_valid(None) is True

    def test_search_method(self, seeded_store):
        from podcast_catalogue.server import store
        results = store.search("conversations")
        assert len(results) == 1
        assert results[0]["title"] == "Conversations"

    def test_search_description(self, seeded_store):
        from podcast_catalogue.server import store
        results = store.search("investigative")
        assert len(results) == 1
        assert results[0]["title"] == "Background Briefing"

    def test_get_details_exact(self, seeded_store):
        from podcast_catalogue.server import store
        result = store.get_details("conversations")
        assert result is not None
        assert result["title"] == "Conversations"

    def test_get_details_partial(self, seeded_store):
        from podcast_catalogue.server import store
        result = store.get_details("background")
        assert result is not None
        assert result["title"] == "Background Briefing"

    def test_get_details_not_found(self, seeded_store):
        from podcast_catalogue.server import store
        result = store.get_details("zzzzzzz")
        assert result is None

    def test_build_aggregate_vibes(self, seeded_store):
        """Verify that _build_aggregate_vibes derives show-level vibes from episode data."""
        from podcast_catalogue.server import store
        store._build_aggregate_vibes()
        conv = store.podcasts["conversations"]
        assert "vibe" in conv
        # The show vibe should now reflect the episode tones
        assert "tone" in conv["vibe"]
