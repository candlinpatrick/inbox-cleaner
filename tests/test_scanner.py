"""Tests for scanner/utils — pure functions only (no API calls)."""

from inbox_cleaner.utils import (
    parse_from_header,
    parse_unsubscribe_header,
    estimate_frequency,
    get_category,
)


class TestParseFromHeader:
    def test_name_and_email(self):
        name, email = parse_from_header("Foo Bar <foo@bar.com>")
        assert name == "Foo Bar"
        assert email == "foo@bar.com"

    def test_quoted_name(self):
        name, email = parse_from_header('"Foo Bar" <foo@bar.com>')
        assert name == "Foo Bar"
        assert email == "foo@bar.com"

    def test_bare_email(self):
        name, email = parse_from_header("foo@bar.com")
        assert name == ""
        assert email == "foo@bar.com"

    def test_email_case_normalized(self):
        _, email = parse_from_header("Test <FOO@BAR.COM>")
        assert email == "foo@bar.com"

    def test_whitespace_handling(self):
        name, email = parse_from_header("  Foo  <foo@bar.com>")
        assert name == "Foo"
        assert email == "foo@bar.com"


class TestParseUnsubscribeHeader:
    def test_single_https(self):
        links = parse_unsubscribe_header("<https://example.com/unsub>")
        assert links == ["https://example.com/unsub"]

    def test_multiple_links(self):
        links = parse_unsubscribe_header(
            "<https://example.com/unsub>, <mailto:unsub@example.com>"
        )
        assert links == ["https://example.com/unsub", "mailto:unsub@example.com"]

    def test_empty(self):
        links = parse_unsubscribe_header("")
        assert links == []

    def test_whitespace(self):
        links = parse_unsubscribe_header("  <https://example.com/unsub>  ")
        assert links == ["https://example.com/unsub"]


class TestEstimateFrequency:
    def test_daily_plus(self):
        assert estimate_frequency(50, 30) == "daily+"

    def test_daily(self):
        assert estimate_frequency(30, 30) == "daily"

    def test_few_per_week(self):
        assert estimate_frequency(12, 30) == "2-3/week"

    def test_weekly(self):
        assert estimate_frequency(4, 30) == "weekly"

    def test_monthly(self):
        assert estimate_frequency(1, 30) == "monthly"

    def test_zero_days(self):
        assert estimate_frequency(5, 0) == "unknown"


class TestGetCategory:
    def test_promotions(self):
        assert get_category(["INBOX", "CATEGORY_PROMOTIONS"]) == "PROMOTIONS"

    def test_no_category(self):
        assert get_category(["INBOX", "UNREAD"]) is None

    def test_first_category_wins(self):
        result = get_category(["CATEGORY_SOCIAL", "CATEGORY_UPDATES"])
        assert result == "SOCIAL"
