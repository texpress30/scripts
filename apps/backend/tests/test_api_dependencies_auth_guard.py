import unittest

from app.api import dependencies as deps
from app.services.auth import AuthError, AuthUser


class ApiDependenciesAuthGuardTests(unittest.TestCase):
    def test_get_current_user_rejects_deleted_db_user_token(self):
        original_decode = deps.decode_access_token
        original_is_active = deps.is_active_user_id
        try:
            deps.decode_access_token = lambda token: AuthUser(
                email="deleted@example.com",
                role="agency_member",
                user_id=88,
                is_env_admin=False,
            )
            deps.is_active_user_id = lambda user_id: False

            with self.assertRaises(deps.HTTPException) as ctx:
                deps.get_current_user(authorization="Bearer token-1")
            self.assertEqual(ctx.exception.status_code, 401)
        finally:
            deps.decode_access_token = original_decode
            deps.is_active_user_id = original_is_active

    def test_get_current_user_skips_db_check_for_env_admin_token(self):
        original_decode = deps.decode_access_token
        original_is_active = deps.is_active_user_id
        calls = {"count": 0}
        try:
            deps.decode_access_token = lambda token: AuthUser(
                email="admin@example.com",
                role="super_admin",
                user_id=None,
                is_env_admin=True,
            )

            def _is_active(_: int) -> bool:
                calls["count"] += 1
                return False

            deps.is_active_user_id = _is_active

            user = deps.get_current_user(authorization="Bearer token-2")
            self.assertTrue(user.is_env_admin)
            self.assertEqual(calls["count"], 0)
        finally:
            deps.decode_access_token = original_decode
            deps.is_active_user_id = original_is_active

    def test_get_current_user_invalid_token_still_rejected(self):
        original_decode = deps.decode_access_token
        try:
            deps.decode_access_token = lambda token: (_ for _ in ()).throw(AuthError("bad token"))
            with self.assertRaises(deps.HTTPException) as ctx:
                deps.get_current_user(authorization="Bearer broken")
            self.assertEqual(ctx.exception.status_code, 401)
        finally:
            deps.decode_access_token = original_decode


if __name__ == "__main__":
    unittest.main()
