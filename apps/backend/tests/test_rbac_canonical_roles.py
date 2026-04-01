import unittest

from app.services.rbac import (
    AuthorizationError,
    normalize_role,
    require_action,
    require_permission,
)


class RbacCanonicalRolesTests(unittest.TestCase):
    def test_normalize_role_legacy_aliases(self):
        self.assertEqual(normalize_role("account_manager"), "subaccount_user")
        self.assertEqual(normalize_role("client_viewer"), "subaccount_viewer")
        self.assertEqual(normalize_role("agency_admin"), "agency_admin")
        self.assertEqual(normalize_role("super_admin"), "super_admin")
        self.assertEqual(normalize_role("agency_owner"), "agency_owner")

    def test_require_permission_on_canonical_roles(self):
        require_permission("agency_admin", "clients:create")
        require_permission("subaccount_user", "rules:write")
        with self.assertRaises(AuthorizationError):
            require_permission("agency_member", "clients:create")
        with self.assertRaises(AuthorizationError):
            require_permission("subaccount_user", "integrations:sync")

    def test_require_action_scope_checks_with_canonical_roles(self):
        require_action("agency_member", action="clients:list", scope="agency")
        require_action("subaccount_admin", action="integrations:sync", scope="subaccount")
        with self.assertRaises(AuthorizationError):
            require_action("agency_member", action="clients:create", scope="agency")
        with self.assertRaises(AuthorizationError):
            require_action("subaccount_user", action="integrations:sync", scope="subaccount")
        # subaccount_admin cannot use agency scope (role not allowed in scope 'agency')
        with self.assertRaises(AuthorizationError):
            require_action("subaccount_admin", action="clients:list", scope="agency")
        require_action("agency_admin", action="integrations:mailgun:config", scope="agency")
        with self.assertRaises(AuthorizationError):
            require_action("agency_member", action="integrations:mailgun:config", scope="agency")

    def test_subaccount_roles_can_use_clients_actions_in_subaccount_scope(self):
        # subaccount_admin can read client data in subaccount scope
        require_action("subaccount_admin", action="clients:list", scope="subaccount")
        # agency roles can also use clients:list in subaccount scope
        require_action("agency_owner", action="clients:list", scope="subaccount")
        require_action("agency_admin", action="clients:create", scope="subaccount")
        # subaccount_admin does NOT have clients:create permission
        with self.assertRaises(AuthorizationError):
            require_action("subaccount_admin", action="clients:create", scope="subaccount")
        # subaccount_viewer can read but not create
        require_action("subaccount_viewer", action="clients:list", scope="subaccount")
        with self.assertRaises(AuthorizationError):
            require_action("subaccount_viewer", action="clients:create", scope="subaccount")
        # subaccount roles cannot use agency scope
        with self.assertRaises(AuthorizationError):
            require_action("subaccount_admin", action="clients:create", scope="agency")

    def test_legacy_aliases_work_in_permission_and_action_checks(self):
        require_action("account_manager", action="rules:create", scope="subaccount")
        require_action("client_viewer", action="rules:list", scope="subaccount")
        with self.assertRaises(AuthorizationError):
            require_action("client_viewer", action="rules:create", scope="subaccount")


if __name__ == "__main__":
    unittest.main()
