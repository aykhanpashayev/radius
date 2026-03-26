# Radius — Demo Guide

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Attack Scenario](#attack-scenario)
- [Running the Demo](#running-the-demo)
- [What to Narrate](#what-to-narrate)
- [Expected Output](#expected-output)
- [Cleanup](#cleanup)

---

## Overview

This guide walks through a live demonstration of Radius using a simulated privilege escalation attack. The demo exercises every major component of the platform in sequence: identity seeding, event injection, detection, scoring, and remediation audit — all running locally with no AWS credentials required.

The scenario follows a compromised IAM user (`attacker`) who executes a four-step privilege escalation sequence: creating a new IAM user, attaching an admin policy, creating a wildcard policy version, and then calling `StopLogging` to cover their tracks. Radius detects the attack pattern, raises a Critical-severity incident, scores the identity above 80, and records remediation evaluation in the audit log.

This demo matters because it shows the full end-to-end pipeline in under 60 seconds. It demonstrates that Radius is not just a detection tool — it is a complete identity risk platform with explainable scoring and auditable remediation decisions. Every output is traceable to a named rule and a specific CloudTrail event.

---

## Prerequisites

- Python 3.11 or later
- Install dependencies:

```bash
pip install -r backend/requirements-dev.txt
```

- No AWS credentials are needed in mock mode. The script uses [moto](https://github.com/getmoto/moto) to mock all AWS services in-process. You can run the demo with `AWS_ACCESS_KEY_ID` unset or set to any value — the output will be identical.

---

## Attack Scenario

A threat actor has compromised an IAM user in account `123456789012`. Over a 15-minute window, they execute a four-step privilege escalation sequence designed to create a persistent backdoor and then disable logging to avoid detection.

### Step-by-Step Narrative

1. **CreateUser** — The attacker creates a new IAM user (`backdoor-user`) to establish a persistent foothold that survives credential rotation on the original account.

2. **AttachUserPolicy** — The attacker attaches the `AdministratorAccess` managed policy to the new user. Combined with the preceding `CreateUser` event in the same 60-minute window, this triggers the `PrivilegeEscalation` detection rule.

3. **CreatePolicyVersion** — The attacker creates a new policy version with `"Action": "*", "Resource": "*"` permissions. This is a second `PrivilegeEscalation` indicator, increasing the Blast Radius Score further.

4. **StopLogging** — The attacker calls `cloudtrail:StopLogging` to disable the org-wide trail. This immediately triggers the `LoggingDisruption` rule at Critical severity, which is the highest-priority detection in the system.

### Event-to-Rule Mapping

| Step | CloudTrail Event | Detection Rule Triggered | Severity |
|------|-----------------|--------------------------|----------|
| 1 | `iam:CreateUser` | — (context building) | — |
| 2 | `iam:AttachUserPolicy` | `PrivilegeEscalation` (CreateUser + AttachUserPolicy in 60m window) | High |
| 3 | `iam:CreatePolicyVersion` | `PrivilegeEscalation` (CreatePolicyVersion indicator) | High |
| 4 | `cloudtrail:StopLogging` | `LoggingDisruption` | Critical |

---

## Running the Demo

All commands use `--mode mock` (the default), which runs entirely in-process with no AWS infrastructure.

**Run the full demo (all five phases):**

```bash
python scripts/simulate-attack.py --mode mock
```

**Run with verbose per-event output:**

```bash
python scripts/simulate-attack.py --mode mock --verbose
```

**Run only Phase 4 (display the Blast Radius Score):**

```bash
python scripts/simulate-attack.py --mode mock --phase 4
```

**Run with a custom identity ARN:**

```bash
python scripts/simulate-attack.py --mode mock --identity arn:aws:iam::999999999999:user/demo-attacker
```

**Run with a longer polling timeout (useful on slow machines):**

```bash
python scripts/simulate-attack.py --mode mock --timeout 60
```

---

## What to Narrate

Use these talking points when presenting the demo live to an interviewer. Each phase maps to a section of the `simulate-attack.py` output.

### Phase 1 — Seed IAM Identity

> "We start by seeding an identity record for the attacker. In production, the Identity_Collector Lambda does this automatically when it sees the first CloudTrail event from an identity. Here we're pre-seeding it so the scoring engine has a profile to work with."

- Point out the `identity_arn`, `identity_type`, and `account_id` fields
- Mention that `event_count` starts at 0 and is incremented by the Event_Normalizer

### Phase 2 — Inject Privilege Escalation Events

> "Now we inject the four CloudTrail events that represent the attack sequence. In production, these would arrive from EventBridge after CloudTrail captures them. The Event_Normalizer normalizes them into Event_Summary records and asynchronously invokes the Detection_Engine."

- Point out the four events and their timestamps (15-minute window)
- Mention that the Detection_Engine receives all four events and evaluates them against 7 detection rules
- Highlight that `PrivilegeEscalation` is a context-aware rule — it needs to see `CreateUser` followed by `AttachUserPolicy` in the same time window

### Phase 3 — Poll for Incident

> "The Detection_Engine found a match and the Incident_Processor created a Critical-severity incident. Notice the `incident_id` — this is the correlation key that ties together the detection, the score, and the remediation audit log."

- Point out the `severity`, `detection_type`, and `identity_arn` fields
- Mention that the Incident_Processor deduplicates incidents — a second identical detection within the dedup window would not create a new incident
- Note that High+ severity incidents trigger an async invoke to the Remediation_Engine

### Phase 4 — Display Blast Radius Score

> "The Score_Engine calculated a Blast Radius Score of 85 out of 100. More importantly, look at the contributing factors — every point is traceable to a named rule. This is what I mean by explainable scoring: there's no black box here."

- Walk through each contributing factor and the rule it maps to
- Point out the `severity` field (`Critical`) and explain the severity thresholds (0–29 Low, 30–59 Medium, 60–79 High, 80–100 Critical)
- Mention the score cap at 100 — correlated indicators don't cause runaway scores

### Phase 5 — Show Audit Log

> "Finally, the Remediation_Engine evaluated the incident against the configured rules. In monitor mode — the safe default — all actions are suppressed and recorded. The audit log is append-only with a 365-day TTL, so you have a complete, immutable record of every remediation decision."

- Point out the `outcome` field (`suppressed` in monitor mode vs `executed` in enforce mode)
- Mention the safety controls: excluded ARNs, protected accounts, cooldown, and rate limit
- Note that switching to `enforce` mode would have executed `disable_iam_user` and `notify_security_team`

---

## Expected Output

Below is the full output of a successful mock run. Inline comments (prefixed with `#`) explain each section.

```
# ── Phase 1: Seed IAM Identity ──────────────────────────────────────────────
# The attacker's identity profile is written to the Identity_Profile table.
# In production this happens automatically via Identity_Collector Lambda.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase 1: Seed IAM Identity
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Identity ARN : arn:aws:iam::123456789012:user/attacker
  Identity Type: IAMUser
  Account ID   : 123456789012
  Status       : ✓ PASS (0.12s)

# ── Phase 2: Inject Privilege Escalation Events ──────────────────────────────
# Four CloudTrail events are written to the Event_Summary table.
# The Detection_Engine evaluates them and finds two rule matches.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase 2: Inject Privilege Escalation Events
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Events injected : 4
  Events:
    [2026-03-25T10:00:00Z] iam:CreateUser
    [2026-03-25T10:05:00Z] iam:AttachUserPolicy  → PrivilegeEscalation triggered
    [2026-03-25T10:10:00Z] iam:CreatePolicyVersion → PrivilegeEscalation (2nd indicator)
    [2026-03-25T10:15:00Z] cloudtrail:StopLogging → LoggingDisruption triggered
  Status       : ✓ PASS (1.43s)

# ── Phase 3: Poll for Incident ───────────────────────────────────────────────
# The Incident_Processor created a Critical incident.
# The incident_id is the correlation key for scoring and remediation.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase 3: Poll for Incident
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Incident ID    : inc-a1b2c3d4-e5f6-7890-abcd-ef1234567890
  Detection Type : privilege_escalation
  Severity       : Critical
  Identity ARN   : arn:aws:iam::123456789012:user/attacker
  Status         : ✓ PASS (2.01s)

# ── Phase 4: Display Blast Radius Score ──────────────────────────────────────
# Score of 85 = Critical. Each contributing factor is named and traceable.
# The score cap at 100 prevents correlated indicators from inflating the score.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase 4: Display Blast Radius Score
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Score    : 85 / 100
  Severity : Critical
  Contributing Factors:
    • privilege_escalation_pattern  (+35)
    • logging_disruption            (+30)
    • iam_modification_spike        (+20)
  Status   : ✓ PASS (0.08s)

# ── Phase 5: Show Audit Log ──────────────────────────────────────────────────
# Remediation_Engine evaluated the incident in monitor mode.
# All actions are suppressed and recorded — no IAM mutations were made.
# The audit log is append-only with a 365-day TTL.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase 5: Show Audit Log
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Audit entries for arn:aws:iam::123456789012:user/attacker:

  Timestamp             | Action                  | Outcome     | Risk Mode
  ──────────────────────┼─────────────────────────┼─────────────┼──────────
  2026-03-25T10:15:03Z  | disable_iam_user         | suppressed  | monitor
  2026-03-25T10:15:03Z  | notify_security_team     | suppressed  | monitor

  Status : ✓ PASS (0.09s)

# ── Summary ──────────────────────────────────────────────────────────────────

┌─────────┬──────────────────────────────┬────────┬──────────┐
│ Phase   │ Name                         │ Status │ Duration │
├─────────┼──────────────────────────────┼────────┼──────────┤
│ 1       │ Seed IAM Identity            │ ✓ PASS │ 0.12s    │
│ 2       │ Inject Privilege Escalation  │ ✓ PASS │ 1.43s    │
│ 3       │ Poll for Incident            │ ✓ PASS │ 2.01s    │
│ 4       │ Display Blast Radius Score   │ ✓ PASS │ 0.08s    │
│ 5       │ Show Audit Log               │ ✓ PASS │ 0.09s    │
└─────────┴──────────────────────────────┴────────┴──────────┘
All phases passed. Total: 3.73s
```

---

## Cleanup

### Mock Mode (default)

No cleanup is needed. Mock mode uses moto's in-process AWS mock, which is torn down when the script exits. No data is written to any real DynamoDB table, S3 bucket, or SNS topic. You can run the script as many times as you like without any side effects.

### Live Mode (`--mode live`)

Live mode writes real records to DynamoDB. To clean up after a live run, delete the seeded records from the following tables (using the `identity_arn` as the key):

- `{env}-identity-profile` — delete item with `identity_arn = <attacker ARN>`
- `{env}-blast-radius-score` — delete item with `identity_arn = <attacker ARN>`
- `{env}-incident` — query `IdentityIndex` GSI and delete all items for the attacker ARN
- `{env}-event-summary` — query `IdentityTimeIndex` GSI and delete all items for the attacker ARN
- `{env}-remediation-audit-log` — query `IdentityTimeIndex` GSI and delete all items for the attacker ARN

The `{env}-remediation-config` table is seeded with a default record but is not attacker-specific — leave it in place.
