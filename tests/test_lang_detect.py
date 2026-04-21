"""Tests for core/lang_detect.py."""

from core.lang_detect import detect_lang


def test_english():
    assert detect_lang("fix the button") == "en"


def test_ukrainian():
    assert detect_lang("виправ кнопку") == "uk"


def test_mixed_counts_as_ukrainian():
    assert detect_lang("fix кнопку please") == "uk"


def test_empty():
    assert detect_lang("") == "en"


def test_numbers_and_punctuation():
    assert detect_lang("123 !!! .com") == "en"
