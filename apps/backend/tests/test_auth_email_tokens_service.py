import unittest
from datetime import datetime, timedelta, timezone

from app.services import auth as auth_service
from app.services import auth_email_tokens as token_module
from app.services.auth_email_tokens import AuthEmailTokenError


class _TokensCursor:
    def __init__(self, state):
        self.state = state
        self._fetchone = None
        self.rowcount = 0

    def execute(self, query, params=None):
        sql = str(query)
        self.rowcount = 0
        if "INSERT INTO auth_email_tokens" in sql:
            self.state["token_id"] += 1
            self.state["tokens"].append(
                {
                    "id": self.state["token_id"],
                    "user_id": int(params[0]),
                    "token_type": str(params[1]),
                    "token_hash": str(params[2]),
                    "email": str(params[3]),
                    "expires_at": params[4],
                    "consumed_at": None,
                    "metadata_json": "{}",
                }
            )
            self.rowcount = 1
            return

        if "SELECT id, user_id, email, token_type, expires_at, consumed_at, metadata_json" in sql:
            token_hash = str(params[0])
            token_types = [str(item) for item in (params[1] or [])]
            match = None
            for row in reversed(self.state["tokens"]):
                if row["token_hash"] == token_hash and row["token_type"] in token_types:
                    match = row
                    break
            if match is None:
                self._fetchone = None
            else:
                self._fetchone = (
                    match["id"],
                    match["user_id"],
                    match["email"],
                    match["token_type"],
                    match["expires_at"],
                    match["consumed_at"],
                    match["metadata_json"],
                )
            return

        if "UPDATE auth_email_tokens" in sql and "id = %s" in sql:
            token_id = int(params[0])
            for row in self.state["tokens"]:
                if row["id"] == token_id and row["consumed_at"] is None:
                    row["consumed_at"] = datetime.now(tz=timezone.utc)
                    self.rowcount = 1
                    return
            self.rowcount = 0
            return

        if "UPDATE auth_email_tokens" in sql and "user_id = %s" in sql:
            user_id = int(params[0])
            token_type = str(params[1])
            exclude = int(params[2]) if len(params or ()) > 2 else None
            now = datetime.now(tz=timezone.utc)
            for row in self.state["tokens"]:
                if row["user_id"] != user_id or row["token_type"] != token_type:
                    continue
                if row["consumed_at"] is not None:
                    continue
                if row["expires_at"] <= now:
                    continue
                if exclude is not None and row["id"] == exclude:
                    continue
                row["consumed_at"] = now
                self.rowcount += 1
            return

        if "SELECT id, email, password_hash, is_active" in sql:
            user = self.state["user"]
            self._fetchone = (user["id"], user["email"], user["password_hash"], user["is_active"])
            return

        if "FROM user_memberships" in sql:
            req_user_id = int(params[0])
            req_role = str(params[1])
            rows = []
            for m in self.state["memberships"]:
                if int(m[4]) == req_user_id and str(m[5]) == req_role:
                    rows.append((m[0], m[1], m[2], m[3]))
            self.state["membership_rows"] = rows
            return

        if "UPDATE users" in sql and "password_hash" in sql:
            self.state["user"]["password_hash"] = str(params[0])
            self.state["user"]["must_reset_password"] = False
            self.rowcount = 1
            return

        if "UPDATE users SET last_login_at" in sql:
            self.rowcount = 1
            return

        raise AssertionError(f"Unexpected SQL in test: {sql}")

    def fetchone(self):
        return self._fetchone

    def fetchall(self):
        rows = self.state.get("membership_rows", [])
        self.state["membership_rows"] = []
        return rows

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _TokensConn:
    def __init__(self, state):
        self._state = state

    def cursor(self):
        return _TokensCursor(self._state)

    def commit(self):
        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class AuthEmailTokensServiceTests(unittest.TestCase):
    def test_token_raw_not_stored_and_can_be_consumed(self):
        state = {"token_id": 0, "tokens": [], "user": {"id": 1, "email": "u@example.com", "password_hash": "", "is_active": True}, "memberships": []}
        service = token_module.AuthEmailTokensService()
        service._schema_initialized = True

        original_connect = service._connect
        try:
            service._connect = lambda: _TokensConn(state)
            raw, _ = service.create_password_reset_token_for_existing_user(user_id=1, email="u@example.com", expires_in_minutes=60)
            self.assertEqual(len(state["tokens"]), 1)
            stored_hash = state["tokens"][0]["token_hash"]
            self.assertNotEqual(stored_hash, raw)
            self.assertEqual(stored_hash, service.debug_get_token_hash_for_raw(raw_token=raw))

            validated = service.validate_password_reset_token(raw_token=raw)
            self.assertEqual(validated.user_id, 1)

            consumed = service.consume_password_reset_token(raw_token=raw)
            self.assertEqual(consumed.user_id, 1)

            with self.assertRaises(AuthEmailTokenError):
                service.consume_password_reset_token(raw_token=raw)
        finally:
            service._connect = original_connect

    def test_expired_and_invalid_tokens_fail_validation(self):
        state = {"token_id": 0, "tokens": [], "user": {"id": 1, "email": "u@example.com", "password_hash": "", "is_active": True}, "memberships": []}
        service = token_module.AuthEmailTokensService()
        service._schema_initialized = True
        original_connect = service._connect
        try:
            service._connect = lambda: _TokensConn(state)
            raw, _ = service.create_password_reset_token(user_id=1, email="u@example.com", expires_in_minutes=60)
            state["tokens"][0]["expires_at"] = datetime.now(tz=timezone.utc) - timedelta(minutes=1)

            with self.assertRaises(AuthEmailTokenError) as expired_ctx:
                service.validate_password_reset_token(raw_token=raw)
            self.assertEqual(expired_ctx.exception.reason, "token_expired")

            with self.assertRaises(AuthEmailTokenError) as invalid_ctx:
                service.validate_password_reset_token(raw_token="missing")
            self.assertEqual(invalid_ctx.exception.reason, "invalid_token")
        finally:
            service._connect = original_connect

    def test_invite_user_token_is_hash_only_and_valid_for_reset_confirm(self):
        state = {"token_id": 0, "tokens": [], "user": {"id": 3, "email": "invitee@example.com", "password_hash": "", "is_active": True}, "memberships": []}
        service = token_module.AuthEmailTokensService()
        service._schema_initialized = True

        original_connect = service._connect
        try:
            service._connect = lambda: _TokensConn(state)
            raw, _ = service.create_user_invite_token_for_existing_user(user_id=3, email="invitee@example.com", expires_in_minutes=60)
            stored_hash = state["tokens"][0]["token_hash"]
            self.assertNotEqual(stored_hash, raw)
            self.assertEqual(state["tokens"][0]["token_type"], "invite_user")

            validated = service.validate_reset_or_invite_token(raw_token=raw)
            self.assertEqual(validated.token_type, "invite_user")
            consumed = service.consume_reset_or_invite_token(raw_token=raw)
            self.assertEqual(consumed.token_type, "invite_user")
        finally:
            service._connect = original_connect

    def test_set_user_password_makes_new_login_work_and_old_fail(self):
        state = {
            "token_id": 0,
            "tokens": [],
            "user": {"id": 22, "email": "u@example.com", "password_hash": auth_service.hash_password("old-password"), "is_active": True, "must_reset_password": True},
            "memberships": [(101, "agency", None, "", 22, "agency_admin")],
            "membership_rows": [],
        }
        original_connect = auth_service._connect
        try:
            auth_service._connect = lambda: _TokensConn(state)
            auth_service.set_user_password(user_id=22, new_password="new-password-123")

            with self.assertRaises(auth_service.AuthLoginError):
                auth_service.authenticate_user_from_db(email="u@example.com", password="old-password", requested_role="agency_admin")

            user = auth_service.authenticate_user_from_db(email="u@example.com", password="new-password-123", requested_role="agency_admin")
            self.assertEqual(user.role, "agency_admin")
        finally:
            auth_service._connect = original_connect


if __name__ == "__main__":
    unittest.main()
