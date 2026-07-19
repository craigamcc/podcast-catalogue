"""Tests for ai_enricher.py — JSON extraction and LLM prompt handling."""
from __future__ import annotations

import unittest
from podcast_catalogue.ai_enricher import extract_json_from_text as extract_json


class TestExtractJson(unittest.TestCase):
    """Test the robust JSON extractor."""

    def test_plain_json(self):
        raw = '{"key": "value", "num": 42}'
        result = extract_json(raw)
        self.assertEqual(result, {"key": "value", "num": 42})

    def test_json_with_markdown_fence(self):
        raw = '```json\n{"key": "value"}\n```'
        result = extract_json(raw)
        self.assertEqual(result, {"key": "value"})

    def test_json_embedded_in_text(self):
        raw = 'Here is some text. {"key": "value"} And more text.'
        result = extract_json(raw)
        self.assertEqual(result, {"key": "value"})

    def test_nested_json(self):
        raw = '{"outer": {"inner": [1, 2, 3]}}'
        result = extract_json(raw)
        self.assertEqual(result["outer"]["inner"], [1, 2, 3])

    def test_empty_string_returns_none(self):
        self.assertIsNone(extract_json(""))

    def test_none_input_returns_none(self):
        self.assertIsNone(extract_json(None))

    def test_garbage_returns_none(self):
        self.assertIsNone(extract_json("This is not JSON at all."))

    def test_json_with_leading_whitespace(self):
        raw = '  \n\n  {"key": "value"}  \n  '
        result = extract_json(raw)
        self.assertEqual(result, {"key": "value"})

    def test_json_with_trailing_comma_fails_gracefully(self):
        # Standard JSON does not allow trailing commas
        raw = '{"key": "value",}'
        result = extract_json(raw)
        # Depending on implementation, this may or may not parse
        # The important thing is it doesn't crash
        self.assertTrue(result is None or isinstance(result, dict))


if __name__ == "__main__":
    unittest.main()
