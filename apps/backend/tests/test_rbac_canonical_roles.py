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
        with self.assertRaises(AuthorizationError):
            require_action("subaccount_admin", action="clients:list", scope="agency")

    def test_legacy_aliases_work_in_permission_and_action_checks(self):
        require_action("account_manager", action="rules:create", scope="subaccount")
        require_action("client_viewer", action="rules:list", scope="subaccount")
        with self.assertRaises(AuthorizationError):
            require_action("client_viewer", action="rules:create", scope="subaccount")


if __name__ == "__main__":
    unittest.main()
