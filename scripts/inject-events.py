#!/usr/bin/env python3
"""inject-events.py — Inject sample CloudTrail events into EventBridge for testing.

Usage:
    python scripts/inject-events.py --env dev [--file path/to/event.json]
    python scripts/inject-events.py --env dev [--dir sample-data/cloud-trail-events]
    python scripts/inject-events.py --env dev --dir sample-data/cloud-trail-events --dry-run

Only supports the dev environment in Phase 2.
"""

import argparse
import json
import sys
import time
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SUPPORTED_ENVS = {"dev"}
EVENT_BUS_NAME = "default"
EVENT_SOURCE = "radius.test"
EVENT_DETAIL_TYPE = "CloudTrail via Radius Test Injector"

REQUIRED_FIELDS = {"eventName", "userIdentity", "eventTime"}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_event(event: dict, path: str) -> list[str]:
    """Return a list of validation errors for a CloudTrail event dict."""
    errors = []
    missing = REQUIRED_FIELDS - set(event.keys())
    if missing:
        errors.append(f"{path}: missing required fields: {sorted(missing)}")
    user_identity = event.get("userIdentity", {})
    if not isinstance(user_identity, dict) or not user_identity.get("type"):
        errors.append(f"{path}: userIdentity.type is missing")
    return errors


def load_event_file(path: Path) -> dict | None:
    """Load and parse a JSON event file. Returns None on error."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        print(f"  ERROR: {path} is not valid JSON — {exc}", file=sys.stderr)
        return None
    except OSError as exc:
        print(f"  ERROR: Cannot read {path} — {exc}", file=sys.stderr)
        return None


def collect_event_files(source: Path) -> list[Path]:
    """Return a sorted list of .json files from a file or directory."""
    if source.is_file():
        return [source]
    if source.is_dir():
        return sorted(source.glob("*.json"))
    print(f"ERROR: {source} is not a file or directory", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Injection
# ---------------------------------------------------------------------------

def inject_events(
    events: list[tuple[Path, dict]],
    region: str,
    dry_run: bool,
) -> tuple[int, int]:
    """Send events to EventBridge. Returns (success_count, failure_count)."""
    if dry_run:
        print(f"\n[DRY RUN] Would inject {len(events)} event(s) — no AWS calls made.")
        for path, event in events:
            print(f"  {path.name}: {event.get('eventName')} / {event.get('eventTime')}")
        return len(events), 0

    client = boto3.client("events", region_name=region)
    success = 0
    failure = 0

    # EventBridge PutEvents accepts up to 10 entries per call
    BATCH_SIZE = 10
    for i in range(0, len(events), BATCH_SIZE):
        batch = events[i : i + BATCH_SIZE]
        entries = [
            {
                "Source": EVENT_SOURCE,
                "DetailType": EVENT_DETAIL_TYPE,
                "Detail": json.dumps(event),
                "EventBusName": EVENT_BUS_NAME,
            }
            for _, event in batch
        ]

        try:
            response = client.put_events(Entries=entries)
        except ClientError as exc:
            print(f"  ERROR: PutEvents API call failed — {exc}", file=sys.stderr)
            failure += len(batch)
            continue

        for j, result in enumerate(response.get("Entries", [])):
            path = batch[j][0]
            if result.get("EventId"):
                print(f"  OK  {path.name} → EventId={result['EventId']}")
                success += 1
            else:
                print(
                    f"  ERR {path.name} → {result.get('ErrorCode')}: {result.get('ErrorMessage')}",
                    file=sys.stderr,
                )
                failure += 1

        # Brief pause between batches to avoid throttling
        if i + BATCH_SIZE < len(events):
            time.sleep(0.1)

    return success, failure


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Inject sample CloudTrail events into EventBridge")
    parser.add_argument("--env", required=True, choices=list(SUPPORTED_ENVS),
                        help="Target environment (only 'dev' supported in Phase 2)")
    parser.add_argument("--file", help="Path to a single event JSON file")
    parser.add_argument("--dir", help="Path to a directory of event JSON files")
    parser.add_argument("--region", default="us-east-1", help="AWS region (default: us-east-1)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Validate and list events without sending to AWS")
    args = parser.parse_args()

    if not args.file and not args.dir:
        parser.error("Provide --file or --dir")

    source = Path(args.file or args.dir)
    event_files = collect_event_files(source)

    if not event_files:
        print("No .json files found.", file=sys.stderr)
        sys.exit(1)

    print(f"==> Injecting events [env={args.env}, region={args.region}, files={len(event_files)}]")

    # Load and validate
    valid_events: list[tuple[Path, dict]] = []
    validation_errors: list[str] = []

    for path in event_files:
        event = load_event_file(path)
        if event is None:
            validation_errors.append(f"{path}: failed to parse JSON")
            continue
        errors = validate_event(event, str(path))
        if errors:
            validation_errors.extend(errors)
        else:
            valid_events.append((path, event))

    if validation_errors:
        print(f"\nValidation errors ({len(validation_errors)}):", file=sys.stderr)
        for err in validation_errors:
            print(f"  {err}", file=sys.stderr)

    if not valid_events:
        print("No valid events to inject.", file=sys.stderr)
        sys.exit(1)

    print(f"  Valid: {len(valid_events)}, Invalid: {len(validation_errors)}")

    # Inject
    success, failure = inject_events(valid_events, args.region, args.dry_run)

    print(f"\n==> Done: {success} succeeded, {failure} failed")
    if failure > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
