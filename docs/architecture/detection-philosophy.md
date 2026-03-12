# Radius Detection Philosophy

Radius focuses on detecting **high-confidence suspicious identity behavior** rather than generating noisy alerts.

## Design Principles

- Context-aware detection
- Sequence-based analysis
- Identity classification
- Confidence scoring
- Suppression support

## Detection Outcomes

Radius distinguishes between:

Observation  
Finding  
Incident

Not every event becomes an incident.

## Example

A single `AssumeRole` event may be normal.

However:

AssumeRole  
→ IAM policy modification  
→ Logging disable attempt

within a short window strongly suggests compromise and should escalate to an incident.