from __future__ import annotations

from dataclasses import dataclass, asdict
from threading import Lock
from typing import Literal

from app.services.audit import audit_log_service
from app.services.dashboard import unified_dashboard_service

RuleType = Literal["stop_loss", "auto_scale"]
RuleStatus = Literal["active", "paused"]


@dataclass
class Rule:
    id: int
    name: str
    rule_type: RuleType
    threshold: float
    action_value: float
    status: RuleStatus


class RulesEngineService:
    def __init__(self) -> None:
        self._rules: dict[int, list[Rule]] = {}
        self._next_id = 1
        self._lock = Lock()

    def create_rule(
        self,
        client_id: int,
        name: str,
        rule_type: RuleType,
        threshold: float,
        action_value: float,
        status: RuleStatus = "active",
    ) -> dict[str, object]:
        with self._lock:
            rule = Rule(
                id=self._next_id,
                name=name,
                rule_type=rule_type,
                threshold=threshold,
                action_value=action_value,
                status=status,
            )
            self._next_id += 1
            self._rules.setdefault(client_id, []).append(rule)
        return asdict(rule)

    def list_rules(self, client_id: int) -> list[dict[str, object]]:
        with self._lock:
            rules = self._rules.get(client_id, [])
            return [asdict(rule) for rule in rules]

    def evaluate_client_rules(self, client_id: int) -> list[dict[str, object]]:
        dashboard = unified_dashboard_service.get_client_dashboard(client_id)
        totals = dashboard["totals"]
        spend = float(totals.get("spend", 0.0))
        roas = float(totals.get("roas", 0.0))

        with self._lock:
            rules = list(self._rules.get(client_id, []))

        actions: list[dict[str, object]] = []
        for rule in rules:
            if rule.status != "active":
                continue

            triggered = False
            action_payload: dict[str, object] = {}

            if rule.rule_type == "stop_loss" and spend >= rule.threshold:
                triggered = True
                action_payload = {
                    "type": "pause_campaigns",
                    "reason": f"Spend {spend} >= threshold {rule.threshold}",
                }
            elif rule.rule_type == "auto_scale" and roas >= rule.threshold:
                triggered = True
                action_payload = {
                    "type": "increase_budget",
                    "percentage": rule.action_value,
                    "reason": f"ROAS {roas} >= threshold {rule.threshold}",
                }

            if triggered:
                entry = {
                    "client_id": client_id,
                    "rule_id": rule.id,
                    "rule_name": rule.name,
                    "rule_type": rule.rule_type,
                    "action": action_payload,
                }
                actions.append(entry)
                audit_log_service.log(
                    actor_email="system_bot",
                    actor_role="system",
                    action="rules_engine.trigger",
                    resource=f"client:{client_id}",
                    details=entry,
                )

        return actions


rules_engine_service = RulesEngineService()
