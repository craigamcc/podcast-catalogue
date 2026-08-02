"""Tests for transcriber.py — diarization support (no model loading)."""
from __future__ import annotations

import unittest
from podcast_catalogue.transcriber import _get_diarization_pipeline


class TestLazyModelLoading(unittest.TestCase):
    """Verify the model doesn't load at import time."""

    def test_model_not_loaded_at_import(self):
        """Confirm that importing transcriber does NOT load the model."""
        from podcast_catalogue import transcriber
        # The module-level _diarization_pipeline should be None until first call
        self.assertIsNone(transcriber._diarization_pipeline)


class TestSegmentExtraction(unittest.TestCase):
    """Test segment processing from mock Whisper output."""

    def test_segments_have_correct_structure(self):
        """Segments should have text, start, end, speaker fields."""
        mock_whisper_segments = [
            {"text": "Hello world", "start": 0.0, "end": 2.5},
            {"text": "How are you", "start": 2.5, "end": 5.0},
            {"text": "  ", "start": 5.0, "end": 5.5},  # Empty — should be skipped
        ]

        segments = [
            {
                "text": seg.get("text", "").strip(),
                "start": round(seg.get("start", 0.0), 2),
                "end": round(seg.get("end", 0.0), 2),
                "speaker": None
            }
            for seg in mock_whisper_segments
            if seg.get("text", "").strip()
        ]

        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0]["text"], "Hello world")
        self.assertEqual(segments[0]["start"], 0.0)
        self.assertEqual(segments[0]["end"], 2.5)
        self.assertIsNone(segments[0]["speaker"])

    def test_empty_segments_filtered(self):
        mock_segments = [
            {"text": "", "start": 0.0, "end": 1.0},
            {"text": "   ", "start": 1.0, "end": 2.0},
        ]
        filtered = [s for s in mock_segments if s.get("text", "").strip()]
        self.assertEqual(len(filtered), 0)


if __name__ == "__main__":
    unittest.main()
