"""Detection rules package — exports ALL_RULES for RuleEngine."""
from backend.functions.detection_engine.rules.privilege_escalation import PrivilegeEscalationRule
from backend.functions.detection_engine.rules.iam_policy_modification_spike import IAMPolicyModificationSpikeRule
from backend.functions.detection_engine.rules.cross_account_role_assumption import CrossAccountRoleAssumptionRule
from backend.functions.detection_engine.rules.logging_disruption import LoggingDisruptionRule
from backend.functions.detection_engine.rules.root_user_activity import RootUserActivityRule
from backend.functions.detection_engine.rules.api_burst_anomaly import APIBurstAnomalyRule
from backend.functions.detection_engine.rules.unusual_service_usage import UnusualServiceUsageRule

ALL_RULES = [
    PrivilegeEscalationRule,
    IAMPolicyModificationSpikeRule,
    CrossAccountRoleAssumptionRule,
    LoggingDisruptionRule,
    RootUserActivityRule,
    APIBurstAnomalyRule,
    UnusualServiceUsageRule,
]
