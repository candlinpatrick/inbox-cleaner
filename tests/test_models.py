"""Tests for data models."""

import json
from datetime import datetime, timezone

from inbox_cleaner.models import (
    Decision,
    Sender,
    SenderDecision,
    ScanResult,
    ApplyResult,
)


class TestDecision:
    def test_enum_values(self):
        assert Decision.KEEP == "keep"
        assert Decision.FILTER_DELETE == "filter_delete"
        assert Decision.UNSUBSCRIBE == "unsubscribe"
        assert Decision.SKIP == "skip"


class TestSender:
    def test_basic_sender(self):
        s = Sender(
            email="test@example.com",
            display_name="Test",
            message_count=5,
            frequency_estimate="weekly",
            has_unsubscribe_header=True,
            first_seen=datetime(2024, 1, 1, tzinfo=timezone.utc),
            last_seen=datetime(2024, 1, 31, tzinfo=timezone.utc),
        )
        assert s.email == "test@example.com"
        assert s.category is None
        assert s.unsubscribe_links == []
        assert s.sample_subjects == []
        assert s.message_ids == []

    def test_sender_serialization_roundtrip(self):
        s = Sender(
            email="test@example.com",
            display_name="Test Sender",
            message_count=10,
            frequency_estimate="daily",
            category="PROMOTIONS",
            has_unsubscribe_header=True,
            unsubscribe_links=["https://example.com/unsub"],
            sample_subjects=["Hello", "World"],
            first_seen=datetime(2024, 1, 1, tzinfo=timezone.utc),
            last_seen=datetime(2024, 1, 31, tzinfo=timezone.utc),
        )
        data = json.loads(s.model_dump_json())
        s2 = Sender.model_validate(data)
        assert s2.email == s.email
        assert s2.message_count == s.message_count
        assert s2.unsubscribe_links == s.unsubscribe_links


class TestScanResult:
    def test_scan_result_serialization(self):
        result = ScanResult(
            account="test",
            scanned_at=datetime(2024, 1, 15, tzinfo=timezone.utc),
            days_scanned=30,
            total_messages=100,
            senders=[
                Sender(
                    email="a@b.com",
                    display_name="A",
                    message_count=50,
                    frequency_estimate="daily",
                    has_unsubscribe_header=True,
                    first_seen=datetime(2024, 1, 1, tzinfo=timezone.utc),
                    last_seen=datetime(2024, 1, 15, tzinfo=timezone.utc),
                )
            ],
        )
        json_str = result.model_dump_json()
        result2 = ScanResult.model_validate_json(json_str)
        assert result2.account == "test"
        assert len(result2.senders) == 1
        assert result2.senders[0].email == "a@b.com"


class TestApplyResult:
    def test_defaults(self):
        r = ApplyResult()
        assert r.filters_created == 0
        assert r.messages_deleted == 0
        assert r.errors == []
