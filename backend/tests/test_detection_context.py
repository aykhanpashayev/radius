"""Unit tests for DetectionContext.build()."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from backend.functions.detection_engine.context import DetectionContext

_IDENTITY = "arn:aws:iam::123456789012:user/alice"
_EVENT_TABLE = "Event_Summary"
_NOW = datetime(2026, 3, 16, 12, 0, 0, tzinfo=timezone.utc)
_NOW_ISO = _NOW.isoformat()


def _ts(delta: timedelta) -> str:
    return (_NOW + delta).isoformat()


def _make_event(event_id: str, event_type: str, ts: str) -> dict:
    return {"event_id": event_id, "event_type": event_type, "timestamp": ts, "identity_arn": _IDENTITY}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_table(responses: list[dict]):
    """Return a mock DynamoDB Table whose query() cycles through responses."""
    table = MagicMock()
    table.query.side_effect = responses
    return table


def _mock_dynamodb(table):
    db = MagicMock()
    db.Table.return_value = table
    return db


# ---------------------------------------------------------------------------
# recent_events_60m
# ---------------------------------------------------------------------------

class TestRecentEvents60m:
    def test_returns_events_within_60_minutes(self):
        event_in = _make_event("e1", "iam:CreateUser", _ts(timedelta(minutes=-30)))
        event_out = _make_event("e2", "iam:DeleteUser", _ts(timedelta(hours=-2)))

        table = _mock_table([
            {"Items": [event_in], "LastEvaluatedKey": None},
        ])

        with patch("backend.functions.detection_engine.context.get_dynamodb_client") as mock_db, \
             patch("backend.functions.detection_engine.context.datetime") as mock_dt:
            mock_dt.now.return_value = _NOW
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            mock_db.return_value = _mock_dynamodb(table)

            ctx = DetectionContext._fetch_recent_events(_IDENTITY, _EVENT_TABLE, minutes=60)

        assert event_in in ctx
        assert event_out not in ctx

    def test_empty_on_dynamodb_exception(self):
        table = MagicMock()
        table.query.side_effect = Exception("DynamoDB unavailable")

        with patch("backend.functions.detection_engine.context.get_dynamodb_client") as mock_db:
            mock_db.return_value = _mock_dynamodb(table)
            result = DetectionContext._fetch_recent_events(_IDENTITY, _EVENT_TABLE, minutes=60)

        assert result == []

    def test_paginates_until_no_last_key(self):
        e1 = _make_event("e1", "iam:CreateUser", _ts(timedelta(minutes=-10)))
        e2 = _make_event("e2", "iam:DeleteUser", _ts(timedelta(minutes=-20)))

        table = _mock_table([
            {"Items": [e1], "LastEvaluatedKey": {"identity_arn": _IDENTITY, "timestamp": e1["timestamp"]}},
            {"Items": [e2], "LastEvaluatedKey": None},
        ])

        with patch("backend.functions.detection_engine.context.get_dynamodb_client") as mock_db:
            mock_db.return_value = _mock_dynamodb(table)
            result = DetectionContext._fetch_recent_events(_IDENTITY, _EVENT_TABLE, minutes=60)

        assert len(result) == 2


# ---------------------------------------------------------------------------
# recent_events_5m (derived property)
# ---------------------------------------------------------------------------

class TestRecentEvents5m:
    def test_filters_to_5_minute_window(self):
        now = datetime.now(timezone.utc)
        e_recent = _make_event("e1", "iam:CreateUser", (now - timedelta(minutes=2)).isoformat())
        e_old = _make_event("e2", "iam:DeleteUser", (now - timedelta(minutes=10)).isoformat())

        ctx = DetectionContext(
            identity_arn=_IDENTITY,
            recent_events_60m=[e_recent, e_old],
        )

        result = ctx.recent_events_5m
        assert e_recent in result
        assert e_old not in result

    def test_empty_when_no_recent_events(self):
        ctx = DetectionContext(identity_arn=_IDENTITY, recent_events_60m=[])
        assert ctx.recent_events_5m == []


# ---------------------------------------------------------------------------
# prior_services_30d
# ---------------------------------------------------------------------------

class TestPriorServices30d:
    def test_extracts_service_prefixes(self):
        current_ts = _NOW_ISO
        older_ts = _ts(timedelta(days=-5))

        events = [
            _make_event("e1", "iam:CreateUser", older_ts),
            _make_event("e2", "sts:AssumeRole", older_ts),
            _make_event("e3", "kms:Decrypt", older_ts),
        ]

        table = _mock_table([{"Items": events, "LastEvaluatedKey": None}])

        with patch("backend.functions.detection_engine.context.get_dynamodb_client") as mock_db:
            mock_db.return_value = _mock_dynamodb(table)
            services = DetectionContext._fetch_prior_services(
                _IDENTITY, "current-event-id", current_ts, _EVENT_TABLE
            )

        assert "iam" in services
        assert "sts" in services
        assert "kms" in services

    def test_excludes_current_event_by_id(self):
        current_ts = _NOW_ISO
        older_ts = _ts(timedelta(days=-1))

        events = [
            _make_event("current-id", "iam:CreateUser", older_ts),
            _make_event("other-id", "sts:AssumeRole", older_ts),
        ]

        table = _mock_table([{"Items": events, "LastEvaluatedKey": None}])

        with patch("backend.functions.detection_engine.context.get_dynamodb_client") as mock_db:
            mock_db.return_value = _mock_dynamodb(table)
            services = DetectionContext._fetch_prior_services(
                _IDENTITY, "current-id", current_ts, _EVENT_TABLE
            )

        # "iam" excluded because event_id == current-id
        assert "iam" not in services
        assert "sts" in services

    def test_empty_on_dynamodb_exception(self):
        table = MagicMock()
        table.query.side_effect = Exception("timeout")

        with patch("backend.functions.detection_engine.context.get_dynamodb_client") as mock_db:
            mock_db.return_value = _mock_dynamodb(table)
            result = DetectionContext._fetch_prior_services(
                _IDENTITY, "eid", _NOW_ISO, _EVENT_TABLE
            )

        assert result == set()

    def test_ignores_events_without_colon_in_event_type(self):
        older_ts = _ts(timedelta(days=-1))
        events = [_make_event("e1", "UnknownEvent", older_ts)]

        table = _mock_table([{"Items": events, "LastEvaluatedKey": None}])

        with patch("backend.functions.detection_engine.context.get_dynamodb_client") as mock_db:
            mock_db.return_value = _mock_dynamodb(table)
            services = DetectionContext._fetch_prior_services(
                _IDENTITY, "other-id", _NOW_ISO, _EVENT_TABLE
            )

        assert services == set()


# ---------------------------------------------------------------------------
# build() integration
# ---------------------------------------------------------------------------

class TestBuild:
    def test_build_returns_populated_context(self):
        now = datetime.now(timezone.utc)
        recent_ts = (now - timedelta(minutes=30)).isoformat()
        old_ts = (now - timedelta(days=10)).isoformat()
        current_ts = now.isoformat()

        recent_event = _make_event("e1", "iam:CreateUser", recent_ts)
        old_event = _make_event("e2", "sts:AssumeRole", old_ts)

        # Two separate tables are queried — mock returns different data per call
        call_count = 0

        def query_side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"Items": [recent_event], "LastEvaluatedKey": None}
            return {"Items": [old_event], "LastEvaluatedKey": None}

        table = MagicMock()
        table.query.side_effect = query_side_effect

        with patch("backend.functions.detection_engine.context.get_dynamodb_client") as mock_db:
            mock_db.return_value = _mock_dynamodb(table)
            ctx = DetectionContext.build(_IDENTITY, "current-id", current_ts, _EVENT_TABLE)

        assert ctx.identity_arn == _IDENTITY
        assert isinstance(ctx.recent_events_60m, list)
        assert isinstance(ctx.prior_services_30d, set)
