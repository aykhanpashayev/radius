# Requirements Document — Phase 8: Final Polish and Portfolio Readiness

## Introduction

Phase 8 prepares Radius for use as a professional portfolio project. The goal is to make the repository immediately legible to a technical recruiter, hiring manager, or senior engineer who lands on it cold — and to give the project author a polished, rehearsable demo they can walk through in a technical interview.

All work in Phase 8 is documentation, tooling, and presentation. No new Lambda logic, DynamoDB tables, API endpoints, or Terraform resources are introduced. Every change must be runnable locally without an active AWS account (using moto for any script that touches AWS APIs).

---

## Glossary

- **Portfolio Visitor**: A recruiter, hiring manager, or senior engineer reviewing the repository on GitHub without prior context.
- **Demo Scenario**: A scripted, end-to-end walkthrough of a privilege escalation attack that exercises the full Radius pipeline.
- **simulate-attack.py**: A new CLI script that orchestrates the demo scenario programmatically.
- **run-tests.sh**: A new shell script that runs all test suites and prints a formatted coverage summary.
- **Architecture Diagram**: A Mermaid-based flowchart embedded in a Markdown file under `docs/architecture/`.
- **Project Walkthrough**: An interview-ready narrative document that explains every design decision in the project.
- **Repository Hygiene**: Removal of stale files, consistent file headers, and a clean `.gitignore`.

---

## Requirements

### Requirement 1: README Overhaul

**User Story:** As a portfolio visitor, I want a README that immediately tells me what Radius does, why it matters, and how to explore it, so that I can evaluate the project in under two minutes.

#### Acceptance Criteria

1. THE `README.md` SHALL be completely replaced with a new document that covers: project headline, architecture diagram (embedded Mermaid or linked image), key features list, full tech stack with badges, quick-start instructions, test results summary, project walkthrough link, and contributing note.
2. THE README SHALL include shield.io badge links for: Python version, Terraform version, AWS Lambda, DynamoDB, React, and a "tests passing" badge.
3. THE README SHALL include a one-paragraph "What is Radius?" section that explains the blast radius concept, the identity-risk focus, and the event-driven architecture in plain language accessible to a non-specialist recruiter.
4. THE README SHALL include a "Key Features" section listing at least six distinct capabilities of the platform (e.g. real-time detection, explainable scoring, automated remediation, multi-account support, property-based test suite, serverless cost model).
5. THE README SHALL include a "Tech Stack" section that lists every major technology with a one-line description of its role in the system.
6. THE README SHALL include a "Quick Start" section with step-by-step commands to clone the repo, install dependencies, run the test suite, and run the demo scenario locally.
7. THE README SHALL include a "Test Results" section that shows the output of `scripts/run-tests.sh` (or a representative excerpt) so a visitor can see test coverage without running anything.
8. THE README SHALL include a "Project Walkthrough" section that links to `docs/walkthrough.md` and describes it as an interview-ready narrative.
9. THE README SHALL NOT reference Phase 2 scope, IMPLEMENTATION_SUMMARY.md, or any stale content from the previous README.
10. THE README SHALL be written in a tone appropriate for a senior engineering audience — precise, direct, and free of marketing language.

---

### Requirement 2: Architecture Diagrams

**User Story:** As a portfolio visitor or interviewer, I want clear visual diagrams of the system architecture, so that I can understand the data flow and component relationships without reading all the code.

#### Acceptance Criteria

1. A Mermaid flowchart diagram SHALL be created at `docs/architecture/pipeline-overview.md` showing the full event processing pipeline from CloudTrail through EventBridge → Event_Normalizer → Detection_Engine → Incident_Processor → Remediation_Engine, with SNS and DynamoDB writes annotated.
2. A Mermaid flowchart diagram SHALL be created at `docs/architecture/scoring-pipeline.md` showing the Score_Engine pipeline: trigger sources (EventBridge schedule, direct invoke) → ScoringContext.build() → 8 scoring rules → ScoreResult → Blast_Radius_Score table.
3. A Mermaid flowchart diagram SHALL be created at `docs/architecture/remediation-branch.md` showing the remediation pipeline branch: Incident_Processor → Remediation_Engine → safety controls → rule matching → action execution → audit log, with the three Risk Mode paths annotated.
4. A Mermaid flowchart diagram SHALL be created at `docs/architecture/api-layer.md` showing the API layer: React Dashboard → API Gateway → API_Handler Lambda → DynamoDB tables, with all endpoint groups annotated.
5. EACH diagram file SHALL include a prose introduction (2–4 sentences) before the Mermaid block explaining what the diagram shows and why this component exists.
6. EACH diagram SHALL use Mermaid `flowchart TD` syntax and SHALL be renderable by GitHub's built-in Mermaid renderer without plugins.
7. THE `docs/architecture.md` file SHALL be updated to include links to all four new diagram files in a "Diagrams" section.

---

### Requirement 3: Demo Scenario

**User Story:** As a project author preparing for a technical interview, I want a scripted demo scenario that I can run and narrate, so that I can demonstrate the full Radius pipeline end-to-end in under ten minutes.

#### Acceptance Criteria

1. A demo guide SHALL be created at `docs/demo/demo-guide.md` that describes a complete privilege escalation attack scenario from the attacker's perspective, maps each attack step to the CloudTrail events it generates, and explains what Radius detects and why.
2. THE demo guide SHALL include a "Prerequisites" section listing all local dependencies (Python 3.11+, pip packages, AWS credentials or moto mock mode).
3. THE demo guide SHALL include a "Running the Demo" section with exact shell commands to execute each phase of the demo.
4. THE demo guide SHALL include a "What to Narrate" section with bullet points the presenter can use to explain each phase to an interviewer.
5. THE demo guide SHALL reference `scripts/simulate-attack.py` as the primary automation tool and explain each CLI flag.
6. THE demo guide SHALL include a "Cleanup" section explaining how to reset the local state after the demo.
7. THE existing `docs/demo/demo-scenario.md` SHALL be updated to cross-reference the new `demo-guide.md` and `simulate-attack.py`.

---

### Requirement 4: simulate-attack.py Script

**User Story:** As a project author, I want a single CLI script that orchestrates the full demo scenario, so that I can run the entire attack simulation with one command and see structured output at each phase.

#### Acceptance Criteria

1. THE script SHALL be created at `scripts/simulate-attack.py` and SHALL be executable with `python scripts/simulate-attack.py`.
2. THE script SHALL accept the following CLI arguments: `--mode` (values: `mock` or `live`, default: `mock`), `--identity` (IAM ARN to use as the attacker identity, default: `arn:aws:iam::123456789012:user/attacker`), `--verbose` (flag, enables per-event output), `--phase` (integer 1–5, runs only the specified phase, default: all phases).
3. THE script SHALL execute five phases in order:
   - Phase 1: Seed IAM identity — write an Identity_Profile record for the attacker identity using `seed-dev-data.py` logic or direct DynamoDB write.
   - Phase 2: Inject privilege escalation events — call `inject-events.py` logic to inject a sequence of CloudTrail events representing a privilege escalation attack (CreateUser → AttachUserPolicy → CreatePolicyVersion → StopLogging).
   - Phase 3: Poll for incident — query the Incident table (or mock) until an incident with `detection_type=privilege_escalation` appears for the attacker identity, with a configurable timeout (default 30 seconds).
   - Phase 4: Display blast radius score — query the Blast_Radius_Score table and print the score value, severity level, and contributing factors.
   - Phase 5: Show audit log — query the Remediation_Audit_Log table and print the most recent 10 audit entries for the attacker identity.
4. IN `--mode mock`, THE script SHALL use moto to mock all AWS API calls so the demo runs without any AWS credentials or live infrastructure.
5. THE script SHALL print a formatted, human-readable summary at the end of each phase showing: phase name, status (PASS / FAIL / SKIPPED), duration in seconds, and key output values.
6. THE script SHALL exit with code 0 if all phases complete successfully and code 1 if any phase fails.
7. THE script SHALL include a `--help` output that explains all flags and the five phases.

---

### Requirement 5: run-tests.sh Script

**User Story:** As a portfolio visitor or CI operator, I want a single script that runs all test suites and prints a coverage summary, so that I can verify the test suite passes and see coverage metrics without knowing the project's test layout.

#### Acceptance Criteria

1. THE script SHALL be created at `scripts/run-tests.sh` and SHALL be executable (`chmod +x`).
2. THE script SHALL run the following test suites in order: unit tests (`backend/tests/test_*.py`, excluding integration), integration tests (`backend/tests/integration/`), and property-based tests (`backend/tests/test_*_properties.py`).
3. THE script SHALL use `pytest` with `--cov=backend` and `--cov-report=term-missing` to collect coverage data across all suites.
4. THE script SHALL print a formatted summary table at the end showing: suite name, number of tests, number passed, number failed, and coverage percentage.
5. THE script SHALL exit with code 0 only if all tests pass; it SHALL exit with code 1 if any test fails.
6. THE script SHALL support a `--fast` flag that skips property-based tests (which can be slow) and runs only unit and integration tests.
7. THE script SHALL print elapsed time for each suite and total elapsed time.
8. THE script SHALL be runnable on macOS and Linux without modification (use `#!/usr/bin/env bash`).

---

### Requirement 6: Documentation Completeness

**User Story:** As a portfolio visitor reading the docs, I want every documentation file to be complete and internally consistent, so that I can trust the documentation reflects the actual system.

#### Acceptance Criteria

1. `docs/api-reference.md` SHALL include all remediation API endpoints (`GET /remediation/config`, `PUT /remediation/config/mode`, `GET /remediation/rules`, `POST /remediation/rules`, `DELETE /remediation/rules/{rule_id}`, `GET /remediation/audit`) with request/response schemas matching the Phase 7 implementation.
2. `docs/deployment.md` SHALL include a section describing the Phase 7 Terraform additions (Remediation_Engine Lambda, Remediation_Config table, Remediation_Audit_Log table, Remediation_Topic SNS) and the new environment variables required.
3. `docs/developer-guide.md` SHALL include a section on running the full test suite locally using `scripts/run-tests.sh`, including how to install test dependencies and interpret coverage output.
4. `docs/monitoring.md` SHALL include descriptions of CloudWatch log groups for all 7 Lambda functions (including Remediation_Engine) and describe the structured log fields emitted by each function.
5. `docs/database-schema.md` SHALL include the full schemas for `Remediation_Config` and `Remediation_Audit_Log` tables including all GSIs, TTL configuration, and example records.
6. EACH documentation file SHALL have a consistent header format: `# Title`, a one-paragraph overview, and a table of contents for files longer than 100 lines.

---

### Requirement 7: Repository Hygiene

**User Story:** As a portfolio visitor cloning the repository, I want a clean, professional repository structure with no stale files or inconsistent formatting, so that the project looks well-maintained.

#### Acceptance Criteria

1. `IMPLEMENTATION_SUMMARY.md` SHALL be deleted from the repository root.
2. `.gitignore` SHALL be updated to include: `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.hypothesis/`, `*.egg-info/`, `dist/`, `build/`, `.env`, `.env.*`, `*.tfstate`, `*.tfstate.backup`, `.terraform/`, `node_modules/`, `frontend/build/`, `coverage.xml`, `.coverage`, `htmlcov/`.
3. A `.python-version` file SHALL be added to the repository root containing `3.11` to signal the expected Python version to pyenv users.
4. EVERY Python file in `backend/functions/` SHALL have a module-level docstring (one sentence minimum) describing the file's purpose.
5. EVERY shell script in `scripts/` SHALL have a `#!/usr/bin/env bash` shebang and a comment block at the top describing what the script does and its usage.
6. THE repository root SHALL contain no files other than: `README.md`, `.gitignore`, `.python-version`, and directories (`backend/`, `docs/`, `frontend/`, `infra/`, `sample-data/`, `scripts/`, `.kiro/`).

---

### Requirement 8: Logging and Observability Improvements

**User Story:** As a developer debugging a production incident, I want structured, consistent log fields across all Lambda functions, so that I can correlate events across the pipeline using CloudWatch Logs Insights.

#### Acceptance Criteria

1. EVERY Lambda function SHALL emit structured JSON logs using the existing `backend/common/logging_utils.py` logger.
2. EVERY log entry SHALL include the fields: `function_name`, `correlation_id`, `timestamp`, `level`, and `message`.
3. THE `correlation_id` SHALL be propagated from Event_Normalizer through all downstream async invocations (Detection_Engine, Identity_Collector, Score_Engine) by including it in the invocation payload.
4. `docs/monitoring.md` SHALL include a "Correlation ID Propagation" section explaining how to trace a single CloudTrail event through the full pipeline using the `correlation_id` field in CloudWatch Logs Insights.
5. `docs/monitoring.md` SHALL include example CloudWatch Logs Insights queries for: finding all log entries for a given `correlation_id`, finding all incidents created in the last hour, and finding all remediation actions executed for a given `identity_arn`.

---

### Requirement 9: Project Walkthrough Document

**User Story:** As a project author preparing for a technical interview, I want a single document that narrates every design decision in the project, so that I can use it as a study guide and reference during interviews.

#### Acceptance Criteria

1. A project walkthrough document SHALL be created at `docs/walkthrough.md`.
2. THE walkthrough SHALL cover: project motivation (why blast radius matters), architecture decisions (why serverless, why event-driven, why DynamoDB), detection engine design (rule types, context building, deduplication), scoring model design (why rule-based, how contributing factors work), remediation design (risk modes, safety controls, audit log), frontend design (React dashboard, API Gateway integration), and testing strategy (unit, integration, property-based).
3. FOR EACH design decision, THE walkthrough SHALL include: the decision made, the alternatives considered, and the reason the chosen approach was selected.
4. THE walkthrough SHALL include a "Common Interview Questions" section with at least 8 questions and model answers covering: scalability, cost, security, observability, trade-offs, and what the author would do differently.
5. THE walkthrough SHALL be written in first person and SHALL be between 1,500 and 3,000 words.
6. THE walkthrough SHALL link to the relevant source files and documentation for each section.

---

## Non-Functional Requirements

1. NO new AWS Lambda functions, DynamoDB tables, API Gateway endpoints, SNS topics, or Terraform resources SHALL be created in Phase 8.
2. ALL scripts (`simulate-attack.py`, `run-tests.sh`) SHALL be runnable on a developer laptop without an active AWS account when using `--mode mock` or the default mock mode.
3. `simulate-attack.py` in mock mode SHALL complete all five phases in under 60 seconds on a standard developer laptop.
4. `run-tests.sh` SHALL complete the unit and integration test suites in under 120 seconds on a standard developer laptop.
5. ALL documentation SHALL be written in standard Markdown compatible with GitHub's renderer.
6. ALL Mermaid diagrams SHALL render correctly in GitHub's built-in Mermaid renderer (no custom plugins required).
7. THE README SHALL render correctly on a 1280px-wide browser window without horizontal scrolling.

---

## Correctness Properties

### Property 1: simulate-attack.py Phase Ordering

For any invocation of `simulate-attack.py` without `--phase`, the five phases SHALL execute in strictly ascending order (1 → 2 → 3 → 4 → 5), and Phase N+1 SHALL NOT begin if Phase N fails.

**Validates: Requirement 4.3**

### Property 2: run-tests.sh Exit Code Consistency

For any invocation of `run-tests.sh`, the exit code SHALL be 0 if and only if all executed test suites report zero failures. The exit code SHALL be 1 if any suite reports one or more failures.

**Validates: Requirement 5.5**

### Property 3: simulate-attack.py Mock Mode Isolation

For any invocation of `simulate-attack.py --mode mock`, no real AWS API calls SHALL be made (all calls go through moto). The script SHALL produce identical structured output regardless of whether AWS credentials are present in the environment.

**Validates: Requirement 4.4**
