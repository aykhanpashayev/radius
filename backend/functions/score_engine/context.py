"""ScoringContext: fetches and holds all data needed to score one IAM identity."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from boto3.dynamodb.conditions import Key

from backend.common.dynamodb_utils import get_dynamodb_client, get_item
from backend.common.logging_utils import get_logger

logger = get_logger(__name__)

_MAX_EVENTS = 1_000


@dataclass
class ScoringContext:
    """All data required to evaluate scoring rules for one IAM identity."""

    identity_arn: str
    identity_profile: dict = field(default_factory=dict)
    events: list[dict] = field(default_factory=list)
    trust_relationships: list[dict] = field(default_factory=list)
    open_incidents: list[dict] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def build(cls, identity_arn: str, tables: dict[str, str]) -> "ScoringContext":
        """Fetch all scoring data from DynamoDB and return a ScoringContext.

        Args:
            identity_arn: The IAM identity ARN to score.
            tables: Mapping of logical table keys to DynamoDB table names.
                Expected keys: "identity_profile", "event_summary",
                "trust_relationship", "incident".

        Returns:
            A populated ScoringContext (partial data on fetch errors).
        """
        identity_profile = cls._fetch_identity_profile(identity_arn, tables)
        events = cls._fetch_events(identity_arn, tables)
        trust_relationships = cls._fetch_trust_relationships(identity_arn, tables)
        open_incidents = cls._fetch_open_incidents(identity_arn, tables)

        return cls(
            identity_arn=identity_arn,
            identity_profile=identity_profile,
            events=events,
            trust_relationships=trust_relationships,
            open_incidents=open_incidents,
        )

    # ------------------------------------------------------------------
    # Private fetch helpers
    # ------------------------------------------------------------------

    @classmethod
    def _fetch_identity_profile(cls, identity_arn: str, tables: dict[str, str]) -> dict:
        try:
            result = get_item(tables["identity_profile"], {"identity_arn": identity_arn})
            return result if result is not None else {}
        except Exception as exc:
            logger.warning(
                "Failed to fetch Identity_Profile",
                extra={"identity_arn": identity_arn, "error": str(exc)},
            )
            return {}

    @classmethod
    def _fetch_events(cls, identity_arn: str, tables: dict[str, str]) -> list[dict]:
        try:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
            dynamodb = get_dynamodb_client()
            table = dynamodb.Table(tables["event_summary"])

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
                items = response.get("Items", [])
                collected.extend(items)

                if len(collected) >= _MAX_EVENTS:
                    collected = collected[:_MAX_EVENTS]
                    break

                last_key = response.get("LastEvaluatedKey")
                if not last_key:
                    break

            return collected
        except Exception as exc:
            logger.warning(
                "Failed to fetch Event_Summary",
                extra={"identity_arn": identity_arn, "error": str(exc)},
            )
            return []

    @classmethod
    def _fetch_trust_relationships(cls, identity_arn: str, tables: dict[str, str]) -> list[dict]:
        try:
            dynamodb = get_dynamodb_client()
            table = dynamodb.Table(tables["trust_relationship"])

            collected: list[dict] = []
            last_key: dict | None = None

            while True:
                kwargs: dict[str, Any] = {
                    "KeyConditionExpression": Key("source_arn").eq(identity_arn),
                }
                if last_key:
                    kwargs["ExclusiveStartKey"] = last_key

                response = table.query(**kwargs)
                collected.extend(response.get("Items", []))

                last_key = response.get("LastEvaluatedKey")
                if not last_key:
                    break

            return collected
        except Exception as exc:
            logger.warning(
                "Failed to fetch Trust_Relationship",
                extra={"identity_arn": identity_arn, "error": str(exc)},
            )
            return []

    @classmethod
    def _fetch_open_incidents(cls, identity_arn: str, tables: dict[str, str]) -> list[dict]:
        try:
            dynamodb = get_dynamodb_client()
            table = dynamodb.Table(tables["incident"])

            # Step 1: query IdentityIndex GSI (KEYS_ONLY) to get incident IDs
            keys: list[dict] = []
            last_key: dict | None = None

            while True:
                kwargs: dict[str, Any] = {
                    "IndexName": "IdentityIndex",
                    "KeyConditionExpression": Key("identity_arn").eq(identity_arn),
                }
                if last_key:
                    kwargs["ExclusiveStartKey"] = last_key

                response = table.query(**kwargs)
                keys.extend(response.get("Items", []))

                last_key = response.get("LastEvaluatedKey")
                if not last_key:
                    break

            # Step 2: fetch full records and filter by status
            open_statuses = {"open", "investigating"}
            open_incidents: list[dict] = []

            for key_item in keys:
                incident_id = key_item.get("incident_id")
                if not incident_id:
                    continue
                record = get_item(tables["incident"], {"incident_id": incident_id})
                if record and record.get("status") in open_statuses:
                    open_incidents.append(record)

            return open_incidents
        except Exception as exc:
            logger.warning(
                "Failed to fetch open Incidents",
                extra={"identity_arn": identity_arn, "error": str(exc)},
            )
            return []
