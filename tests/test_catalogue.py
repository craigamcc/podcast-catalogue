"""Tests for catalogue.py — data loading and configuration."""
from __future__ import annotations

import json
import os
import tempfile
import unittest

from podcast_catalogue.catalogue import CatalogueBuilder, CatalogueConfig


class TestLoadExistingData(unittest.TestCase):
    """Test incremental data loading from JSONL files."""

    def test_loads_valid_jsonl(self):
        builder = CatalogueBuilder()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False, encoding='utf-8') as f:
            f.write(json.dumps({"title": "Show A", "description": "Desc A"}) + "\n")
            f.write(json.dumps({"title": "Show B", "description": "Desc B"}) + "\n")
            tmp_path = f.name

        try:
            result = builder._load_existing_data(tmp_path)
            self.assertEqual(len(result), 2)
            self.assertIn("Show A", result)
            self.assertIn("Show B", result)
        finally:
            os.remove(tmp_path)

    def test_handles_empty_file(self):
        builder = CatalogueBuilder()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            tmp_path = f.name

        try:
            result = builder._load_existing_data(tmp_path)
            self.assertEqual(len(result), 0)
        finally:
            os.remove(tmp_path)

    def test_handles_missing_file(self):
        builder = CatalogueBuilder()
        result = builder._load_existing_data("/tmp/nonexistent_file.jsonl")
        self.assertEqual(len(result), 0)

    def test_handles_none_path(self):
        builder = CatalogueBuilder()
        result = builder._load_existing_data(None)
        self.assertEqual(len(result), 0)

    def test_skips_malformed_lines(self):
        builder = CatalogueBuilder()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False, encoding='utf-8') as f:
            f.write(json.dumps({"title": "Good Show"}) + "\n")
            f.write("this is not json\n")
            f.write(json.dumps({"title": "Another Good Show"}) + "\n")
            tmp_path = f.name

        try:
            result = builder._load_existing_data(tmp_path)
            self.assertEqual(len(result), 2)
        finally:
            os.remove(tmp_path)


class TestCatalogueConfig(unittest.TestCase):
    """Test config defaults and duration_limit field."""

    def test_default_values(self):
        config = CatalogueConfig(sitemap_url="https://example.com/sitemap.xml")
        self.assertEqual(config.limit, 0)
        self.assertFalse(config.transcribe)
        self.assertFalse(config.ai_enrich)
        self.assertEqual(config.duration_limit, 0)

    def test_duration_limit_set(self):
        config = CatalogueConfig(sitemap_url="https://example.com", duration_limit=120)
        self.assertEqual(config.duration_limit, 120)


if __name__ == "__main__":
    unittest.main()
