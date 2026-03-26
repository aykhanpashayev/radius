# Scoring Pipeline

The Score_Engine Lambda calculates a Blast Radius Score (0–100) for each IAM identity by evaluating eight rule-based scoring rules against a pre-fetched ScoringContext. It can be triggered on a per-identity EventBridge schedule or invoked directly by Event_Normalizer for immediate scoring after a new event arrives. Each rule emits a named contributing factor with a point value, making every score fully explainable. The final score is the sum of all rule contributions, capped at 100 to prevent correlated-indicator inflation.

```mermaid
flowchart TD
    EB_SCHED[EventBridge Schedule] -->|scheduled invoke| SE[Score_Engine\nLambda]
    EN[Event_Normalizer\nLambda] -->|async invoke| SE

    SE --> SC[ScoringContext.build]

    SC -->|query| IP[(Identity_Profile\nDynamoDB)]
    SC -->|query recent events| ES[(Event_Summary\nDynamoDB)]
    SC -->|query open incidents| IN[(Incident\nDynamoDB)]
    SC -->|query prior score| BS[(Blast_Radius_Score\nDynamoDB)]

    SC --> R1[PrivilegeEscalationRule]
    SC --> R2[CrossAccountActivityRule]
    SC --> R3[RootUserActivityRule]
    SC --> R4[LoggingDisruptionRule]
    SC --> R5[APIBurstAnomalyRule]
    SC --> R6[UnusualServiceUsageRule]
    SC --> R7[IAMPolicyModificationRule]
    SC --> R8[OpenIncidentPenaltyRule]

    R1 --> CAP[sum_and_cap\nsum scores, cap at 100]
    R2 --> CAP
    R3 --> CAP
    R4 --> CAP
    R5 --> CAP
    R6 --> CAP
    R7 --> CAP
    R8 --> CAP

    CAP --> SR[ScoreResult\nscore value · severity level · contributing_factors]
    SR -->|write| BS2[(Blast_Radius_Score\nDynamoDB)]
```
