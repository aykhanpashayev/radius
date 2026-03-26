# Remediation Branch

When Incident_Processor creates a High, Very High, or Critical severity incident, it asynchronously invokes the Remediation_Engine Lambda. The engine is configuration-driven: it loads a singleton Remediation_Config record, runs four safety control checks before any rule matching, and then executes actions according to the configured risk mode (monitor, alert, or enforce). Every evaluation — including suppressed and no-match cases — writes an append-only entry to the Remediation_Audit_Log table.

```mermaid
flowchart TD
    INC[Incident_Processor\nLambda] -->|async invoke High+| RE[Remediation_Engine\nLambda]

    RE --> LC[load_config]
    LC -->|read| RC[(Remediation_Config\nDynamoDB)]

    LC --> SC[safety_controls check]

    SC -->|suppressed?| SUP{Suppressed?}
    SUP -->|Yes| SALOG[write suppression\naudit entry]
    SALOG --> RAL[(Remediation_Audit_Log\nDynamoDB)]
    RAL --> END1[END]

    SUP -->|No| MR[match_rules]

    MR --> NOMATCH{Rules matched?}
    NOMATCH -->|No match| NMLOG[write no-match\naudit entry]
    NMLOG --> RAL2[(Remediation_Audit_Log\nDynamoDB)]
    RAL2 --> END2[END]

    NOMATCH -->|Matched| CA[collect_actions]

    CA --> MODE{Risk Mode}

    MODE -->|monitor| MON[log only]
    MON --> ALOG1[write audit log]
    ALOG1 --> RAL3[(Remediation_Audit_Log\nDynamoDB)]

    MODE -->|alert| ALT[write audit log]
    ALT --> RAL4[(Remediation_Audit_Log\nDynamoDB)]
    ALT --> SNS[publish SNS\nRemediation_Topic]

    MODE -->|enforce| ENF[execute IAM actions]
    ENF --> ALOG2[write audit log]
    ALOG2 --> RAL5[(Remediation_Audit_Log\nDynamoDB)]
    ALOG2 --> SNS2[publish SNS\nRemediation_Topic]
```
