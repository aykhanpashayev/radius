# API Layer

The React Dashboard communicates with the backend exclusively through API Gateway over HTTPS. API Gateway proxies every request to the API_Handler Lambda, which handles all read and write operations against DynamoDB. The handler is organized into five endpoint groups — Identity, Incident, Score, Event, and Remediation — each backed by its own DynamoDB table or pair of tables. No Lambda function other than API_Handler is reachable from the frontend.

```mermaid
flowchart TD
    RD[React Dashboard] -->|HTTPS| AG[API Gateway]
    AG -->|proxy| AH[API_Handler\nLambda]

    AH --> GRP1[Identity endpoints]
    AH --> GRP2[Incident endpoints]
    AH --> GRP3[Score endpoints]
    AH --> GRP4[Event endpoints]
    AH --> GRP5[Remediation endpoints]

    GRP1 -->|read/write| IP[(Identity_Profile\nDynamoDB)]
    GRP2 -->|read/write| IN[(Incident\nDynamoDB)]
    GRP3 -->|read/write| BS[(Blast_Radius_Score\nDynamoDB)]
    GRP4 -->|read/write| ES[(Event_Summary\nDynamoDB)]
    GRP5 -->|read/write| RC[(Remediation_Config\nDynamoDB)]
    GRP5 -->|read| RAL[(Remediation_Audit_Log\nDynamoDB)]
```
