"""Phase 4 acceptance: security surface tests.

PRODUCTION_PLAN.md Phase 4 acceptance: 401 without token; ingest rejects
metadata-endpoint SSRF URLs; correction tool rejects regex patterns and
accepts literal names; DJ bundle response contains no directive/instruction
keys.
"""
import json
import os

import pytest

pytest.importorskip("mcp", reason="server.py requires the optional 'mcp' extra")

TEST_TOKEN = "test-secret-token"
os.environ.setdefault("GOLDMINE_API_TOKEN", TEST_TOKEN)

from podcast_catalogue import server


# ── HTTP bridge (requires the http extra) ──────────────────────────────────

fastapi = pytest.importorskip("fastapi", reason="prism_http requires the optional 'http' extra")
from fastapi.testclient import TestClient
from podcast_catalogue.prism_http import app

AUTH = {"Authorization": f"Bearer {os.environ['GOLDMINE_API_TOKEN']}"}


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


class TestBearerAuth:
    def test_api_route_401_without_token(self, client):
        assert client.get("/api/v1/shows").status_code == 401

    def test_api_route_401_with_wrong_token(self, client):
        r = client.get("/api/v1/shows", headers={"Authorization": "Bearer wrong"})
        assert r.status_code == 401

    def test_api_route_ok_with_token(self, client):
        assert client.get("/api/v1/shows", headers=AUTH).status_code == 200

    def test_health_root_open(self, client):
        assert client.get("/").status_code == 200

    def test_startup_refuses_without_token(self, monkeypatch):
        monkeypatch.delenv("GOLDMINE_API_TOKEN", raising=False)
        with pytest.raises(RuntimeError, match="GOLDMINE_API_TOKEN"):
            with TestClient(app):
                pass


class TestIngestSSRFGuard:
    def test_metadata_endpoint_rejected(self, client):
        r = client.post("/api/v1/ingest", json={"url": "http://169.254.169.254/latest/meta-data/"}, headers=AUTH)
        assert r.status_code == 403

    def test_arbitrary_host_rejected(self, client):
        r = client.post("/api/v1/ingest", json={"url": "https://evil.example.com/crawl-me"}, headers=AUTH)
        assert r.status_code == 403

    def test_non_http_scheme_rejected(self, client):
        r = client.post("/api/v1/ingest", json={"url": "file:///etc/passwd"}, headers=AUTH)
        assert r.status_code == 403

    def test_allowlisted_host_accepted(self, client):
        r = client.post(
            "/api/v1/ingest",
            json={"url": "https://www.abc.net.au/listen/programs/conversations", "deep_crawl": False},
            headers=AUTH,
        )
        assert r.status_code == 200

    def test_oversized_content_rejected(self, client):
        r = client.post("/api/v1/ingest", json={"content": "x" * (256 * 1024 + 1)}, headers=AUTH)
        assert r.status_code == 413


# ── MCP tool layer ─────────────────────────────────────────────────────────

class TestCorrectionHardening:
    def test_regex_pattern_rejected(self, tmp_path, monkeypatch):
        result = server.register_entity_correction(".*", "Anything")
        assert result.startswith("Rejected")

    def test_regex_metacharacters_rejected(self):
        result = server.register_entity_correction(r"\bBargara\b", "Barbara")
        assert result.startswith("Rejected")

    def test_overlong_pattern_rejected(self):
        result = server.register_entity_correction("x" * 201, "Y")
        assert result.startswith("Rejected")

    def test_literal_name_accepted(self, tmp_path, monkeypatch):
        import podcast_catalogue.entity_registry as er
        monkeypatch.setattr(er, "REGISTRY_FILE", str(tmp_path / "registry.json"))
        monkeypatch.setattr(server, "data_path", lambda *p: str(tmp_path.joinpath(*p)))

        result = server.register_entity_correction("Bargara", "Barbara")
        assert result.startswith("Successfully registered")

        audit = tmp_path / "corrections_audit.log"
        assert audit.exists(), "accepted corrections must be audit-logged"
        entry = json.loads(audit.read_text().strip())
        assert entry["pattern"] == "Bargara"
        assert entry["replacement"] == "Barbara"


class TestDJBundleNoDirectives:
    def test_bundle_contains_no_agent_directives(self, monkeypatch):
        fake = {
            "title": "Show", "episodes": [
                {"title": "Ep", "vibe": {"tone": ["Calm"], "complexity": 0.5}}
            ],
        }
        monkeypatch.setattr(server.store, "podcasts", {"show": fake})
        result = json.loads(server.get_dj_session_bundle("Show", "Ep"))
        assert "directive" not in result
        assert "instruction" not in result
        assert "current_context" in result


class TestSearchCaps:
    @pytest.mark.anyio
    async def test_overlong_query_rejected(self):
        result = await server.search_catalogue("x" * 501)
        assert "error" in json.loads(result)
