import unittest

from app.api import team as team_api
from app.services.auth import AuthUser


class TeamMembershipEditApiTests(unittest.TestCase):
    def test_get_membership_detail_direct_ok(self):
        user = AuthUser(email="admin@example.com", role="agency_admin")
        original = team_api.team_members_service.get_membership_detail
        try:
            team_api.team_members_service.get_membership_detail = lambda **kwargs: {
                "membership_id": 41,
                "user_id": 8,
                "scope_type": "subaccount",
                "subaccount_id": 12,
                "subaccount_name": "Client 12",
                "role_key": "subaccount_user",
                "role_label": "Subaccount User",
                "module_keys": ["dashboard", "rules"],
                "source_scope": "subaccount",
                "is_inherited": False,
                "membership_status": "active",
                "first_name": "Ana",
                "last_name": "Pop",
                "email": "ana@example.com",
                "phone": "",
                "extension": "",
            }
            resp = team_api.get_team_membership_detail(membership_id=41, user=user)
            self.assertEqual(resp.item.membership_id, 41)
            self.assertEqual(resp.item.module_keys, ["dashboard", "rules"])
            self.assertFalse(resp.item.is_inherited)
            self.assertEqual(resp.item.membership_status, "active")
        finally:
            team_api.team_members_service.get_membership_detail = original

    def test_get_membership_detail_inaccessible_forbidden(self):
        user = AuthUser(email="admin@example.com", role="agency_admin")
        original = team_api.team_members_service.get_membership_detail
        try:
            team_api.team_members_service.get_membership_detail = lambda **kwargs: (_ for _ in ()).throw(PermissionError("Nu ai acces la acest membership"))
            with self.assertRaises(team_api.HTTPException) as ctx:
                team_api.get_team_membership_detail(membership_id=41, user=user)
            self.assertEqual(ctx.exception.status_code, 403)
        finally:
            team_api.team_members_service.get_membership_detail = original

    def test_patch_agency_role_change_valid(self):
        user = AuthUser(email="admin@example.com", role="agency_admin")
        original = team_api.team_members_service.update_membership
        try:
            team_api.team_members_service.update_membership = lambda **kwargs: {
                "membership_id": 50,
                "user_id": 9,
                "scope_type": "agency",
                "subaccount_id": None,
                "subaccount_name": "Toate",
                "role_key": "agency_viewer",
                "role_label": "Agency Viewer",
                "module_keys": [],
                "source_scope": "agency",
                "is_inherited": False,
                "membership_status": "active",
                "first_name": "Mara",
                "last_name": "I",
                "email": "mara@example.com",
                "phone": "",
                "extension": "",
            }
            payload = team_api.UpdateTeamMembershipRequest(user_role="agency_viewer")
            resp = team_api.patch_team_membership(membership_id=50, payload=payload, user=user)
            self.assertEqual(resp.item.role_key, "agency_viewer")
        finally:
            team_api.team_members_service.update_membership = original

    def test_patch_agency_with_module_keys_valid(self):
        user = AuthUser(email="admin@example.com", role="agency_admin")
        original = team_api.team_members_service.update_membership
        try:
            team_api.team_members_service.update_membership = lambda **kwargs: {
                "membership_id": 51,
                "user_id": 9,
                "scope_type": "agency",
                "subaccount_id": None,
                "subaccount_name": "Toate",
                "role_key": "agency_member",
                "role_label": "Agency Member",
                "module_keys": ["agency_dashboard", "settings", "settings_my_team"],
                "source_scope": "agency",
                "is_inherited": False,
                "membership_status": "active",
                "first_name": "Mara",
                "last_name": "I",
                "email": "mara@example.com",
                "phone": "",
                "extension": "",
            }
            payload = team_api.UpdateTeamMembershipRequest(user_role="agency_member", module_keys=["agency_dashboard", "settings", "settings_my_team"])
            resp = team_api.patch_team_membership(membership_id=51, payload=payload, user=user)
            self.assertEqual(resp.item.module_keys, ["agency_dashboard", "settings", "settings_my_team"])
        finally:
            team_api.team_members_service.update_membership = original

    def test_patch_subaccount_role_change_valid(self):
        user = AuthUser(email="admin@example.com", role="agency_admin")
        original = team_api.team_members_service.update_membership
        try:
            team_api.team_members_service.update_membership = lambda **kwargs: {
                "membership_id": 60,
                "user_id": 14,
                "scope_type": "subaccount",
                "subaccount_id": 7,
                "subaccount_name": "Client 7",
                "role_key": "subaccount_admin",
                "role_label": "Subaccount Admin",
                "module_keys": ["dashboard", "campaigns", "rules", "creative", "recommendations"],
                "source_scope": "subaccount",
                "is_inherited": False,
                "membership_status": "active",
                "first_name": "Ioan",
                "last_name": "D",
                "email": "ioan@example.com",
                "phone": "",
                "extension": "",
            }
            payload = team_api.UpdateTeamMembershipRequest(user_role="subaccount_admin")
            resp = team_api.patch_team_membership(membership_id=60, payload=payload, user=user)
            self.assertEqual(resp.item.scope_type, "subaccount")
            self.assertEqual(resp.item.role_key, "subaccount_admin")
        finally:
            team_api.team_members_service.update_membership = original

    def test_patch_subaccount_module_update_valid(self):
        user = AuthUser(email="admin@example.com", role="agency_admin")
        original = team_api.team_members_service.update_membership
        captured = {}
        try:
            def _fake_update(**kwargs):
                captured.update(kwargs)
                return {
                    "membership_id": 61,
                    "user_id": 15,
                    "scope_type": "subaccount",
                    "subaccount_id": 7,
                    "subaccount_name": "Client 7",
                    "role_key": "subaccount_user",
                    "role_label": "Subaccount User",
                    "module_keys": ["dashboard", "creative"],
                    "source_scope": "subaccount",
                    "is_inherited": False,
                    "membership_status": "active",
                    "first_name": "Elena",
                    "last_name": "G",
                    "email": "elena@example.com",
                    "phone": "",
                    "extension": "",
                }
            team_api.team_members_service.update_membership = _fake_update
            payload = team_api.UpdateTeamMembershipRequest(module_keys=["dashboard", "creative"])
            resp = team_api.patch_team_membership(membership_id=61, payload=payload, user=user)
            self.assertEqual(resp.item.module_keys, ["dashboard", "creative"])
            self.assertEqual(captured["module_keys"], ["dashboard", "creative"])
        finally:
            team_api.team_members_service.update_membership = original

    def test_patch_invalid_module_keys_rejected(self):
        user = AuthUser(email="admin@example.com", role="agency_admin")
        original = team_api.team_members_service.update_membership
        try:
            team_api.team_members_service.update_membership = lambda **kwargs: (_ for _ in ()).throw(ValueError("Modul invalid: invalid_key"))
            payload = team_api.UpdateTeamMembershipRequest(module_keys=["invalid_key"])
            with self.assertRaises(team_api.HTTPException) as ctx:
                team_api.patch_team_membership(membership_id=61, payload=payload, user=user)
            self.assertEqual(ctx.exception.status_code, 400)
        finally:
            team_api.team_members_service.update_membership = original

    def test_patch_empty_module_list_rejected(self):
        user = AuthUser(email="admin@example.com", role="agency_admin")
        original = team_api.team_members_service.update_membership
        try:
            team_api.team_members_service.update_membership = lambda **kwargs: (_ for _ in ()).throw(ValueError("Selectează cel puțin o cheie de navigare"))
            payload = team_api.UpdateTeamMembershipRequest(module_keys=[])
            with self.assertRaises(team_api.HTTPException) as ctx:
                team_api.patch_team_membership(membership_id=61, payload=payload, user=user)
            self.assertEqual(ctx.exception.status_code, 400)
        finally:
            team_api.team_members_service.update_membership = original

    def test_patch_grant_ceiling_violation_rejected(self):
        user = AuthUser(email="sub-admin@example.com", role="subaccount_admin", allowed_subaccount_ids=(7,), access_scope="subaccount")
        original = team_api.team_members_service.update_membership
        try:
            team_api.team_members_service.update_membership = lambda **kwargs: (_ for _ in ()).throw(PermissionError("Nu poți acorda module în afara permisiunilor proprii: campaigns"))
            payload = team_api.UpdateTeamMembershipRequest(module_keys=["dashboard", "campaigns"])
            with self.assertRaises(team_api.HTTPException) as ctx:
                team_api.patch_team_membership(membership_id=62, payload=payload, user=user)
            self.assertEqual(ctx.exception.status_code, 403)
        finally:
            team_api.team_members_service.update_membership = original

    def test_patch_inherited_access_rejected(self):
        user = AuthUser(email="sub-admin@example.com", role="subaccount_admin", allowed_subaccount_ids=(7,), access_scope="subaccount")
        original = team_api.team_members_service.update_membership
        try:
            team_api.team_members_service.update_membership = lambda **kwargs: (_ for _ in ()).throw(RuntimeError("Access moștenit: acest membership nu poate fi editat local"))
            payload = team_api.UpdateTeamMembershipRequest(user_role="subaccount_user")
            with self.assertRaises(team_api.HTTPException) as ctx:
                team_api.patch_team_membership(membership_id=63, payload=payload, user=user)
            self.assertEqual(ctx.exception.status_code, 409)
        finally:
            team_api.team_members_service.update_membership = original

    def test_subaccount_user_cannot_edit_memberships(self):
        user = AuthUser(email="sub-user@example.com", role="subaccount_user", allowed_subaccount_ids=(7,), access_scope="subaccount")
        payload = team_api.UpdateTeamMembershipRequest(user_role="subaccount_user")
        with self.assertRaises(team_api.HTTPException) as ctx:
            team_api.patch_team_membership(membership_id=63, payload=payload, user=user)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_deactivate_membership_success(self):
        user = AuthUser(email="admin@example.com", role="agency_admin")
        original = team_api.team_members_service.deactivate_membership
        try:
            team_api.team_members_service.deactivate_membership = lambda **kwargs: {
                "membership_id": 99,
                "status": "inactive",
                "message": "Membership dezactivat",
            }
            resp = team_api.deactivate_team_membership(membership_id=99, user=user)
            self.assertEqual(resp.membership_id, 99)
            self.assertEqual(resp.status, "inactive")
        finally:
            team_api.team_members_service.deactivate_membership = original

    def test_reactivate_membership_idempotent_success(self):
        user = AuthUser(email="admin@example.com", role="agency_admin")
        original = team_api.team_members_service.reactivate_membership
        try:
            team_api.team_members_service.reactivate_membership = lambda **kwargs: {
                "membership_id": 99,
                "status": "active",
                "message": "Membership-ul este deja activ",
            }
            resp = team_api.reactivate_team_membership(membership_id=99, user=user)
            self.assertEqual(resp.membership_id, 99)
            self.assertEqual(resp.status, "active")
            self.assertIn("deja activ", resp.message)
        finally:
            team_api.team_members_service.reactivate_membership = original

    def test_deactivate_inherited_conflict(self):
        user = AuthUser(email="sub-admin@example.com", role="subaccount_admin", allowed_subaccount_ids=(7,), access_scope="subaccount")
        original = team_api.team_members_service.deactivate_membership
        try:
            team_api.team_members_service.deactivate_membership = lambda **kwargs: (_ for _ in ()).throw(RuntimeError("Access moștenit: acest membership nu poate fi modificat local"))
            with self.assertRaises(team_api.HTTPException) as ctx:
                team_api.deactivate_team_membership(membership_id=63, user=user)
            self.assertEqual(ctx.exception.status_code, 409)
        finally:
            team_api.team_members_service.deactivate_membership = original


    def test_remove_membership_success(self):
        user = AuthUser(email="admin@example.com", role="agency_admin")
        original = team_api.team_members_service.remove_membership
        try:
            team_api.team_members_service.remove_membership = lambda **kwargs: {
                "membership_id": 144,
                "removed": True,
                "message": "Membership eliminat",
            }
            resp = team_api.remove_team_membership(membership_id=144, user=user)
            self.assertEqual(resp.membership_id, 144)
            self.assertTrue(resp.removed)
            self.assertEqual(resp.message, "Membership eliminat")
        finally:
            team_api.team_members_service.remove_membership = original

    def test_remove_membership_inherited_conflict(self):
        user = AuthUser(email="sub-admin@example.com", role="subaccount_admin", allowed_subaccount_ids=(7,), access_scope="subaccount")
        original = team_api.team_members_service.remove_membership
        try:
            team_api.team_members_service.remove_membership = lambda **kwargs: (_ for _ in ()).throw(RuntimeError("Access moștenit: acest membership nu poate fi eliminat local"))
            with self.assertRaises(team_api.HTTPException) as ctx:
                team_api.remove_team_membership(membership_id=63, user=user)
            self.assertEqual(ctx.exception.status_code, 409)
        finally:
            team_api.team_members_service.remove_membership = original

    def test_remove_membership_self_conflict(self):
        user = AuthUser(email="admin@example.com", role="agency_admin")
        original = team_api.team_members_service.remove_membership
        try:
            team_api.team_members_service.remove_membership = lambda **kwargs: (_ for _ in ()).throw(RuntimeError("Nu îți poți elimina propriul membership din sesiunea curentă"))
            with self.assertRaises(team_api.HTTPException) as ctx:
                team_api.remove_team_membership(membership_id=101, user=user)
            self.assertEqual(ctx.exception.status_code, 409)
        finally:
            team_api.team_members_service.remove_membership = original


    def test_get_membership_detail_returns_404_after_remove(self):
        user = AuthUser(email="admin@example.com", role="agency_admin")
        original_get = team_api.team_members_service.get_membership_detail
        original_remove = team_api.team_members_service.remove_membership
        state = {"exists": True}
        try:
            def _get(**kwargs):
                if not state["exists"]:
                    return None
                return {
                    "membership_id": 77,
                    "user_id": 8,
                    "scope_type": "subaccount",
                    "subaccount_id": 12,
                    "subaccount_name": "Client 12",
                    "role_key": "subaccount_user",
                    "role_label": "Subaccount User",
                    "module_keys": ["dashboard"],
                    "source_scope": "subaccount",
                    "is_inherited": False,
                    "membership_status": "active",
                    "first_name": "Ana",
                    "last_name": "Pop",
                    "email": "ana@example.com",
                    "phone": "",
                    "extension": "",
                }

            def _remove(**kwargs):
                state["exists"] = False
                return {"membership_id": 77, "removed": True, "message": "Membership eliminat"}

            team_api.team_members_service.get_membership_detail = _get
            team_api.team_members_service.remove_membership = _remove
            team_api.remove_team_membership(membership_id=77, user=user)
            with self.assertRaises(team_api.HTTPException) as ctx:
                team_api.get_team_membership_detail(membership_id=77, user=user)
            self.assertEqual(ctx.exception.status_code, 404)
        finally:
            team_api.team_members_service.get_membership_detail = original_get
            team_api.team_members_service.remove_membership = original_remove

    def test_subaccount_user_cannot_deactivate_memberships(self):
        user = AuthUser(email="sub-user@example.com", role="subaccount_user", allowed_subaccount_ids=(7,), access_scope="subaccount")
        with self.assertRaises(team_api.HTTPException) as ctx:
            team_api.deactivate_team_membership(membership_id=63, user=user)
        self.assertEqual(ctx.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
