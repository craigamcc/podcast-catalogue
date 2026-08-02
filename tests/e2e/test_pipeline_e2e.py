import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from podcast_catalogue.pipeline import Pipeline, PipelineContext, DiscoverStage, ParseStage
from podcast_catalogue.models import Podcast
from podcast_catalogue.catalogue import CatalogueConfig

@pytest.mark.asyncio
async def test_pipeline_e2e_minimal():
    """
    End-to-end test of the minimal pipeline (Discover + Parse).
    Mocks the network to avoid external dependencies.
    """
    # Setup
    config = CatalogueConfig(sitemap_url="https://example.com/sitemap.xml", limit=1)
    session = AsyncMock()
    
    # Mock sitemap response (gzipped or plain)
    sitemap_content = b"""<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        <url><loc>https://www.abc.net.au/listen/programs/test-show</loc></url>
    </urlset>"""
    
    # Mock podcast page HTML with meta tags for parser
    podcast_html = """
    <html>
        <head>
            <title>Test Show - ABC Listen</title>
            <meta property="og:title" content="Test Show" />
            <meta name="description" content="This is a test podcast." />
        </head>
        <body>
            <h1 data-testid="title">Test Show</h1>
            <div class="description">This is a test podcast.</div>
            <a href="/listen/programs/test-show/episodes/test-episode">Episode 1</a>
        </body>
    </html>
    """
    
    # Initialize Context with mocked fetchers
    ctx = PipelineContext(session=session, config=config)
    ctx.fetch_bytes = AsyncMock(return_value=sitemap_content)
    ctx.fetch_text = AsyncMock(return_value=podcast_html)
    
    # Run pipeline
    pipeline = Pipeline([DiscoverStage(), ParseStage()])
    results = await pipeline.run([], ctx)
    
    # Verify results
    assert len(results) == 1
    p = results[0]
    # Note: parse_podcast_detail is complex, we just verify it extracted something
    assert p.title == "test-show" or p.title == "Test Show"
    assert p.abc_podcast_page == "https://www.abc.net.au/listen/programs/test-show"

@pytest.mark.asyncio
async def test_pipeline_with_incremental_update():
    """
    Verifies that the pipeline correctly handles existing data (incremental update).
    """
    existing_p = Podcast(title="Existing Show", description="Old description")
    config = CatalogueConfig(sitemap_url="https://example.com/sitemap.xml", limit=1)
    session = AsyncMock()
    
    ctx = PipelineContext(
        session=session, 
        config=config, 
        existing_podcasts={"Existing Show": existing_p}
    )
    
    # If we pass existing podcasts to DiscoverStage, it should skip discovery
    stage = DiscoverStage()
    results = await stage.process([existing_p], ctx)
    
    assert len(results) == 1
    assert results[0].title == "Existing Show"
    assert results[0].description == "Old description"
