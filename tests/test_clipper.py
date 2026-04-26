"""Tests for clipper.py — audio clip extraction."""
from __future__ import annotations

import asyncio
import os
import tempfile
import unittest
from unittest.mock import patch, AsyncMock, MagicMock

from podcast_catalogue.clipper import (
    extract_clip, _slugify, _clip_filename, _format_timestamp
)


class TestSlugify(unittest.TestCase):

    def test_basic_title(self):
        self.assertEqual(_slugify("ABC News Daily"), "abc_news_daily")

    def test_special_characters(self):
        self.assertEqual(_slugify("What's That? — A Show!"), "what_s_that_a_show")

    def test_long_title_truncated(self):
        slug = _slugify("A" * 100)
        self.assertLessEqual(len(slug), 60)

    def test_empty_string(self):
        self.assertEqual(_slugify(""), "")


class TestClipFilename(unittest.TestCase):

    def test_deterministic(self):
        f1 = _clip_filename("Show A", "Episode 1", 10.0, 40.0)
        f2 = _clip_filename("Show A", "Episode 1", 10.0, 40.0)
        self.assertEqual(f1, f2)

    def test_includes_timestamps(self):
        filename = _clip_filename("Show", "Ep", 120.5, 180.0)
        self.assertIn("120", filename)
        self.assertIn("180", filename)

    def test_ends_with_mp3(self):
        filename = _clip_filename("Show", "Ep", 0, 30)
        self.assertTrue(filename.endswith(".mp3"))


class TestFormatTimestamp(unittest.TestCase):

    def test_zero(self):
        self.assertEqual(_format_timestamp(0), "00:00:00.000")

    def test_seconds(self):
        self.assertEqual(_format_timestamp(45.5), "00:00:45.500")

    def test_minutes(self):
        self.assertEqual(_format_timestamp(125.0), "00:02:05.000")

    def test_hours(self):
        self.assertEqual(_format_timestamp(3661.5), "01:01:01.500")


class TestExtractClipValidation(unittest.TestCase):

    def test_negative_start_raises(self):
        with self.assertRaises(ValueError):
            asyncio.run(extract_clip("http://x.mp3", -1.0, 10.0))

    def test_end_before_start_raises(self):
        with self.assertRaises(ValueError):
            asyncio.run(extract_clip("http://x.mp3", 50.0, 30.0))

    def test_empty_url_raises(self):
        with self.assertRaises(ValueError):
            asyncio.run(extract_clip("", 0.0, 10.0))


class TestExtractClipCaching(unittest.TestCase):

    def test_returns_cached_file(self):
        """If the clip file already exists, it should be returned without calling ffmpeg."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a fake cached file
            filename = _clip_filename("Show", "Ep", 10, 40)
            cached_path = os.path.join(tmpdir, filename)
            with open(cached_path, "w") as f:
                f.write("fake mp3 data")

            result = asyncio.run(extract_clip(
                "http://x.mp3", 10.0, 40.0,
                output_dir=tmpdir, podcast_title="Show", episode_title="Ep"
            ))
            self.assertEqual(result, os.path.abspath(cached_path))


if __name__ == "__main__":
    unittest.main()
