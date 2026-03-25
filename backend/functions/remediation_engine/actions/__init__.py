"""Action registry for the Remediation_Engine.

ALL_ACTIONS maps action name strings to RemediationAction instances.
"""

from backend.functions.remediation_engine.actions.block_role_assumption import BlockRoleAssumptionAction
from backend.functions.remediation_engine.actions.disable_iam_user import DisableIAMUserAction
from backend.functions.remediation_engine.actions.notify_security_team import NotifySecurityTeamAction
from backend.functions.remediation_engine.actions.remove_risky_policies import RemoveRiskyPoliciesAction
from backend.functions.remediation_engine.actions.restrict_network_access import RestrictNetworkAccessAction

ALL_ACTIONS: dict = {
    DisableIAMUserAction.action_name: DisableIAMUserAction(),
    RemoveRiskyPoliciesAction.action_name: RemoveRiskyPoliciesAction(),
    BlockRoleAssumptionAction.action_name: BlockRoleAssumptionAction(),
    RestrictNetworkAccessAction.action_name: RestrictNetworkAccessAction(),
    NotifySecurityTeamAction.action_name: NotifySecurityTeamAction(),
}
