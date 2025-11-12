from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional

from .client import FetchResult, HttpClient, load_local
from .exporter import podcasts_to_typescript
from .models import Podcast
from .parser import parse_flag_sections, parse_podcast_detail, parse_podcast_links


@dataclass
class CatalogueConfig:
    index_url: str
    flags_url: Optional[str] = None
    index_file: Optional[str] = None
    flags_file: Optional[str] = None
    output_var: str = "MOCKED_PODCASTS"


class CatalogueBuilder:
    def __init__(self, http_client: Optional[HttpClient] = None):
        self.http_client = http_client or HttpClient()

    def _load(self, url: Optional[str], file_path: Optional[str]) -> Optional[FetchResult]:
        if file_path:
            return load_local(file_path)
        if url:
            return self.http_client.fetch(url)
        return None

    def build(self, config: CatalogueConfig) -> List[Podcast]:
        index_result = self._load(config.index_url, config.index_file)
        if not index_result:
            raise ValueError("An index URL or file must be provided")

        flag_result = self._load(config.flags_url, config.flags_file)
        flags_map = (
            parse_flag_sections(flag_result.content, config.flags_url or flag_result.url)
            if flag_result
            else {}
        )

        podcast_links = parse_podcast_links(index_result.content, config.index_url)
        podcasts: List[Podcast] = []
        for link in podcast_links:
            try:
                detail_result = self.http_client.fetch(link)
            except Exception as exc:  # pragma: no cover - network errors
                print(f"Failed to fetch {link}: {exc}")
                continue
            flags = flags_map.get(link, [])
            podcast = parse_podcast_detail(detail_result.content, link, flags=flags)
            podcasts.append(podcast)
        return podcasts

    def export_typescript(self, podcasts: Iterable[Podcast], var_name: str = "MOCKED_PODCASTS") -> str:
        return podcasts_to_typescript(podcasts, var_name=var_name)
