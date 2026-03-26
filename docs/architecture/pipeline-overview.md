# Pipeline Overview

Radius processes AWS CloudTrail management events through a fully serverless, event-driven pipeline. CloudTrail captures org-wide control-plane activity and routes it through EventBridge to the Event_Normalizer Lambda, which is the single entry point for all downstream processing. From there, Detection_Engine, Identity_Collector, and Score_Engine are invoked asynchronously — each operating independently so a slow scoring run never blocks incident creation. The React Dashboard reads all pipeline outputs through API Gateway and the API_Handler Lambda.

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
