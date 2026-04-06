![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)
![Terraform](https://img.shields.io/badge/Terraform-1.7-purple?logo=terraform)
![AWS Lambda](https://img.shields.io/badge/AWS-Lambda-orange?logo=amazonaws)
![DynamoDB](https://img.shields.io/badge/AWS-DynamoDB-blue?logo=amazonaws)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react)
![Tests](https://img.shields.io/badge/tests-passing-brightgreen)

# Radius — Cloud Identity Blast Radius Platform

When an IAM identity is compromised, the blast radius is how much damage it can do. Radius monitors AWS CloudTrail control-plane events across your entire organization, detects suspicious IAM behavior in real time, and calculates an explainable Blast Radius Score (0–100) for every identity. When a score crosses a severity threshold, Radius can automatically trigger remediation actions — disabling users, revoking sessions, or notifying your security team — with a full audit trail of every decision.

```mermaid
flowchart TD
    CT[CloudTrail\nOrg-wide trail] -->|management events| EB[EventBridge\nIAM/STS/EC2 rule]
    EB -->|invoke| EN[Event_Normalizer\nLambda]
    EN -->|write| ES[(Event_Summary\nDynamoDB)]
    EN -->|async invoke| DE[Detection_Engine\nLambda]
    EN -->|async invoke| IC[Identity_Collector\nLambda]
    EN -->|async invoke| SE[Score_Engine\nLambda]
    IC -->|upsert| IP[(Identity_Profile\nDynamoDB)]
    IC -->|write| TR[(Trust_Relationship\nDynamoDB)]
    SE -->|write| BS[(Blast_Radius_Score\nDynamoDB)]
    DE -->|async invoke| INC[Incident_Processor\nLambda]
    INC -->|write| IN[(Incident\nDynamoDB)]
    INC -->|publish High+| SNS1[SNS Alert_Topic]
    INC -->|async invoke High+| RE[Remediation_Engine\nLambda]
    RE -->|read| RC[(Remediation_Config\nDynamoDB)]
    RE -->|write| RAL[(Remediation_Audit_Log\nDynamoDB)]
    RE -->|publish alert/enforce| SNS2[SNS Remediation_Topic]
    AG[API Gateway] -->|proxy| AH[API_Handler\nLambda]
    AH -->|read/write| IP
    AH -->|read/write| BS
    AH -->|read/write| IN
    AH -->|read/write| ES
    AH -->|read/write| RC
    AH -->|read| RAL
    RD[React Dashboard] -->|HTTPS| AG
```

## Key Features

- Real-time detection of 7 IAM attack patterns via a rule-based engine
- Explainable Blast Radius Scores (0–100) with named contributing factors per identity
- Automated remediation with three risk modes: Monitor, Alert, and Enforce
- Immutable audit log of every remediation action evaluation for compliance
- Multi-account AWS Organizations support via org-wide CloudTrail
- Full property-based test suite using Hypothesis (100+ correctness properties)

## Tech Stack

| Technology | Role |
|---|---|
| AWS Lambda (Python 3.11, arm64) | All backend processing — 7 functions |
| Amazon DynamoDB | Primary data store — 7 tables with GSIs |
| Amazon EventBridge | CloudTrail event routing and Score_Engine scheduling |
| Amazon API Gateway | REST API serving the React dashboard |
| Amazon SNS | High-severity alerts and remediation notifications |
| Amazon CloudTrail | Org-wide management event capture |
| Terraform | Infrastructure as Code — all AWS resources |
| React 18 | Frontend dashboard |
| Hypothesis | Property-based testing framework |
| moto | AWS mock library for local testing |

## Quick Start

1. `git clone <repo> && cd radius`
2. `python -m venv .venv && source .venv/bin/activate`
3. `pip install -r backend/requirements-dev.txt`
4. `bash scripts/run-tests.sh` — runs the full test suite
5. `python scripts/simulate-attack.py --mode mock` — runs the demo scenario locally, no AWS credentials needed

> The React dashboard requires a deployed AWS backend. Steps 4 and 5 above work entirely offline. To run the full stack including the UI, follow [docs/deployment.md](docs/deployment.md) to deploy to AWS first.

## Test Results

Run the test suite yourself to see current coverage:

```bash
pip install -r backend/requirements-dev.txt
bash scripts/run-tests.sh
```

The suite covers unit tests, integration tests (using moto AWS mocks), and property-based tests via Hypothesis.

## Deploying to AWS

To deploy Radius in your own AWS account, see [docs/deployment.md](docs/deployment.md). It covers prerequisites, Terraform state setup, building Lambda packages, deploying infrastructure, and verifying the deployment. For extending the platform with new rules or running the test suite, see [docs/developer-guide.md](docs/developer-guide.md).

## Project Walkthrough

For a deep-dive into every design decision, see [docs/walkthrough.md](docs/walkthrough.md).

## Contributing

This is a portfolio project. Pull requests are welcome for bug fixes and documentation improvements. Please open an issue first to discuss any significant changes, and ensure all tests pass before submitting.
