"""DetectionContext: fetches and holds historical data needed to evaluate detection rules."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from boto3.dynamodb.conditions import Key

from backend.common.dynamodb_utils import get_dynamodb_client
from backend.common.logging_utils import get_logger

logger = get_logger(__name__)

_MAX_EVENTS = 1_000


@dataclass
class DetectionContext:
    """Pre-fetched historical data for context-aware detection rules."""

    identity_arn: str
    recent_events_60m: list[dict] = field(default_factory=list)
    prior_services_30d: set[str] = field(default_factory=set)

    @property
    def recent_events_5m(self) -> list[dict]:
        """Events in last 5 minutes — derived in-memory from recent_events_60m."""
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        return [e for e in self.recent_events_60m if e.get("timestamp", "") >= cutoff]

    @classmethod
    def build(
        cls,
        identity_arn: str,
        current_event_id: str,
        current_event_timestamp: str,
        event_summary_table: str,
    ) -> "DetectionContext":
        """Fetch detection context from DynamoDB.

        Performs exactly two DynamoDB queries:
        1. Events in last 60 minutes (for IAMPolicyModificationSpike, APIBurstAnomaly,
           PrivilegeEscalation).
        2. Events in last 30 days strictly before current_event_timestamp (for
           UnusualServiceUsage prior_services_30d).

        Args:
            identity_arn: The IAM identity ARN being evaluated.
            current_event_id: The event_id of the triggering event (excluded from 30d query).
            current_event_timestamp: ISO timestamp of the current event.
            event_summary_table: DynamoDB table name for Event_Summary.

        Returns:
            Populated DetectionContext (empty collections on fetch errors).
        """
        recent_events_60m = cls._fetch_recent_events(
            identity_arn, event_summary_table, minutes=60
        )
        prior_services_30d = cls._fetch_prior_services(
            identity_arn, current_event_id, current_event_timestamp, event_summary_table
        )
        return cls(
            identity_arn=identity_arn,
            recent_events_60m=recent_events_60m,
            prior_services_30d=prior_services_30d,
        )

    @classmethod
    def _fetch_recent_events(
        cls, identity_arn: str, table_name: str, minutes: int
    ) -> list[dict]:
        try:
            cutoff = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
            dynamodb = get_dynamodb_client()
            table = dynamodb.Table(table_name)

            collected: list[dict] = []
            last_key: dict | None = None

            while True:
                kwargs: dict[str, Any] = {
                    "KeyConditionExpression": (
                        Key("identity_arn").eq(identity_arn)
                        & Key("timestamp").gte(cutoff)
                    ),
                }
                if last_key:
                    kwargs["ExclusiveStartKey"] = last_key

                response = table.query(**kwargs)
                collected.extend(response.get("Items", []))

                if len(collected) >= _MAX_EVENTS:
                    collected = collected[:_MAX_EVENTS]
                    break

                last_key = response.get("LastEvaluatedKey")
                if not last_key:
                    break

            return collected
        except Exception as exc:
            logger.warning(
                "Failed to fetch recent events",
                extra={"identity_arn": identity_arn, "minutes": minutes, "error": str(exc)},
            )
            return []

    @classmethod
    def _fetch_prior_services(
        cls,
        identity_arn: str,
        current_event_id: str,
        current_event_timestamp: str,
        table_name: str,
    ) -> set[str]:
        """Fetch distinct services used in the 30 days strictly before current event."""
        try:
            cutoff_30d = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
            dynamodb = get_dynamodb_client()
            table = dynamodb.Table(table_name)

            services: set[str] = set()
            last_key: dict | None = None

            while True:
                kwargs: dict[str, Any] = {
                    "KeyConditionExpression": (
                        Key("identity_arn").eq(identity_arn)
                        & Key("timestamp").between(cutoff_30d, current_event_timestamp)
                    ),
                }
                if last_key:
                    kwargs["ExclusiveStartKey"] = last_key

                response = table.query(**kwargs)
                for item in response.get("Items", []):
                    # Exclude the current event by event_id and exact timestamp boundary
                    if item.get("event_id") == current_event_id:
                        continue
                    if item.get("timestamp", "") >= current_event_timestamp:
                        continue
                    event_type = item.get("event_type", "")
                    if ":" in event_type:
                        services.add(event_type.split(":")[0].lower())

                last_key = response.get("LastEvaluatedKey")
                if not last_key:
                    break

            return services
        except Exception as exc:
            logger.warning(
                "Failed to fetch prior services",
                extra={"identity_arn": identity_arn, "error": str(exc)},
            )
            return set()
