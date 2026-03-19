import unittest

from app.api import ai as ai_api
from app.api import campaigns as campaigns_api
from app.api import creative as creative_api
from app.api import dashboard as dashboard_api
from app.api import dependencies as deps
from app.api import rules as rules_api
from app.services.auth import AuthUser


class SubaccountModuleEnforcementTests(unittest.TestCase):
    def test_enforce_module_access_allows_scoped_user_with_module(self):
        original = deps.team_members_service.get_subaccount_my_access
        try:
            deps.team_members_service.get_subaccount_my_access = lambda **kwargs: {"module_keys": ["rules", "dashboard"]}
            deps.enforce_subaccount_module_access(
                user=AuthUser(email="u@example.com", role="subaccount_user", allowed_subaccount_ids=(12,), access_scope="subaccount"),
                subaccount_id=12,
                module_key="rules",
            )
        finally:
            deps.team_members_service.get_subaccount_my_access = original

    def test_enforce_module_access_denies_when_module_missing(self):
        original = deps.team_members_service.get_subaccount_my_access
        try:
            deps.team_members_service.get_subaccount_my_access = lambda **kwargs: {"module_keys": ["dashboard"]}
            with self.assertRaises(deps.HTTPException) as ctx:
                deps.enforce_subaccount_module_access(
                    user=AuthUser(email="u@example.com", role="subaccount_user", allowed_subaccount_ids=(12,), access_scope="subaccount"),
                    subaccount_id=12,
                    module_key="rules",
                )
            self.assertEqual(ctx.exception.status_code, 403)
            self.assertEqual(str(ctx.exception.detail), deps.NAVIGATION_ACCESS_DENIED_MESSAGE)
        finally:
            deps.team_members_service.get_subaccount_my_access = original

    def test_enforce_module_access_keeps_agency_bypass(self):
        deps.enforce_subaccount_module_access(
            user=AuthUser(email="admin@example.com", role="agency_admin"),
            subaccount_id=12,
            module_key="rules",
        )

    def test_enforce_module_access_legacy_fallback_full_catalog(self):
        user = AuthUser(email="legacy@example.com", role="subaccount_user", user_id=None, allowed_subaccount_ids=(12,), access_scope="subaccount")
        deps.enforce_subaccount_module_access(user=user, subaccount_id=12, module_key="campaigns")

    def test_subaccount_access_denied_before_module_check(self):
        original = deps.team_members_service.get_subaccount_my_access
        try:
            deps.team_members_service.get_subaccount_my_access = lambda **kwargs: {"module_keys": ["rules"]}
            with self.assertRaises(deps.HTTPException) as ctx:
                deps.enforce_subaccount_module_access(
                    user=AuthUser(email="u@example.com", role="subaccount_user", allowed_subaccount_ids=(8,), access_scope="subaccount"),
                    subaccount_id=12,
                    module_key="rules",
                )
            self.assertEqual(ctx.exception.status_code, 403)
            self.assertIn("sub-account", str(ctx.exception.detail))
        finally:
            deps.team_members_service.get_subaccount_my_access = original

    def test_campaigns_summary_forbidden_without_campaigns_module(self):
        user = AuthUser(email="u@example.com", role="subaccount_user", allowed_subaccount_ids=(10,), access_scope="subaccount")
        original_access = deps.team_members_service.get_subaccount_my_access
        original_dashboard = campaigns_api.unified_dashboard_service.get_client_dashboard
        try:
            deps.team_members_service.get_subaccount_my_access = lambda **kwargs: {"module_keys": ["dashboard"]}
            campaigns_api.unified_dashboard_service.get_client_dashboard = lambda **kwargs: {"is_synced": True}
            with self.assertRaises(campaigns_api.HTTPException) as ctx:
                campaigns_api.campaigns_summary(client_id=10, start_date=None, end_date=None, business_period_grain="day", user=user)
            self.assertEqual(ctx.exception.status_code, 403)
        finally:
            deps.team_members_service.get_subaccount_my_access = original_access
            campaigns_api.unified_dashboard_service.get_client_dashboard = original_dashboard

    def test_campaigns_summary_allowed_with_campaigns_module(self):
        user = AuthUser(email="u@example.com", role="subaccount_user", allowed_subaccount_ids=(10,), access_scope="subaccount")
        original_access = deps.team_members_service.get_subaccount_my_access
        original_dashboard = campaigns_api.unified_dashboard_service.get_client_dashboard
        try:
            deps.team_members_service.get_subaccount_my_access = lambda **kwargs: {"module_keys": ["campaigns"]}
            campaigns_api.unified_dashboard_service.get_client_dashboard = lambda **kwargs: {"is_synced": True, "totals": {}}
            payload = campaigns_api.campaigns_summary(client_id=10, start_date=None, end_date=None, business_period_grain="day", user=user)
            self.assertEqual(payload["is_synced"], True)
        finally:
            deps.team_members_service.get_subaccount_my_access = original_access
            campaigns_api.unified_dashboard_service.get_client_dashboard = original_dashboard

    def test_rules_endpoint_forbidden_without_rules_module(self):
        user = AuthUser(email="u@example.com", role="subaccount_user", allowed_subaccount_ids=(10,), access_scope="subaccount")
        original_access = deps.team_members_service.get_subaccount_my_access
        original_list = rules_api.rules_engine_service.list_rules
        try:
            deps.team_members_service.get_subaccount_my_access = lambda **kwargs: {"module_keys": ["dashboard"]}
            rules_api.rules_engine_service.list_rules = lambda client_id: []
            with self.assertRaises(rules_api.HTTPException) as ctx:
                rules_api.list_rules(client_id=10, user=user)
            self.assertEqual(ctx.exception.status_code, 403)
        finally:
            deps.team_members_service.get_subaccount_my_access = original_access
            rules_api.rules_engine_service.list_rules = original_list

    def test_dashboard_endpoint_forbidden_without_dashboard_module(self):
        user = AuthUser(email="u@example.com", role="subaccount_user", allowed_subaccount_ids=(10,), access_scope="subaccount")
        original_access = deps.team_members_service.get_subaccount_my_access
        original_dashboard = dashboard_api.unified_dashboard_service.get_client_dashboard
        try:
            deps.team_members_service.get_subaccount_my_access = lambda **kwargs: {"module_keys": ["campaigns"]}
            dashboard_api.unified_dashboard_service.get_client_dashboard = lambda **kwargs: {"is_synced": True}
            with self.assertRaises(dashboard_api.HTTPException) as ctx:
                dashboard_api.client_dashboard(client_id=10, user=user)
            self.assertEqual(ctx.exception.status_code, 403)
        finally:
            deps.team_members_service.get_subaccount_my_access = original_access
            dashboard_api.unified_dashboard_service.get_client_dashboard = original_dashboard

    def test_creative_endpoint_forbidden_without_creative_module(self):
        user = AuthUser(email="u@example.com", role="subaccount_user", allowed_subaccount_ids=(10,), access_scope="subaccount")
        original_access = deps.team_members_service.get_subaccount_my_access
        original_list = creative_api.creative_workflow_service.list_assets
        try:
            deps.team_members_service.get_subaccount_my_access = lambda **kwargs: {"module_keys": ["dashboard"]}
            creative_api.creative_workflow_service.list_assets = lambda **kwargs: []
            with self.assertRaises(creative_api.HTTPException) as ctx:
                creative_api.list_assets(client_id=10, user=user)
            self.assertEqual(ctx.exception.status_code, 403)
        finally:
            deps.team_members_service.get_subaccount_my_access = original_access
            creative_api.creative_workflow_service.list_assets = original_list

    def test_recommendations_endpoint_forbidden_without_recommendations_module(self):
        user = AuthUser(email="u@example.com", role="subaccount_user", allowed_subaccount_ids=(10,), access_scope="subaccount")
        original_access = deps.team_members_service.get_subaccount_my_access
        original_list = ai_api.recommendations_service.list_recommendations
        try:
            deps.team_members_service.get_subaccount_my_access = lambda **kwargs: {"module_keys": ["dashboard"]}
            ai_api.recommendations_service.list_recommendations = lambda client_id: []
            with self.assertRaises(ai_api.HTTPException) as ctx:
                ai_api.list_recommendations(client_id=10, user=user)
            self.assertEqual(ctx.exception.status_code, 403)
        finally:
            deps.team_members_service.get_subaccount_my_access = original_access
            ai_api.recommendations_service.list_recommendations = original_list


if __name__ == "__main__":
    unittest.main()
