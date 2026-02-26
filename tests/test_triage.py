"""Tests for triage module — pure functions only."""

from datetime import datetime, timezone

from inbox_cleaner.models import Decision, Sender
from inbox_cleaner.triage import _auto_recommend


def _make_sender(**kwargs) -> Sender:
    """Helper to create a Sender with defaults."""
    defaults = {
        "email": "test@example.com",
        "display_name": "Test",
        "message_count": 5,
        "frequency_estimate": "weekly",
        "category": None,
        "has_unsubscribe_header": False,
        "first_seen": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "last_seen": datetime(2024, 1, 31, tzinfo=timezone.utc),
    }
    defaults.update(kwargs)
    return Sender(**defaults)


class TestAutoRecommend:
    def test_daily_promo_with_unsub_header(self):
        s = _make_sender(
            category="PROMOTIONS",
            frequency_estimate="daily",
            has_unsubscribe_header=True,
        )
        assert _auto_recommend(s) == Decision.UNSUBSCRIBE

    def test_daily_promo_without_unsub_header(self):
        s = _make_sender(
            category="PROMOTIONS",
            frequency_estimate="daily",
            has_unsubscribe_header=False,
        )
        assert _auto_recommend(s) == Decision.FILTER_DELETE

    def test_daily_plus_promo(self):
        s = _make_sender(
            category="PROMOTIONS",
            frequency_estimate="daily+",
            has_unsubscribe_header=True,
        )
        assert _auto_recommend(s) == Decision.UNSUBSCRIBE

    def test_high_count_promo(self):
        s = _make_sender(
            category="PROMOTIONS",
            message_count=15,
            frequency_estimate="2-3/week",
        )
        assert _auto_recommend(s) == Decision.FILTER_DELETE

    def test_daily_social(self):
        s = _make_sender(
            category="SOCIAL",
            frequency_estimate="daily",
        )
        assert _auto_recommend(s) == Decision.FILTER_DELETE

    def test_low_frequency_returns_none(self):
        s = _make_sender(
            category="UPDATES",
            frequency_estimate="weekly",
            message_count=3,
        )
        assert _auto_recommend(s) is None

    def test_no_category_returns_none(self):
        s = _make_sender(frequency_estimate="weekly", message_count=3)
        assert _auto_recommend(s) is None
