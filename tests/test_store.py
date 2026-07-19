"""Phase 3 acceptance: atomic save, quarantine-not-drop, fabricated-link migration.

PRODUCTION_PLAN.md Phase 3 acceptance: prove atomic save, quarantine-not-drop,
and the fabricated-link migration against a fixture containing one poisoned
record. Runs against a temp data dir, never the real data/.
"""
import json
import os

import pytest

pytest.importorskip("mcp", reason="server.py requires the optional 'mcp' extra (pip install -e .[mcp])")

from podcast_catalogue.server import DataStore
from scripts.migrate_strip_fabricated import migrate


GOOD_SHOW = {
    "title": "Good Show",
    "description": "A well-formed record.",
    "episodes": [
        {
            "title": "Episode One",
            "vibe": {"tone": ["Calm"], "complexity": 0.5, "pace": "Slow"},
        }
    ],
}

POISONED_SHOW = {
    "title": "Poisoned Show",
    "description": "Carries a fabricated referral link.",
    "applePodcastPage": "https://podcasts.apple.com/au/search?term=Poisoned+Show",
    "episodes": [],
}


def write_jsonl(path, records, extra_raw_lines=()):
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
        for raw in extra_raw_lines:
            f.write(raw + "\n")


class TestQuarantineNotDrop:
    def test_bad_lines_quarantined_and_counted(self, tmp_path):
        data_file = tmp_path / "universe.jsonl"
        write_jsonl(data_file, [GOOD_SHOW], extra_raw_lines=['{"broken json… no closing brace'])

        store = DataStore()
        store.load_data(str(data_file))

        assert len(store.podcasts) == 1  # good record loaded
        quarantine = tmp_path / "universe.jsonl.quarantine.jsonl"
        assert quarantine.exists(), "bad line must be quarantined, not dropped"
        assert "broken json" in quarantine.read_text()

    def test_save_after_bad_line_does_not_lose_it(self, tmp_path):
        """The CRITICAL_REVIEW.md §3 data-loss scenario: bad line + save used to erase the line forever."""
        data_file = tmp_path / "universe.jsonl"
        bad_line = '{"title": "Recoverable Show", "episodes": [BROKEN'
        write_jsonl(data_file, [GOOD_SHOW], extra_raw_lines=[bad_line])

        store = DataStore()
        store.load_data(str(data_file))
        store.save_data(str(data_file))  # rewrites the file from memory

        # The rewritten file no longer has the bad line, but the quarantine does
        assert bad_line not in data_file.read_text()
        assert "Recoverable Show" in (tmp_path / "universe.jsonl.quarantine.jsonl").read_text()


class TestAtomicSave:
    def test_save_writes_via_tmp_and_replace(self, tmp_path):
        data_file = tmp_path / "universe.jsonl"
        write_jsonl(data_file, [GOOD_SHOW])

        store = DataStore()
        store.load_data(str(data_file))
        store.save_data(str(data_file))

        assert not (tmp_path / "universe.jsonl.tmp").exists(), "tmp file must be cleaned up"
        reloaded = [json.loads(l) for l in data_file.read_text().splitlines() if l.strip()]
        assert reloaded[0]["title"] == "Good Show"

    def test_failed_save_leaves_original_intact(self, tmp_path, monkeypatch):
        data_file = tmp_path / "universe.jsonl"
        write_jsonl(data_file, [GOOD_SHOW])
        original_content = data_file.read_text()

        store = DataStore()
        store.load_data(str(data_file))

        def boom(*a, **k):
            raise OSError("disk full")

        monkeypatch.setattr(json, "dumps", boom)
        store.save_data(str(data_file))  # must not raise, must not corrupt

        assert data_file.read_text() == original_content


class TestFabricatedLinkMigration:
    def test_poisoned_record_cleaned(self, tmp_path):
        data_file = tmp_path / "universe.jsonl"
        write_jsonl(data_file, [GOOD_SHOW, POISONED_SHOW])

        total, cleaned = migrate(str(data_file))
        assert total == 2
        assert cleaned == 1

        records = {r["title"]: r for r in (json.loads(l) for l in data_file.read_text().splitlines())}
        assert records["Poisoned Show"]["applePodcastPage"] is None
        assert "applePodcastPage" not in records["Good Show"] or not records["Good Show"].get("applePodcastPage")

    def test_idempotent(self, tmp_path):
        data_file = tmp_path / "universe.jsonl"
        write_jsonl(data_file, [GOOD_SHOW, POISONED_SHOW])

        migrate(str(data_file))
        after_first = data_file.read_text()
        total, cleaned = migrate(str(data_file))
        assert cleaned == 0
        assert data_file.read_text() == after_first

    def test_genuine_links_untouched(self, tmp_path):
        real = {
            "title": "Real Link Show",
            "applePodcastPage": "https://podcasts.apple.com/au/podcast/conversations/id80934561",
            "episodes": [],
        }
        data_file = tmp_path / "universe.jsonl"
        write_jsonl(data_file, [real])

        total, cleaned = migrate(str(data_file))
        assert cleaned == 0
        record = json.loads(data_file.read_text().strip())
        assert record["applePodcastPage"].endswith("id80934561")


class TestProvenanceDefaults:
    def test_enriched_episode_without_provenance_gets_honest_default(self, tmp_path):
        data_file = tmp_path / "universe.jsonl"
        write_jsonl(data_file, [GOOD_SHOW])  # has vibe, no aiProvenance

        store = DataStore()
        store.load_data(str(data_file))

        ep = store.episodes_index[0]
        assert ep["ai_provenance"] == {"modelName": "unknown", "humanReviewed": False}

    def test_existing_provenance_preserved(self, tmp_path):
        show = {
            "title": "Labeled Show",
            "episodes": [
                {
                    "title": "Labeled Episode",
                    "vibe": {"tone": ["Calm"], "complexity": 0.4, "pace": "Slow"},
                    "aiProvenance": {"modelName": "gemini-2.5", "humanReviewed": True},
                }
            ],
        }
        data_file = tmp_path / "universe.jsonl"
        write_jsonl(data_file, [show])

        store = DataStore()
        store.load_data(str(data_file))
        assert store.episodes_index[0]["ai_provenance"]["modelName"] == "gemini-2.5"

    def test_unenriched_episode_gets_no_provenance(self, tmp_path):
        show = {"title": "Plain Show", "episodes": [{"title": "Plain Episode"}]}
        data_file = tmp_path / "universe.jsonl"
        write_jsonl(data_file, [show])

        store = DataStore()
        store.load_data(str(data_file))
        assert store.episodes_index[0]["ai_provenance"] is None
