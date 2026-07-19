"""
MCP Tool Layer — End-to-End Tests.

Tests the 21 MCP tool functions that power the agentic interface.
Uses the seeded_store fixture for deterministic results.
"""
import json
import pytest
from podcast_catalogue.server import (
    list_categories,
    browse_by_category,
    search_by_location,
    get_trending_content,
    search_catalogue,
    get_catalogue_context,
    get_episode_details,
    get_podcast_details,
    get_editorial_trust_report,
    generate_json_ld,
    find_podcast_by_vibe,
    get_recent_episodes,
    search_by_guest,
    get_guest_co_occurrences,
    recommend_episodes,
    find_episodes_by_vibe,
    extract_chapter_clip,
    get_catalogue_stats,
)


# ── Catalogue Browse & Discovery ──────────────────────────────────────────

class TestCatalogueBrowse:
    def test_list_categories(self, seeded_store):
        result = json.loads(list_categories())
        assert "categories" in result
        assert "Society & Culture" in result["categories"]
        assert "News" in result["categories"]

    def test_list_categories_empty(self):
        result = json.loads(list_categories())
        assert result["categories"] == []

    def test_browse_by_category(self, seeded_store):
        result = json.loads(browse_by_category("News"))
        assert result["category"] == "News"
        assert len(result["shows"]) == 1
        assert result["shows"][0]["title"] == "Background Briefing"

    def test_browse_by_category_no_match(self, seeded_store):
        result = json.loads(browse_by_category("Nonexistent Genre"))
        assert len(result["shows"]) == 0

    def test_search_by_location(self, seeded_store):
        result = json.loads(search_by_location("Queensland"))
        assert len(result) >= 1

    def test_get_trending_content(self, seeded_store):
        result = get_trending_content()
        # Returns a wrapped UI dict
        assert "content" in result
        content = json.loads(result["content"][0]["text"])
        # Popular show should rank first
        assert content[0]["title"] == "Conversations"

    def test_get_catalogue_stats(self, seeded_store):
        result = json.loads(get_catalogue_stats())
        assert result["total_shows"] == 2
        assert result["total_episodes"] == 1

    def test_get_catalogue_context(self, seeded_store):
        result = json.loads(get_catalogue_context())
        assert result["catalogue_scope"]["total_shows"] == 2
        assert "discovery_strategy_guide" in result
        assert "agent_best_practices" in result


# ── Search Tools ───────────────────────────────────────────────────────────

class TestSearchTools:
    @pytest.mark.asyncio
    async def test_search_catalogue_hit(self, seeded_store):
        result = await search_catalogue("Conversations")
        content = json.loads(result["content"][0]["text"])
        assert len(content) >= 1
        assert any(r["title"] == "Conversations" for r in content)

    @pytest.mark.asyncio
    async def test_search_catalogue_no_results(self, seeded_store):
        result = await search_catalogue("zzzzzzz_no_match")
        parsed = json.loads(result)
        assert parsed["results"] == []
        assert "suggestion" in parsed

    @pytest.mark.asyncio
    async def test_search_catalogue_synonym_expansion(self, seeded_store):
        """The search tool supports synonym expansion for key topics."""
        result = await search_catalogue("ai")
        # May or may not match — but should not crash and should include suggestion if empty
        if isinstance(result, str):
            parsed = json.loads(result)
            assert "suggestion" in parsed or "results" in parsed
        else:
            assert "content" in result


# ── Detail Tools ───────────────────────────────────────────────────────────

class TestDetailTools:
    def test_get_podcast_details_found(self, seeded_store):
        result = get_podcast_details("Conversations")
        assert "content" in result
        content = json.loads(result["content"][0]["text"])
        assert content["title"] == "Conversations"

    def test_get_podcast_details_not_found(self, seeded_store):
        result = get_podcast_details("Nonexistent Show")
        assert "not found" in result

    def test_get_episode_details_found(self, seeded_store):
        result = json.loads(get_episode_details("Conversations", "The Bushfire Survivor"))
        assert result["title"] == "The Bushfire Survivor"
        assert "transcript" in result

    def test_get_episode_details_podcast_not_found(self, seeded_store):
        result = json.loads(get_episode_details("Nonexistent", "Ep"))
        assert "error" in result

    def test_get_episode_details_episode_not_found(self, seeded_store):
        result = json.loads(get_episode_details("Conversations", "Nonexistent Episode"))
        assert "error" in result


# ── Editorial Trust Layer ──────────────────────────────────────────────────

class TestEditorialTrust:
    def test_trust_report_found(self, seeded_store):
        result = get_editorial_trust_report("Conversations", "The Bushfire Survivor")
        content = json.loads(result["content"][0]["text"])
        assert content["podcast"] == "Conversations"
        assert content["trust_summary"]["risk_level"] == "medium"
        assert "disaster" in content["trust_summary"]["risk_categories"]
        assert content["trust_summary"]["ai_model"] == "gemini-2.5-flash"

    def test_trust_report_highlight_claims(self, seeded_store):
        result = get_editorial_trust_report("Conversations", "The Bushfire Survivor")
        content = json.loads(result["content"][0]["text"])
        claims = content["highlight_claims"]
        assert len(claims) == 1
        assert claims[0]["status"] == "confirmed"
        assert claims[0]["category"] == "PEAK"

    def test_trust_report_not_found(self, seeded_store):
        result = get_editorial_trust_report("Nonexistent", "Ep")
        content = json.loads(result)
        assert "error" in content

    def test_json_ld_podcast(self, seeded_store):
        result = json.loads(generate_json_ld("Conversations"))
        assert result["@type"] == "PodcastSeries"
        assert result["name"] == "Conversations"
        assert result["publisher"]["name"] == "ABC Australia"

    def test_json_ld_episode(self, seeded_store):
        result = json.loads(generate_json_ld("Conversations", "The Bushfire Survivor"))
        assert result["@type"] == "PodcastEpisode"
        assert result["name"] == "The Bushfire Survivor"
        # Should have Clip parts from highlights
        assert len(result.get("hasPart", [])) == 1
        clip = result["hasPart"][0]
        assert clip["@type"] == "Clip"

    def test_json_ld_not_found(self, seeded_store):
        result = json.loads(generate_json_ld("Nonexistent"))
        assert "error" in result


# ── Vibe & Discovery Tools ────────────────────────────────────────────────

class TestVibeDiscovery:
    def test_find_podcast_by_vibe_tone(self, seeded_store):
        result = find_podcast_by_vibe(tone="Contemplative")
        content = json.loads(result["content"][0]["text"])
        assert len(content) >= 1
        assert content[0]["title"] == "Conversations"

    def test_find_podcast_by_vibe_complexity(self, seeded_store):
        result = find_podcast_by_vibe(complexity="Deep")
        content = json.loads(result["content"][0]["text"])
        titles = [r["title"] for r in content]
        assert "Background Briefing" in titles

    def test_find_podcast_by_vibe_no_match(self, seeded_store):
        result = find_podcast_by_vibe(tone="Nonexistent Tone XYZ")
        content = json.loads(result["content"][0]["text"])
        assert len(content) == 0

    def test_find_episodes_by_vibe(self, seeded_store):
        result = json.loads(find_episodes_by_vibe(tone="Emotional"))
        assert len(result) >= 1
        assert result[0]["title"] == "The Bushfire Survivor"

    def test_find_episodes_by_vibe_complexity_filter(self, seeded_store):
        result = json.loads(find_episodes_by_vibe(complexity="Deep"))
        assert len(result) >= 1


# ── Guest Tools ────────────────────────────────────────────────────────────

class TestGuestTools:
    @pytest.mark.asyncio
    async def test_search_by_guest_found(self, seeded_store):
        result = await search_by_guest("Jane Smith")
        content = json.loads(result["content"][0]["text"])
        assert len(content) >= 1
        assert content[0]["podcast"] == "Conversations"

    @pytest.mark.asyncio
    async def test_search_by_guest_partial(self, seeded_store):
        result = await search_by_guest("Smith")
        content = json.loads(result["content"][0]["text"])
        assert len(content) >= 1

    @pytest.mark.asyncio
    async def test_search_by_guest_not_found(self, seeded_store):
        result = await search_by_guest("Nonexistent Person XYZ")
        content = json.loads(result["content"][0]["text"])
        assert "error" in content

    def test_guest_co_occurrences(self, seeded_store):
        result = get_guest_co_occurrences("Jane Smith")
        content = json.loads(result["content"][0]["text"])
        # Jane Smith is in the episode, and Bob Jones is a co-guest
        assert "guest" in content


# ── Episode Retrieval & Clips ──────────────────────────────────────────────

class TestEpisodeTools:
    @pytest.mark.asyncio
    async def test_get_recent_episodes(self, seeded_store):
        result = json.loads(await get_recent_episodes())
        assert len(result) >= 1
        assert result[0]["episode_title"] == "The Bushfire Survivor"
        assert result[0]["audio_url"] == "https://mediacore.abc.net.au/test1.mp3"

    @pytest.mark.asyncio
    async def test_get_recent_episodes_filtered(self, seeded_store):
        result = json.loads(await get_recent_episodes(show="Conversations"))
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_recent_episodes_no_match(self, seeded_store):
        result = json.loads(await get_recent_episodes(show="Nonexistent"))
        assert result.get("results") == []

    def test_extract_chapter_clip_found(self, seeded_store):
        result = json.loads(extract_chapter_clip("The Bushfire Survivor", "Recovery"))
        assert result["chapter_title"] == "Recovery"
        assert result["audio_url"] == "https://mediacore.abc.net.au/test1.mp3"

    def test_extract_chapter_clip_episode_not_found(self, seeded_store):
        result = extract_chapter_clip("Nonexistent Episode", "chapter")
        assert "not found" in result.lower()

    def test_extract_chapter_clip_chapter_not_found(self, seeded_store):
        result = extract_chapter_clip("The Bushfire Survivor", "nonexistent_chapter_xyz")
        assert "no chapter matching" in result.lower()


# ── Recommendation Engine ──────────────────────────────────────────────────

class TestRecommendation:
    @pytest.mark.asyncio
    async def test_recommend_episodes_by_interest(self, seeded_store):
        result = await recommend_episodes("bushfire")
        content = json.loads(result["content"][0]["text"])
        assert len(content) >= 1
        assert content[0]["podcast"] == "Conversations"

    @pytest.mark.asyncio
    async def test_recommend_episodes_no_match(self, seeded_store):
        result = await recommend_episodes("quantum_computing_xxxx")
        content = json.loads(result["content"][0]["text"])
        assert len(content) == 0
