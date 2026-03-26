> **Automated version available:** This document describes the demo scenario in narrative form. To run it end-to-end locally (no AWS credentials required), use the automated script and guide:
>
> - **Script:** [`scripts/simulate-attack.py`](../../scripts/simulate-attack.py) — executes all five phases in mock mode using moto
> - **Guide:** [`docs/demo/demo-guide.md`](demo-guide.md) — step-by-step instructions, narration talking points, and expected output

---

# Radius — Demo Scenario: Privilege Escalation Attack

## Scenario Summary

A compromised IAM user in account `123456789012` executes a four-step privilege escalation sequence over a 15-minute window. The attacker's goal is to create a persistent backdoor with administrator access and then disable CloudTrail logging to cover their tracks.

## Actor

- **Identity:** `arn:aws:iam::123456789012:user/attacker`
- **Identity Type:** IAMUser
- **Account:** `123456789012`

## Attack Sequence

### Step 1 — CreateUser (`10:00 UTC`)

The attacker calls `iam:CreateUser` to create a new IAM user (`backdoor-user`). This event is normalized by the Event_Normalizer and stored in the Event_Summary table. The Identity_Collector upserts the attacker's Identity_Profile record.

### Step 2 — AttachUserPolicy (`10:05 UTC`)

The attacker calls `iam:AttachUserPolicy` to attach the `AdministratorAccess` managed policy to `backdoor-user`. The Detection_Engine evaluates the event in context: seeing `CreateUser` followed by `AttachUserPolicy` within a 60-minute window triggers the `PrivilegeEscalation` rule at High severity.

### Step 3 — CreatePolicyVersion (`10:10 UTC`)

The attacker calls `iam:CreatePolicyVersion` with a document granting `"Action": "*", "Resource": "*"`. This is a second `PrivilegeEscalation` indicator. The Score_Engine recalculates the Blast Radius Score, incorporating both privilege escalation signals.

### Step 4 — StopLogging (`10:15 UTC`)

The attacker calls `cloudtrail:StopLogging` to disable the org-wide CloudTrail trail. This immediately triggers the `LoggingDisruption` rule at Critical severity. The Incident_Processor creates a Critical incident and asynchronously invokes the Remediation_Engine.

## Radius Response

| Component | Action |
|-----------|--------|
| Event_Normalizer | Normalizes all 4 events into Event_Summary records |
| Identity_Collector | Upserts Identity_Profile for the attacker |
| Detection_Engine | Fires `PrivilegeEscalation` (High) and `LoggingDisruption` (Critical) |
| Incident_Processor | Creates a Critical incident; publishes SNS alert |
| Score_Engine | Calculates Blast Radius Score of 85 (Critical) |
| Remediation_Engine | Evaluates `disable_iam_user` + `notify_security_team`; suppresses in monitor mode |

## Expected Outcome

- Blast Radius Score: **85 / 100 (Critical)**
- Incident severity: **Critical**
- Remediation audit entries: 2 (both `suppressed` in default monitor mode)
- In `enforce` mode: `disable_iam_user` would execute, `notify_security_team` would publish to SNS
