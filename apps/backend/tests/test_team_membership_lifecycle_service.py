import unittest

from app.services.auth import AuthUser
from app.services.team_members import team_members_service


class _CursorTransition:
    def __init__(self):
        self.rowcount = 1
        self.updated_to = None

    def execute(self, query, params=None):
        sql = str(query)
        if "UPDATE user_memberships" in sql:
            self.updated_to = str(params[0])
            self.rowcount = 1
            return
        raise AssertionError(f"Unexpected SQL: {sql}")

    def fetchone(self):
        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _CursorMembershipSelect:
    def __init__(self, rows):
        self.rows = rows
        self._next_fetchone = None

    def execute(self, query, params=None):
        sql = str(query).lower()
        if "from user_memberships" not in sql:
            raise AssertionError(f"Unexpected SQL: {sql}")

        only_active = "status = 'active'" in sql
        user_id = int(params[0])
        if len(params) == 3:
            role_key = str(params[1])
            subaccount_id = int(params[2])
            filtered = [
                row for row in self.rows
                if int(row["user_id"]) == user_id
                and str(row["role_key"]) == role_key
                and int(row.get("subaccount_id") or 0) == subaccount_id
                and (not only_active or str(row.get("status") or "").lower() == "active")
            ]
        elif "subaccount_id" in sql:
            subaccount_id = int(params[1])
            filtered = [
                row for row in self.rows
                if int(row["user_id"]) == user_id
                and int(row.get("subaccount_id") or 0) == subaccount_id
                and (not only_active or str(row.get("status") or "").lower() == "active")
            ]
        else:
            raise AssertionError(f"Unexpected params for SQL: {params}")

        if filtered:
            first = filtered[0]
            self._next_fetchone = (first["id"], first["role_key"], first["scope_type"])
        else:
            self._next_fetchone = None

    def fetchone(self):
        return self._next_fetchone

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _Conn:
    def __init__(self, cursor):
        self._cursor = cursor
        self.committed = False

    def cursor(self):
        return self._cursor

    def commit(self):
        self.committed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class TeamMembershipLifecycleServiceTests(unittest.TestCase):
    def test_deactivate_membership_updates_status(self):
        original_get = team_members_service.get_membership_detail
        original_connect = team_members_service._connect
        cursor = _CursorTransition()
        try:
            team_members_service.get_membership_detail = lambda **kwargs: {
                "membership_id": 9,
                "is_inherited": False,
                "membership_status": "active",
            }
            team_members_service._connect = lambda: _Conn(cursor)
            actor = AuthUser(email="admin@example.com", role="agency_admin")
            result = team_members_service.deactivate_membership(membership_id=9, actor_user=actor)
            self.assertEqual(result["status"], "inactive")
            self.assertEqual(cursor.updated_to, "inactive")
        finally:
            team_members_service.get_membership_detail = original_get
            team_members_service._connect = original_connect

    def test_reactivate_membership_idempotent(self):
        original_get = team_members_service.get_membership_detail
        try:
            team_members_service.get_membership_detail = lambda **kwargs: {
                "membership_id": 9,
                "is_inherited": False,
                "membership_status": "active",
            }
            actor = AuthUser(email="admin@example.com", role="agency_admin")
            result = team_members_service.reactivate_membership(membership_id=9, actor_user=actor)
            self.assertEqual(result["status"], "active")
            self.assertIn("deja activ", result["message"])
        finally:
            team_members_service.get_membership_detail = original_get

    def test_transition_rejects_inherited_membership(self):
        original_get = team_members_service.get_membership_detail
        try:
            team_members_service.get_membership_detail = lambda **kwargs: {
                "membership_id": 9,
                "is_inherited": True,
                "membership_status": "active",
            }
            actor = AuthUser(email="subadmin@example.com", role="subaccount_admin", allowed_subaccount_ids=(4,), access_scope="subaccount")
            with self.assertRaisesRegex(RuntimeError, "moștenit"):
                team_members_service.deactivate_membership(membership_id=9, actor_user=actor)
        finally:
            team_members_service.get_membership_detail = original_get

    def test_grantable_modules_ignore_inactive_membership(self):
        original_connect = team_members_service._connect
        original_get_modules = team_members_service.get_membership_module_keys
        rows = [
            {"id": 41, "user_id": 33, "role_key": "subaccount_admin", "scope_type": "subaccount", "subaccount_id": 77, "status": "inactive"},
            {"id": 42, "user_id": 33, "role_key": "subaccount_admin", "scope_type": "subaccount", "subaccount_id": 77, "status": "active"},
        ]
        try:
            team_members_service._connect = lambda: _Conn(_CursorMembershipSelect(rows))
            team_members_service.get_membership_module_keys = lambda **kwargs: ["dashboard"] if int(kwargs["membership_id"]) == 42 else ["campaigns"]
            actor = AuthUser(email="subadmin@example.com", role="subaccount_admin", user_id=33)
            keys = team_members_service.get_grantable_module_keys_for_actor(actor_user=actor, subaccount_id=77)
            self.assertEqual(keys, {"dashboard"})
        finally:
            team_members_service._connect = original_connect
            team_members_service.get_membership_module_keys = original_get_modules

    def test_my_access_ignores_inactive_membership(self):
        original_connect = team_members_service._connect
        original_get_modules = team_members_service.get_membership_module_keys
        rows = [
            {"id": 51, "user_id": 44, "role_key": "subaccount_user", "scope_type": "subaccount", "subaccount_id": 88, "status": "inactive"},
            {"id": 52, "user_id": 44, "role_key": "subaccount_user", "scope_type": "subaccount", "subaccount_id": 88, "status": "active"},
        ]
        try:
            team_members_service._connect = lambda: _Conn(_CursorMembershipSelect(rows))
            team_members_service.get_membership_module_keys = lambda **kwargs: ["creative"] if int(kwargs["membership_id"]) == 52 else ["dashboard"]
            actor = AuthUser(email="member@example.com", role="subaccount_user", user_id=44, access_scope="subaccount")
            payload = team_members_service.get_subaccount_my_access(actor_user=actor, subaccount_id=88)
            self.assertEqual(payload["module_keys"], ["creative"])
        finally:
            team_members_service._connect = original_connect
            team_members_service.get_membership_module_keys = original_get_modules


if __name__ == "__main__":
    unittest.main()
