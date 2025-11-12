# podcast-catalogue

Utilities for generating a TypeScript friendly podcast catalogue from ABC Listen metadata.

## Features

- Crawls the ABC A–Z podcast listing and collects each podcast page.
- Cross-references the ABC Listen landing page to mark shows flagged as **Popular** or **Award Winning**, exposing the values as `isPopular` and `isAwardWinning` booleans.
- Extracts structured podcast information from JSON-LD metadata when available.
- Captures external review links (Apple Podcasts, Spotify, YouTube, etc.) referenced by ABC and surfaces the Apple Podcasts URL via `applePodcastPage` in the export.
- Produces a ready-to-use TypeScript export that mirrors the expected `Podcast[]` shape used by LLM recommendation tooling, matching the catalogue examples shared above.

## Usage

1. Ensure you have Python 3.11 available.
2. Run the CLI, providing an output path for the generated TypeScript file:

```bash
python -m podcast_catalogue.cli --output data/podcasts.ts
```

Optional arguments:

- `--index-url`: Override the ABC A–Z listing URL.
- `--flags-url`: Override the ABC landing page URL for Popular/Award Winning data.
- `--index-file`: Use a local HTML file instead of fetching the A–Z listing.
- `--flags-file`: Use a local HTML file instead of fetching the landing page (useful when network access is restricted).
- `--var-name`: Change the exported constant name (default `MOCKED_PODCASTS`).

When running in a network-restricted environment, first download the necessary HTML pages and supply them via `--index-file` and `--flags-file`. The CLI will still visit each individual podcast link; use a tool such as `wget` to create a local mirror if full offline processing is required.

## Testing

Run the unit tests with:

```bash
python -m unittest discover
```
