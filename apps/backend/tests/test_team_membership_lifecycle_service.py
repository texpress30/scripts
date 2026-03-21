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




class _CursorRemoveMembership:
    def __init__(self):
        self.rowcount = 0
        self.deleted_permissions_for = None
        self.deleted_membership_id = None

    def execute(self, query, params=None):
        sql = str(query)
        if "DELETE FROM membership_module_permissions" in sql:
            self.deleted_permissions_for = int(params[0])
            self.rowcount = 3
            return
        if "DELETE FROM user_memberships" in sql:
            self.deleted_membership_id = int(params[0])
            self.rowcount = 1
            return
        raise AssertionError(f"Unexpected SQL: {sql}")

    def fetchone(self):
        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _CursorDeleteUserHard:
    def __init__(self, *, user_exists: bool = True, memberships_count: int = 2):
        self.rowcount = 0
        self._next_fetchone = None
        self.user_exists = user_exists
        self.memberships_count = memberships_count
        self.deleted_team_members_email = None
        self.deleted_user_id = None

    def execute(self, query, params=None):
        sql = str(query)
        self.rowcount = 0
        if "SELECT email" in sql and "FROM users" in sql:
            if self.user_exists:
                self._next_fetchone = ("ana@example.com",)
            else:
                self._next_fetchone = None
            return
        if "SELECT COUNT(*)" in sql and "FROM user_memberships" in sql:
            self._next_fetchone = (self.memberships_count,)
            return
        if "DELETE FROM team_members" in sql:
            self.deleted_team_members_email = str(params[0])
            self.rowcount = 1
            return
        if "DELETE FROM users" in sql:
            self.deleted_user_id = int(params[0])
            self.rowcount = 1 if self.user_exists else 0
            return
        raise AssertionError(f"Unexpected SQL: {sql}")

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


    def test_remove_membership_success_deletes_membership_and_permissions(self):
        original_get = team_members_service.get_membership_detail
        original_connect = team_members_service._connect
        cursor = _CursorRemoveMembership()
        conn = _Conn(cursor)
        try:
            team_members_service.get_membership_detail = lambda **kwargs: {
                "membership_id": 75,
                "is_inherited": False,
            }
            team_members_service._connect = lambda: conn
            actor = AuthUser(email="admin@example.com", role="agency_admin", membership_id=1, membership_ids=(1,))
            result = team_members_service.remove_membership(membership_id=75, actor_user=actor)
            self.assertTrue(result["removed"])
            self.assertEqual(result["membership_id"], 75)
            self.assertEqual(cursor.deleted_permissions_for, 75)
            self.assertEqual(cursor.deleted_membership_id, 75)
            self.assertTrue(conn.committed)
        finally:
            team_members_service.get_membership_detail = original_get
            team_members_service._connect = original_connect

    def test_remove_membership_rejects_inherited_access(self):
        original_get = team_members_service.get_membership_detail
        try:
            team_members_service.get_membership_detail = lambda **kwargs: {
                "membership_id": 10,
                "is_inherited": True,
            }
            actor = AuthUser(email="subadmin@example.com", role="subaccount_admin", membership_id=2, membership_ids=(2,))
            with self.assertRaisesRegex(RuntimeError, "moștenit"):
                team_members_service.remove_membership(membership_id=10, actor_user=actor)
        finally:
            team_members_service.get_membership_detail = original_get

    def test_remove_membership_rejects_current_session_membership(self):
        original_get = team_members_service.get_membership_detail
        try:
            team_members_service.get_membership_detail = lambda **kwargs: {
                "membership_id": 33,
                "is_inherited": False,
            }
            actor = AuthUser(email="admin@example.com", role="agency_admin", membership_id=33, membership_ids=(33, 34))
            with self.assertRaisesRegex(RuntimeError, "propriul membership"):
                team_members_service.remove_membership(membership_id=33, actor_user=actor)
        finally:
            team_members_service.get_membership_detail = original_get

    def test_delete_user_hard_success_deletes_user_and_legacy_team_members(self):
        original_connect = team_members_service._connect
        cursor = _CursorDeleteUserHard(user_exists=True, memberships_count=3)
        conn = _Conn(cursor)
        try:
            team_members_service._connect = lambda: conn
            actor = AuthUser(email="admin@example.com", role="agency_admin", user_id=999)
            result = team_members_service.delete_user_hard(user_id=55, actor_user=actor)
            self.assertTrue(result["deleted"])
            self.assertEqual(result["user_id"], 55)
            self.assertEqual(result["deleted_memberships_count"], 3)
            self.assertEqual(cursor.deleted_team_members_email, "ana@example.com")
            self.assertEqual(cursor.deleted_user_id, 55)
            self.assertTrue(conn.committed)
        finally:
            team_members_service._connect = original_connect

    def test_delete_user_hard_blocks_self_delete(self):
        actor = AuthUser(email="admin@example.com", role="agency_admin", user_id=42)
        with self.assertRaisesRegex(RuntimeError, "propriul utilizator"):
            team_members_service.delete_user_hard(user_id=42, actor_user=actor)

    def test_delete_user_hard_missing_user_raises_lookup(self):
        original_connect = team_members_service._connect
        cursor = _CursorDeleteUserHard(user_exists=False, memberships_count=0)
        conn = _Conn(cursor)
        try:
            team_members_service._connect = lambda: conn
            actor = AuthUser(email="admin@example.com", role="agency_admin", user_id=9)
            with self.assertRaisesRegex(LookupError, "inexistent"):
                team_members_service.delete_user_hard(user_id=777, actor_user=actor)
        finally:
            team_members_service._connect = original_connect

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
