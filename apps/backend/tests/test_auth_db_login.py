import unittest

from app.api import auth as auth_api
from app.schemas.auth import LoginRequest
from app.services import auth as auth_service
from app.services.auth import AuthLoginError, create_access_token, decode_access_token, hash_password


class _FakeCursor:
    def __init__(self, *, user_row, memberships):
        self.user_row = user_row
        self.memberships = memberships
        self.updated_last_login = False
        self._next_fetchone = None
        self._next_fetchall = []

    def execute(self, query, params=None):
        sql = str(query)
        if "FROM users" in sql and "WHERE LOWER(email)" in sql:
            self._next_fetchone = self.user_row
            return
        if "FROM user_memberships" in sql:
            user_id = params[0]
            role_key = params[1]
            self._next_fetchall = [m for m in self.memberships if int(m[4]) == int(user_id) and str(m[5]) == str(role_key)]
            return
        if "UPDATE users SET last_login_at" in sql:
            self.updated_last_login = True
            return

        raise AssertionError(f"Unexpected SQL: {sql}")

    def fetchone(self):
        return self._next_fetchone

    def fetchall(self):
        rows = self._next_fetchall
        self._next_fetchall = []
        return [(row[0], row[1], row[2], row[3]) for row in rows]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeConn:
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


class AuthDbLoginTests(unittest.TestCase):
    def test_login_db_success_agency_admin(self):
        password = "secret123"
        user_row = (11, "admin@example.com", hash_password(password), True)
        memberships = [
            (101, "agency", None, "", 11, "agency_admin"),
        ]
        cursor = _FakeCursor(user_row=user_row, memberships=memberships)
        original_connect = auth_service._connect
        try:
            auth_service._connect = lambda: _FakeConn(cursor)
            user = auth_service.authenticate_user_from_db(email="admin@example.com", password=password, requested_role="agency_admin")
            self.assertEqual(user.user_id, 11)
            self.assertEqual(user.role, "agency_admin")
            self.assertEqual(user.scope_type, "agency")
            self.assertEqual(user.membership_id, 101)
            self.assertTrue(cursor.updated_last_login)
        finally:
            auth_service._connect = original_connect

    def test_login_db_success_subaccount_user(self):
        password = "p@ss"
        user_row = (12, "member@example.com", hash_password(password), True)
        memberships = [
            (202, "subaccount", 55, "Client Z", 12, "subaccount_user"),
        ]
        cursor = _FakeCursor(user_row=user_row, memberships=memberships)
        original_connect = auth_service._connect
        try:
            auth_service._connect = lambda: _FakeConn(cursor)
            user = auth_service.authenticate_user_from_db(email="member@example.com", password=password, requested_role="subaccount_user")
            self.assertEqual(user.role, "subaccount_user")
            self.assertEqual(user.scope_type, "subaccount")
            self.assertEqual(user.subaccount_id, 55)
            self.assertEqual(user.subaccount_name, "Client Z")
        finally:
            auth_service._connect = original_connect

    def test_invalid_password(self):
        user_row = (13, "u@example.com", hash_password("good"), True)
        memberships = [(301, "agency", None, "", 13, "agency_admin")]
        cursor = _FakeCursor(user_row=user_row, memberships=memberships)
        original_connect = auth_service._connect
        try:
            auth_service._connect = lambda: _FakeConn(cursor)
            with self.assertRaises(AuthLoginError) as ctx:
                auth_service.authenticate_user_from_db(email="u@example.com", password="bad", requested_role="agency_admin")
            self.assertEqual(ctx.exception.status_code, 401)
        finally:
            auth_service._connect = original_connect

    def test_user_inactive(self):
        user_row = (14, "u@example.com", hash_password("good"), False)
        cursor = _FakeCursor(user_row=user_row, memberships=[])
        original_connect = auth_service._connect
        try:
            auth_service._connect = lambda: _FakeConn(cursor)
            with self.assertRaises(AuthLoginError) as ctx:
                auth_service.authenticate_user_from_db(email="u@example.com", password="good", requested_role="agency_admin")
            self.assertEqual(ctx.exception.status_code, 403)
        finally:
            auth_service._connect = original_connect

    def test_user_without_membership_for_role(self):
        user_row = (15, "u@example.com", hash_password("good"), True)
        memberships = [(401, "agency", None, "", 15, "agency_member")]
        cursor = _FakeCursor(user_row=user_row, memberships=memberships)
        original_connect = auth_service._connect
        try:
            auth_service._connect = lambda: _FakeConn(cursor)
            with self.assertRaises(AuthLoginError) as ctx:
                auth_service.authenticate_user_from_db(email="u@example.com", password="good", requested_role="agency_admin")
            self.assertEqual(ctx.exception.status_code, 403)
        finally:
            auth_service._connect = original_connect

    def test_legacy_alias_role_normalization(self):
        user_row = (16, "u@example.com", hash_password("good"), True)
        memberships = [(501, "subaccount", 7, "Client A", 16, "subaccount_user")]
        cursor = _FakeCursor(user_row=user_row, memberships=memberships)
        original_connect = auth_service._connect
        try:
            auth_service._connect = lambda: _FakeConn(cursor)
            user = auth_service.authenticate_user_from_db(email="u@example.com", password="good", requested_role="account_manager")
            self.assertEqual(user.role, "subaccount_user")
            self.assertEqual(user.membership_id, 501)
        finally:
            auth_service._connect = original_connect

    def test_ambiguous_membership_returns_409(self):
        user_row = (17, "u@example.com", hash_password("good"), True)
        memberships = [
            (601, "subaccount", 9, "Client A", 17, "subaccount_user"),
            (602, "subaccount", 10, "Client B", 17, "subaccount_user"),
        ]
        cursor = _FakeCursor(user_row=user_row, memberships=memberships)
        original_connect = auth_service._connect
        try:
            auth_service._connect = lambda: _FakeConn(cursor)
            with self.assertRaises(AuthLoginError) as ctx:
                auth_service.authenticate_user_from_db(email="u@example.com", password="good", requested_role="subaccount_user")
            self.assertEqual(ctx.exception.status_code, 409)
        finally:
            auth_service._connect = original_connect

    def test_env_fallback_admin_login(self):
        original_auth = auth_api.authenticate_user_from_db
        original_env_validate = auth_api.validate_login_credentials
        original_rate = auth_api.rate_limiter_service.check
        try:
            auth_api.authenticate_user_from_db = lambda **kwargs: (_ for _ in ()).throw(
                AuthLoginError(status_code=401, message="Invalid email or password", reason="invalid_credentials")
            )
            auth_api.validate_login_credentials = lambda email, password: True
            auth_api.rate_limiter_service.check = lambda *args, **kwargs: None
            resp = auth_api.login(LoginRequest(email="admin@example.com", password="ok", role="subaccount_user"))
            decoded = decode_access_token(resp.access_token)
            self.assertEqual(decoded.role, "super_admin")
            self.assertTrue(decoded.is_env_admin)
        finally:
            auth_api.authenticate_user_from_db = original_auth
            auth_api.validate_login_credentials = original_env_validate
            auth_api.rate_limiter_service.check = original_rate

    def test_decode_old_and_new_token_payloads(self):
        old_token = create_access_token(email="old@example.com", role="agency_admin")
        old_user = decode_access_token(old_token)
        self.assertEqual(old_user.email, "old@example.com")
        self.assertEqual(old_user.role, "agency_admin")
        self.assertIsNone(old_user.membership_id)

        new_token = create_access_token(
            email="new@example.com",
            role="subaccount_user",
            user_id=99,
            scope_type="subaccount",
            membership_id=777,
            subaccount_id=8,
            subaccount_name="Client New",
            is_env_admin=False,
        )
        new_user = decode_access_token(new_token)
        self.assertEqual(new_user.user_id, 99)
        self.assertEqual(new_user.membership_id, 777)
        self.assertEqual(new_user.subaccount_id, 8)
        self.assertEqual(new_user.subaccount_name, "Client New")


if __name__ == "__main__":
    unittest.main()
