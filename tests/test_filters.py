"""Tests for filter utilities — pure functions only."""

from inbox_cleaner.utils import filter_exists_for_sender


class TestFilterExists:
    def test_exact_match(self):
        filters = [
            {"criteria": {"from": "test@example.com"}, "action": {}},
        ]
        assert filter_exists_for_sender(filters, "test@example.com") is True

    def test_case_insensitive(self):
        filters = [
            {"criteria": {"from": "Test@Example.com"}, "action": {}},
        ]
        assert filter_exists_for_sender(filters, "test@example.com") is True

    def test_no_match(self):
        filters = [
            {"criteria": {"from": "other@example.com"}, "action": {}},
        ]
        assert filter_exists_for_sender(filters, "test@example.com") is False

    def test_empty_filters(self):
        assert filter_exists_for_sender([], "test@example.com") is False

    def test_filter_without_from(self):
        filters = [
            {"criteria": {"subject": "test"}, "action": {}},
        ]
        assert filter_exists_for_sender(filters, "test@example.com") is False
