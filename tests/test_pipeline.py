"""Tests for pipeline.py — stage composition and pipeline execution."""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock, AsyncMock

from podcast_catalogue.pipeline import (
    Stage, Pipeline, PipelineContext, build_pipeline,
    ALL_STAGES, DEFAULT_STAGE_ORDER,
    DiscoverStage, ParseStage, EnrichStage, DeepCrawlStage,
    TranscribeStage, AIEnrichStage, IndexStage,
)
from podcast_catalogue.catalogue import CatalogueConfig
from podcast_catalogue.models import Podcast


class MockStage(Stage):
    """A stage that appends a marker to each podcast description."""
    name = "mock"

    def __init__(self, marker: str):
        self.marker = marker

    async def process(self, podcasts, ctx):
        for p in podcasts:
            p.description = (p.description or "") + f"[{self.marker}]"
        return podcasts


class TestPipeline(unittest.TestCase):

    def test_stages_run_in_order(self):
        """Verify that stages execute sequentially and transform data cumulatively."""
        p = Podcast(title="Test Show", description="")
        stage_a = MockStage("A")
        stage_b = MockStage("B")
        stage_c = MockStage("C")

        pipeline = Pipeline([stage_a, stage_b, stage_c])
        ctx = PipelineContext(session=None, config=None)

        result = asyncio.run(pipeline.run([p], ctx))

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].description, "[A][B][C]")

    def test_empty_pipeline(self):
        """An empty pipeline should pass data through unchanged."""
        p = Podcast(title="Test", description="original")
        pipeline = Pipeline([])
        ctx = PipelineContext(session=None, config=None)

        result = asyncio.run(pipeline.run([p], ctx))
        self.assertEqual(result[0].description, "original")


class TestBuildPipeline(unittest.TestCase):

    def test_single_stage_selection(self):
        """--stage ai-enrich should create a pipeline with only AIEnrichStage."""
        config = CatalogueConfig(sitemap_url="https://example.com", stage="ai-enrich")
        pipeline = build_pipeline(config, stage_name="ai-enrich")
        self.assertEqual(len(pipeline.stages), 1)
        self.assertIsInstance(pipeline.stages[0], AIEnrichStage)

    def test_full_pipeline_with_all_flags(self):
        """Full pipeline with all flags should include all 7 stages."""
        config = CatalogueConfig(
            sitemap_url="https://example.com",
            enrich=True,
            fetch_audio=True,
            transcribe=True,
            ai_enrich=True,
        )
        pipeline = build_pipeline(config, stage_name="all")
        stage_names = [s.name for s in pipeline.stages]

        self.assertIn("discover", stage_names)
        self.assertIn("parse", stage_names)
        self.assertIn("enrich", stage_names)
        self.assertIn("deep-crawl", stage_names)
        self.assertIn("transcribe", stage_names)
        self.assertIn("ai-enrich", stage_names)
        self.assertIn("index", stage_names)

    def test_minimal_pipeline(self):
        """Pipeline with no optional flags should only have discover + parse."""
        config = CatalogueConfig(sitemap_url="https://example.com")
        pipeline = build_pipeline(config, stage_name="all")
        stage_names = [s.name for s in pipeline.stages]

        self.assertEqual(stage_names, ["discover", "parse"])

    def test_invalid_stage_raises(self):
        """An invalid stage name should raise ValueError."""
        config = CatalogueConfig(sitemap_url="https://example.com")
        with self.assertRaises(ValueError):
            build_pipeline(config, stage_name="nonexistent")


class TestAllStagesRegistered(unittest.TestCase):

    def test_all_stages_in_registry(self):
        self.assertEqual(len(ALL_STAGES), 7)
        for name in DEFAULT_STAGE_ORDER:
            self.assertIn(name, ALL_STAGES)

    def test_stage_classes_have_name(self):
        for name, cls in ALL_STAGES.items():
            instance = cls()
            self.assertEqual(instance.name, name)


class TestDiscoverStageSkipsExisting(unittest.TestCase):

    def test_skips_if_podcasts_already_loaded(self):
        """DiscoverStage should skip network calls if podcasts are pre-loaded."""
        existing = [Podcast(title="Pre-loaded Show")]
        stage = DiscoverStage()
        ctx = PipelineContext(session=None, config=None)

        result = asyncio.run(stage.process(existing, ctx))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].title, "Pre-loaded Show")


if __name__ == "__main__":
    unittest.main()
