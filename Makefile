# GoldMine Ecosystem Automation (v5.0)

# Paths to consumer applications
SOTA_APP_DIR = ../AI\ Podcast/sota-app/public
DAISY_APP_DIR = ../Daisy-Podcasts/public
SENTINEL_DIR = ../The-Sentinel/data

# Unified Intelligence Universe
RAW_DATA = data/universe.jsonl

.PHONY: help export-sota export-daisy run-http diag test-e2e test-backend test-frontend

help:
	@echo "📡 PRISM Automation"
	@echo "  make export-sota   - Refresh SOTA app with Tier 0 catalogue"
	@echo "  make export-daisy  - Refresh Daisy app with Tier 1 intelligence"
	@echo "  make run-http      - Launch the FastAPI HTTP Bridge (Port 8000)"
	@echo "  make diag          - Run environmental diagnostics"
	@echo "  make test-e2e      - Run all E2E tests (Backend & Frontend)"
	@echo "  make test-backend  - Run Python backend E2E tests"
	@echo "  make test-frontend - Run Playwright UI E2E tests"

export-sota:
	@echo "🚀 Syncing Tier 0 Catalogue to SOTA App..."
	./.venv/bin/python3 -m podcast_catalogue.cli --input $(RAW_DATA) --format json --tier 0 --output "$(SOTA_APP_DIR)/catalogue.json"
	@echo "✅ SOTA export complete. Slim discovery catalogue refreshed."

export-daisy:
	@echo "🌼 Syncing Tier 1 Intelligence to Daisy..."
	./.venv/bin/python3 -m podcast_catalogue.cli --input $(RAW_DATA) --format json --tier 1 --output "$(DAISY_APP_DIR)/intelligence.json"
	@echo "✅ Daisy export complete. Intelligence graph refreshed."

run-http:
	@echo "🌉 Starting PRISM HTTP Bridge..."
	./.venv/bin/uvicorn podcast_catalogue.prism_http:app --reload --port 8000

diag:
	./.venv/bin/python3 -m podcast_catalogue.cli --check-env

test-backend:
	@echo "🧪 Running Backend E2E Tests..."
	PYTHONPATH=. ./.venv/bin/pytest tests/e2e -v

test-frontend:
	@echo "🎭 Running Frontend E2E Tests..."
	cd goldmine && npx playwright test

test-e2e: test-backend test-frontend
	@echo "🏁 All GoldMine E2E tests completed."
