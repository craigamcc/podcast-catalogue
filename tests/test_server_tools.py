"""Phase 2 acceptance: scripted MCP client against a 3-show fixture.

PRODUCTION_PLAN.md Phase 2 acceptance requires a scripted MCP client that
calls search_catalogue, get_podcast_details, get_episode_details,
walkie_talkie_pivot, and get_catalogue_stats against a 3-show fixture and
asserts non-error responses. Calls go through mcp.call_tool — the real MCP
dispatch path — not direct function calls.
"""
import json

import pytest

pytest.importorskip("mcp", reason="server.py requires the optional 'mcp' extra (pip install -e .[mcp])")

from podcast_catalogue import server


THREE_SHOWS = [
    {
        "title": "The Science Hour",
        "description": "Weekly deep dives into scientific discoveries.",
        "primaryGenre": "Science",
        "episodes": [
            {
                "title": "The Quantum Leap",
                "description": "Quantum computing explained.",
                "audioUrl": "https://example.com/quantum.mp3",
                "vibe": {"tone": ["Analytical"], "complexity": 0.8, "pace": "Moderate"},
                "highlights": [
                    {
                        "title": "Qubit basics",
                        "reason": "clear explanation of qubits",
                        "startTime": 30.0,
                        "endTime": 90.0,
                    }
                ],
            }
        ],
    },
    {
        "title": "History Uncovered",
        "description": "Stories from the archives.",
        "primaryGenre": "History",
        "episodes": [
            {
                "title": "The Lost Expedition",
                "description": "A vanished Antarctic voyage.",
                "audioUrl": "https://example.com/expedition.mp3",
                "vibe": {"tone": ["Investigative"], "complexity": 0.5, "pace": "Slow"},
            }
        ],
    },
    {
        "title": "Morning Brief",
        "description": "Daily news in ten minutes.",
        "primaryGenre": "News",
        "episodes": [],
    },
]


@pytest.fixture()
def three_show_store():
    """Seed the global store with exactly three shows, restoring afterwards."""
    original_podcasts = server.store.podcasts
    original_index = server.store.episodes_index
    original_by_id = server.store.episodes_by_id

    server.store.podcasts = {p["title"].lower(): p for p in THREE_SHOWS}
    server.store.episodes_index = [
        {**ep, "podcast_title": p["title"]}
        for p in THREE_SHOWS
        for ep in p.get("episodes", [])
    ]
    server.store.episodes_by_id = {}

    yield server.store

    server.store.podcasts = original_podcasts
    server.store.episodes_index = original_index
    server.store.episodes_by_id = original_by_id


async def _call(tool_name, args):
    result = await server.mcp.call_tool(tool_name, args)
    assert result, f"{tool_name} returned an empty result"
    text = result[0].text
    assert text, f"{tool_name} returned empty text"
    return text


async def test_search_catalogue(three_show_store):
    text = await _call("search_catalogue", {"query": "quantum"})
    assert "error" not in text.lower() or "Quantum" in text


async def test_get_podcast_details(three_show_store):
    text = await _call("get_podcast_details", {"title": "The Science Hour"})
    payload = json.loads(text)
    assert "error" not in payload


async def test_get_episode_details(three_show_store):
    text = await _call(
        "get_episode_details",
        {"podcast_title": "The Science Hour", "episode_title": "The Quantum Leap"},
    )
    payload = json.loads(text)
    assert "error" not in payload
    assert payload["title"] == "The Quantum Leap"


async def test_walkie_talkie_pivot(three_show_store):
    text = await _call(
        "walkie_talkie_pivot",
        {"current_episode_title": "The Quantum Leap", "user_interruption": "qubits"},
    )
    payload = json.loads(text)
    assert payload["status"] in {"pivoted_within_episode", "pivoted_new_show", "no_match"}
    assert payload["status"] == "pivoted_within_episode"
    assert payload["next_snip"]["startTime"] == 30.0


async def test_get_catalogue_stats(three_show_store):
    text = await _call("get_catalogue_stats", {})
    payload = json.loads(text)
    assert payload["total_shows"] == 3
    assert payload["total_episodes"] == 2


async def test_get_catalogue_stats_empty_store(three_show_store):
    server.store.episodes_index = []
    text = await _call("get_catalogue_stats", {})
    payload = json.loads(text)
    assert payload["total_episodes"] == 0
    assert payload["enriched_coverage"] == "0.0%"
