"""Scoring rules package for Score_Engine.

ALL_RULES is consumed by RuleEngine to instantiate all scoring rules.
Rules are imported defensively so the package loads even if individual
rule modules are not yet implemented.
"""
from __future__ import annotations

_rule_classes = []


def _try_import(module_path: str, class_name: str) -> None:
    try:
        import importlib
        mod = importlib.import_module(module_path)
        _rule_classes.append(getattr(mod, class_name))
    except (ImportError, AttributeError):
        pass


_try_import("backend.functions.score_engine.rules.admin_privileges", "AdminPrivilegesRule")
_try_import("backend.functions.score_engine.rules.iam_permissions_scope", "IAMPermissionsScopeRule")
_try_import("backend.functions.score_engine.rules.iam_modification", "IAMModificationRule")
_try_import("backend.functions.score_engine.rules.logging_disruption", "LoggingDisruptionRule")
_try_import("backend.functions.score_engine.rules.cross_account_trust", "CrossAccountTrustRule")
_try_import("backend.functions.score_engine.rules.role_chaining", "RoleChainingRule")
_try_import("backend.functions.score_engine.rules.privilege_escalation", "PrivilegeEscalationRule")
_try_import("backend.functions.score_engine.rules.lateral_movement", "LateralMovementRule")

ALL_RULES = _rule_classes
