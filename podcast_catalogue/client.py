from __future__ import annotations

import pathlib
from dataclasses import dataclass
from typing import Optional
from urllib import request


@dataclass
class FetchResult:
    url: str
    content: str


class HttpClient:
    def __init__(self, user_agent: str = "Mozilla/5.0 (compatible; PodcastCatalogueBot/1.0)"):
        self.user_agent = user_agent

    def fetch(self, url: str, timeout: int = 30) -> FetchResult:
        req = request.Request(url, headers={"User-Agent": self.user_agent})
        with request.urlopen(req, timeout=timeout) as response:
            content = response.read().decode("utf-8", errors="replace")
        return FetchResult(url=url, content=content)


def load_local(path: str) -> FetchResult:
    file_path = pathlib.Path(path)
    content = file_path.read_text(encoding="utf-8")
    return FetchResult(url=file_path.as_uri(), content=content)
