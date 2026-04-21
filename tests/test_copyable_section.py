"""Tests for CopyableSection text extraction."""
from gui.copyable_widgets import extract_text_from_labels


def test_extract_text_from_labels():
    texts = ["Line 1", "Line 2", "Line 3"]
    result = extract_text_from_labels(texts)
    assert result == "Line 1\nLine 2\nLine 3"


def test_extract_empty():
    assert extract_text_from_labels([]) == ""
