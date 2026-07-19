"""
Shared fixtures for E2E tests.
Ensures deterministic test isolation by resetting global state before each test.
"""
import pytest

pytest.importorskip("mcp", reason="server.py requires the optional 'mcp' extra (pip install -e .[mcp])")

from podcast_catalogue.server import store, DataStore


@pytest.fixture(autouse=True)
def reset_store(tmp_path):
    """Reset the global DataStore before each test to prevent cross-test contamination.

    Critically, this also redirects the store's persistence to an isolated temp
    file. Otherwise a test that exercises ingest (which calls save_data +
    load_data) would rewrite the real data/universe.jsonl from the wiped test
    state — which is exactly how the e2e Snipd-ingest test clobbered the real
    catalogue once the e2e suite became runnable.
    """
    # Save original state
    original_podcasts = store.podcasts
    original_episodes_index = store.episodes_index
    original_episodes_by_id = store.episodes_by_id
    original_search = getattr(store, '_original_search', store.search)
    original_data_file = store.data_file

    # Reset to clean state, isolated from the real catalogue file
    store.podcasts = {}
    store.episodes_index = []
    store.episodes_by_id = {}
    store.search = original_search  # restore in case a test monkeypatched it
    store.data_file = str(tmp_path / "test_universe.jsonl")

    yield store

    # Restore original state after test
    store.podcasts = original_podcasts
    store.episodes_index = original_episodes_index
    store.episodes_by_id = original_episodes_by_id
    store.search = original_search
    store.data_file = original_data_file


@pytest.fixture
def seeded_store(reset_store):
    """Provides a DataStore pre-loaded with representative test data."""
    s = reset_store

    s.podcasts = {
        "conversations": {
            "title": "Conversations",
            "description": "In-depth interviews with remarkable Australians. Including stories from Queensland.",
            "hostInformation": "Richard Fidler",
            "averageRating": 4.8,
            "ratingCount": 2400,
            "primaryGenre": "Society & Culture",
            "appleGenres": ["Society & Culture", "Personal Journals"],
            "isPopular": True,
            "isAwardWinning": True,
            "applePodcastPage": "https://podcasts.apple.com/au/podcast/conversations/id1",
            "spotifyPodcastPage": "https://open.spotify.com/show/test1",
            "vibe": {"tone": ["Contemplative", "Warm"], "complexity": 0.6},
            "narrativeHook": "The voices that shape Australia.",
            "sourceOrganization": "ABC Australia",
            "genre": "interview",
            "license": "all_rights_reserved",
            "originLocation": {"country": "Australia", "state": "Queensland"},
            "episodes": [
                {
                    "title": "The Bushfire Survivor",
                    "description": "A harrowing account of survival.",
                    "publishedAt": "2026-05-10T00:00:00Z",
                    "audioUrl": "https://mediacore.abc.net.au/test1.mp3",
                    "transcript": "This is a clean transcript of the episode. It discusses resilience and community recovery.",
                    "segments": [
                        {"text": "We lost everything in the fire.", "start": 10.0, "end": 25.0, "speaker": "Guest A"},
                        {"text": "The community came together.", "start": 30.0, "end": 45.0, "speaker": "Richard Fidler"},
                    ],
                    "chapters": [
                        {"title": "The Day It Happened", "summary": "Guest A recounts the initial impact.", "startTime": 0, "endTime": 300},
                        {"title": "Recovery", "summary": "How the community rebuilt.", "startTime": 300, "endTime": 600},
                    ],
                    "highlights": [
                        {
                            "title": "We lost everything",
                            "reason": "Emotional peak of the narrative.",
                            "category": "PEAK",
                            "startTime": 10.0,
                            "endTime": 25.0,
                            "claimStatus": "confirmed",
                            "sourceAnchor": {"transcriptText": "We lost everything in the fire.", "timestampStart": 10.0, "timestampEnd": 25.0},
                        }
                    ],
                    "entities": ["Bushfire", "Queensland", "Community"],
                    "guests": [{"name": "Jane Smith", "expertise": "Disaster Recovery"}, {"name": "Bob Jones", "expertise": "Local Volunteer"}],
                    "vibe": {"tone": ["Emotional", "Serious"], "complexity": 0.7, "pace": "Measured"},
                    "engagement": {
                        "takeaway": "Resilience is forged in shared adversity.",
                        "keyStatistics": ["80% of homes lost", "3 months to rebuild"],
                        "bestQuotes": ["We lost everything in the fire."],
                        "whyListen": "A deeply human story of survival.",
                        "socialPost": "Must-listen: a bushfire survivor's incredible story.",
                    },
                    "contentRisk": {"level": "medium", "categories": ["disaster", "trauma"], "requiresHumanReview": False},
                    "aiProvenance": {"modelName": "gemini-2.5-flash", "generatedAt": "2026-05-10T12:00:00Z", "humanReviewed": False},
                    "genre": "interview",
                    "authorityScore": 0.85,
                }
            ],
        },
        "background briefing": {
            "title": "Background Briefing",
            "description": "Investigative journalism that goes deeper.",
            "averageRating": 4.5,
            "primaryGenre": "News",
            "appleGenres": ["News"],
            "isPopular": False,
            "vibe": {"tone": ["Analytical", "Serious"], "complexity": 0.9},
            "episodes": [],
        },
    }

    # Build the episode index from the seeded data (mirrors DataStore.load_data logic)
    import hashlib
    for title, podcast in s.podcasts.items():
        for ep in podcast.get("episodes", []):
            ep_title = ep.get("title")
            ep_id = hashlib.md5(f"{podcast['title']}:{ep_title}".encode()).hexdigest()[:12]
            episode_data = {
                "id": ep_id,
                "podcast_title": podcast["title"],
                "title": ep_title,
                "description": ep.get("description", ""),
                "publishedAt": ep.get("publishedAt", ""),
                "transcript": ep.get("transcript", ""),
                "hook": ep.get("narrativeHook") or ep.get("description", ""),
                "entities": ep.get("entities", []),
                "guests": ep.get("guests", []),
                "segments": ep.get("segments", []),
                "chapters": ep.get("chapters", []),
                "highlights": ep.get("highlights", []),
                "audio_url": ep.get("audioUrl") or ep.get("audio_url", ""),
                "vibe": ep.get("vibe", {}),
                "engagement": ep.get("engagement", {}),
                "apple_podcast_page": podcast.get("applePodcastPage"),
                "genre": ep.get("genre"),
                "content_risk": ep.get("contentRisk"),
                "ai_provenance": ep.get("aiProvenance"),
                "url": ep.get("url"),
            }
            s.episodes_index.append(episode_data)
            s.episodes_by_id[ep_id] = episode_data

    return s
