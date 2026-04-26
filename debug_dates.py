import asyncio
import aiohttp
from podcast_catalogue.catalogue import CatalogueBuilder, CatalogueConfig
from podcast_catalogue.pipeline import PipelineContext, build_pipeline

async def debug():
    config = CatalogueConfig(output="debug.jsonl", limit=1, filter_pattern="Conversations", deep_crawl=True)
    builder = CatalogueBuilder()
    
    async with aiohttp.ClientSession() as session:
        ctx = PipelineContext(session=session, config=config, fetch_text=builder._fetch_text)
        pipeline = build_pipeline(config)
        podcasts = await pipeline.run([], ctx)
        
        if podcasts:
            p = podcasts[0]
            if p.episodes:
                ep = p.episodes[0]
                print(f"Title: {ep.title}")
                print(f"URL: {ep.url}")
                print(f"Audio URL: {ep.audio_url}")
                print(f"Published At: {ep.published_at}")
                print(f"JSON Dump: {ep.model_dump_json(by_alias=True)}")

if __name__ == "__main__":
    asyncio.run(debug())
