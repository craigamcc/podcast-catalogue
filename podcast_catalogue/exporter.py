from __future__ import annotations

from typing import Iterable

from .models import Podcast


def podcasts_to_typescript(podcasts: Iterable[Podcast], var_name: str = "MOCKED_PODCASTS") -> str:
    entries = [podcast.to_typescript() for podcast in podcasts]
    joined = ",\n  ".join(entries)
    return f"export const {var_name}: Podcast[] = [\n  {joined}\n];\n"
