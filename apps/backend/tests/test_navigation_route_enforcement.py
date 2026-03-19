import unittest

from app.api import clients as clients_api
from app.api import dependencies as deps
from app.api import email_notifications as email_notifications_api
from app.api import email_templates as email_templates_api
from app.api import team as team_api
from app.services.auth import AuthUser


class NavigationRouteEnforcementTests(unittest.TestCase):
    def test_agency_main_route_forbidden_when_agency_clients_missing(self):
        user = AuthUser(email="member@example.com", role="agency_member", user_id=11)
        original = deps.team_members_service.get_agency_my_access
        try:
            deps.team_members_service.get_agency_my_access = lambda **kwargs: {"module_keys": ["agency_dashboard"]}
            with self.assertRaises(clients_api.HTTPException) as ctx:
                clients_api.list_clients(user=user)
            self.assertEqual(ctx.exception.status_code, 403)
            self.assertEqual(ctx.exception.detail, deps.NAVIGATION_ACCESS_DENIED_MESSAGE)
        finally:
            deps.team_members_service.get_agency_my_access = original

    def test_agency_main_route_allowed_when_agency_clients_present(self):
        user = AuthUser(email="member@example.com", role="agency_member", user_id=11)
        original_access = deps.team_members_service.get_agency_my_access
        original_list = clients_api.client_registry_service.list_clients
        try:
            deps.team_members_service.get_agency_my_access = lambda **kwargs: {"module_keys": ["agency_clients"]}
            clients_api.client_registry_service.list_clients = lambda: []
            payload = clients_api.list_clients(user=user)
            self.assertIn("items", payload)
        finally:
            deps.team_members_service.get_agency_my_access = original_access
            clients_api.client_registry_service.list_clients = original_list

    def test_settings_parent_required_for_child_permissions(self):
        user = AuthUser(email="member@example.com", role="agency_member", user_id=22)
        original = deps.team_members_service.get_agency_my_access
        try:
            deps.team_members_service.get_agency_my_access = lambda **kwargs: {"module_keys": ["settings_profile"]}
            with self.assertRaises(deps.HTTPException) as ctx:
                deps.enforce_agency_navigation_access(user=user, permission_key="settings_profile")
            self.assertEqual(ctx.exception.status_code, 403)
            self.assertEqual(ctx.exception.detail, deps.NAVIGATION_ACCESS_DENIED_MESSAGE)
        finally:
            deps.team_members_service.get_agency_my_access = original

    def test_email_templates_blocked_when_settings_parent_off(self):
        user = AuthUser(email="member@example.com", role="agency_member", user_id=22)
        original = deps.team_members_service.get_agency_my_access
        try:
            deps.team_members_service.get_agency_my_access = lambda **kwargs: {"module_keys": ["email_templates"]}
            with self.assertRaises(email_templates_api.HTTPException) as ctx:
                email_templates_api.list_agency_email_templates(user=user)
            self.assertEqual(ctx.exception.status_code, 403)
        finally:
            deps.team_members_service.get_agency_my_access = original

    def test_email_templates_blocked_when_child_off(self):
        user = AuthUser(email="member@example.com", role="agency_member", user_id=22)
        original = deps.team_members_service.get_agency_my_access
        try:
            deps.team_members_service.get_agency_my_access = lambda **kwargs: {"module_keys": ["settings", "settings_profile"]}
            with self.assertRaises(email_templates_api.HTTPException) as ctx:
                email_templates_api.list_agency_email_templates(user=user)
            self.assertEqual(ctx.exception.status_code, 403)
        finally:
            deps.team_members_service.get_agency_my_access = original

    def test_notifications_blocked_when_child_off(self):
        user = AuthUser(email="member@example.com", role="agency_member", user_id=22)
        original = deps.team_members_service.get_agency_my_access
        try:
            deps.team_members_service.get_agency_my_access = lambda **kwargs: {"module_keys": ["settings", "settings_profile"]}
            with self.assertRaises(email_notifications_api.HTTPException) as ctx:
                email_notifications_api.list_agency_email_notifications(user=user)
            self.assertEqual(ctx.exception.status_code, 403)
        finally:
            deps.team_members_service.get_agency_my_access = original

    def test_super_admin_bypass_navigation_enforcement(self):
        user = AuthUser(email="sa@example.com", role="super_admin")
        deps.enforce_agency_navigation_access(user=user, permission_key="settings_ai_agents")
        deps.enforce_subaccount_navigation_access(user=user, subaccount_id=7, permission_key="settings")

    def test_subaccount_settings_route_blocked_without_settings_key(self):
        user = AuthUser(email="sub@example.com", role="subaccount_user", user_id=91, allowed_subaccount_ids=(8,), access_scope="subaccount")
        original_access = deps.team_members_service.get_subaccount_my_access
        original_list = team_api.team_members_service.list_subaccount_members
        try:
            deps.team_members_service.get_subaccount_my_access = lambda **kwargs: {"module_keys": ["dashboard"]}
            team_api.team_members_service.list_subaccount_members = lambda **kwargs: ([], 0)
            with self.assertRaises(team_api.HTTPException) as ctx:
                team_api.list_subaccount_team_members(subaccount_id=8, search="", user_role="", page=1, page_size=10, user=user)
            self.assertEqual(ctx.exception.status_code, 403)
        finally:
            deps.team_members_service.get_subaccount_my_access = original_access
            team_api.team_members_service.list_subaccount_members = original_list

    def test_subaccount_settings_route_allowed_with_settings_key(self):
        user = AuthUser(email="sub@example.com", role="subaccount_user", user_id=91, allowed_subaccount_ids=(8,), access_scope="subaccount")
        original_access = deps.team_members_service.get_subaccount_my_access
        original_list = team_api.team_members_service.list_subaccount_members
        try:
            deps.team_members_service.get_subaccount_my_access = lambda **kwargs: {"module_keys": ["settings", "dashboard"]}
            team_api.team_members_service.list_subaccount_members = lambda **kwargs: ([], 0)
            payload = team_api.list_subaccount_team_members(subaccount_id=8, search="", user_role="", page=1, page_size=10, user=user)
            self.assertEqual(payload.total, 0)
        finally:
            deps.team_members_service.get_subaccount_my_access = original_access
            team_api.team_members_service.list_subaccount_members = original_list


if __name__ == "__main__":
    unittest.main()
