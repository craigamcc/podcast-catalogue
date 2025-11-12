from __future__ import annotations

import argparse
from pathlib import Path

from .catalogue import CatalogueBuilder, CatalogueConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate podcast catalogue from ABC Listen pages")
    parser.add_argument("--index-url", default="https://www.abc.net.au/listen/podcasts/a-z-podcasts", help="URL for the ABC A-Z podcasts page")
    parser.add_argument("--flags-url", default="https://www.abc.net.au/listen/podcasts", help="URL for the ABC podcasts landing page with Popular/Award sections")
    parser.add_argument("--index-file", help="Local HTML file to use instead of fetching the index page")
    parser.add_argument("--flags-file", help="Local HTML file to use instead of fetching the flags page")
    parser.add_argument("--output", help="Path to the output TypeScript file", required=True)
    parser.add_argument("--var-name", default="MOCKED_PODCASTS", help="Name of the exported constant")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    builder = CatalogueBuilder()
    config = CatalogueConfig(
        index_url=args.index_url,
        flags_url=args.flags_url,
        index_file=args.index_file,
        flags_file=args.flags_file,
        output_var=args.var_name,
    )

    podcasts = builder.build(config)
    ts_content = builder.export_typescript(podcasts, var_name=args.var_name)

    output_path = Path(args.output)
    output_path.write_text(ts_content, encoding="utf-8")
    print(f"Wrote {len(podcasts)} podcasts to {output_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
