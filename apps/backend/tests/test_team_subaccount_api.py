import unittest

from app.api import dependencies as deps
from app.api import team as team_api
from app.services.auth import AuthUser


class TeamSubaccountApiTests(unittest.TestCase):
    def test_subaccount_scoped_user_own_subaccount_ok(self):
        user = AuthUser(email="u@example.com", role="subaccount_user", subaccount_id=12)
        deps.enforce_subaccount_action(user=user, action="team:subaccount:list", subaccount_id=12)

    def test_subaccount_scoped_user_allowed_subaccount_list_ok(self):
        user = AuthUser(email="u@example.com", role="subaccount_user", allowed_subaccount_ids=(12, 13), access_scope="subaccount")
        deps.enforce_subaccount_action(user=user, action="team:subaccount:list", subaccount_id=13)

    def test_subaccount_scoped_user_other_subaccount_forbidden(self):
        user = AuthUser(email="u@example.com", role="subaccount_user", subaccount_id=12)
        with self.assertRaises(deps.HTTPException) as ctx:
            deps.enforce_subaccount_action(user=user, action="team:subaccount:list", subaccount_id=99)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_subaccount_scoped_user_not_in_allowed_list_forbidden(self):
        user = AuthUser(email="u@example.com", role="subaccount_user", allowed_subaccount_ids=(12, 13), access_scope="subaccount")
        with self.assertRaises(deps.HTTPException) as ctx:
            deps.enforce_subaccount_action(user=user, action="team:subaccount:list", subaccount_id=99)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_agency_role_can_access_any_subaccount(self):
        user = AuthUser(email="admin@example.com", role="agency_admin")
        deps.enforce_subaccount_action(user=user, action="team:subaccount:list", subaccount_id=77)

    def test_list_subaccount_members_endpoint(self):
        user = AuthUser(email="admin@example.com", role="agency_admin")
        original = team_api.team_members_service.list_subaccount_members
        try:
            team_api.team_members_service.list_subaccount_members = lambda **kwargs: (
                [
                    {
                        "membership_id": 1,
                        "user_id": 4,
                        "display_id": "TM-1",
                        "first_name": "Ana",
                        "last_name": "Ionescu",
                        "email": "ana@example.com",
                        "phone": "",
                        "extension": "",
                        "role_key": "subaccount_user",
                        "role_label": "Subaccount User",
                        "source_scope": "subaccount",
                        "source_label": "Client A",
                        "is_active": True,
                        "is_inherited": False,
                    }
                ],
                1,
            )
            resp = team_api.list_subaccount_team_members(subaccount_id=8, search="", user_role="", page=1, page_size=10, user=user)
            self.assertEqual(resp.total, 1)
            self.assertEqual(resp.items[0].role_key, "subaccount_user")
        finally:
            team_api.team_members_service.list_subaccount_members = original

    def test_create_subaccount_member_default_role(self):
        user = AuthUser(email="admin@example.com", role="agency_admin")
        original = team_api.team_members_service.create_subaccount_member
        try:
            def _fake_create(**kwargs):
                self.assertEqual(kwargs["user_role"], "subaccount_user")
                return {
                    "membership_id": 11,
                    "user_id": 5,
                    "display_id": "TM-11",
                    "first_name": "Ion",
                    "last_name": "Pop",
                    "email": "ion@example.com",
                    "phone": "",
                    "extension": "",
                    "role_key": "subaccount_user",
                    "role_label": "Subaccount User",
                    "source_scope": "subaccount",
                    "source_label": "Client B",
                    "is_active": True,
                    "is_inherited": False,
                }

            team_api.team_members_service.create_subaccount_member = _fake_create
            payload = team_api.CreateSubaccountTeamMemberRequest(
                first_name="Ion",
                last_name="Pop",
                email="ion@example.com",
            )
            resp = team_api.create_subaccount_team_member(subaccount_id=9, payload=payload, user=user)
            self.assertEqual(resp.item.membership_id, 11)
        finally:
            team_api.team_members_service.create_subaccount_member = original

    def test_create_subaccount_member_invalid_role_rejected(self):
        user = AuthUser(email="admin@example.com", role="agency_admin")
        original = team_api.team_members_service.create_subaccount_member
        try:
            team_api.team_members_service.create_subaccount_member = lambda **kwargs: (_ for _ in ()).throw(
                ValueError("Rol invalid pentru endpointul de sub-account")
            )
            payload = team_api.CreateSubaccountTeamMemberRequest(
                first_name="Ion",
                last_name="Pop",
                email="ion@example.com",
                user_role="agency_member",
            )
            with self.assertRaises(team_api.HTTPException) as ctx:
                team_api.create_subaccount_team_member(subaccount_id=9, payload=payload, user=user)
            self.assertEqual(ctx.exception.status_code, 400)
        finally:
            team_api.team_members_service.create_subaccount_member = original

    def test_create_subaccount_member_subaccount_not_found(self):
        user = AuthUser(email="admin@example.com", role="agency_admin")
        original = team_api.team_members_service.create_subaccount_member
        try:
            team_api.team_members_service.create_subaccount_member = lambda **kwargs: (_ for _ in ()).throw(
                ValueError("Sub-account inexistent")
            )
            payload = team_api.CreateSubaccountTeamMemberRequest(
                first_name="Ion",
                last_name="Pop",
                email="ion@example.com",
            )
            with self.assertRaises(team_api.HTTPException) as ctx:
                team_api.create_subaccount_team_member(subaccount_id=999, payload=payload, user=user)
            self.assertEqual(ctx.exception.status_code, 404)
        finally:
            team_api.team_members_service.create_subaccount_member = original

    def test_duplicate_membership_no_crash(self):
        service = team_api.team_members_service
        original_resolve = service._resolve_subaccount_by_id
        original_upsert_user = service._upsert_user
        original_upsert_membership = service._upsert_membership
        original_set_modules = service.set_membership_module_keys
        try:
            service._resolve_subaccount_by_id = lambda **kwargs: type("_S", (), {"id": 10, "name": "Client X"})()
            service._upsert_user = lambda **kwargs: 20
            service._upsert_membership = lambda **kwargs: 500  # existing membership id reused
            service.set_membership_module_keys = lambda **kwargs: None
            item = service.create_subaccount_member(
                subaccount_id=10,
                first_name="Ana",
                last_name="D",
                email="ANA@EXAMPLE.COM",
                phone="",
                extension="",
                user_role="subaccount_user",
                password=None,
            )
            self.assertEqual(item["membership_id"], 500)
            self.assertEqual(item["email"], "ana@example.com")
        finally:
            service._resolve_subaccount_by_id = original_resolve
            service._upsert_user = original_upsert_user
            service._upsert_membership = original_upsert_membership
            service.set_membership_module_keys = original_set_modules

    def test_subaccount_actor_cannot_grant_modules_outside_own_set(self):
        service = team_api.team_members_service
        original_resolve = service._resolve_subaccount_by_id
        original_upsert_user = service._upsert_user
        original_upsert_membership = service._upsert_membership
        original_grantable = service.get_grantable_module_keys_for_actor
        original_set_modules = service.set_membership_module_keys
        try:
            service._resolve_subaccount_by_id = lambda **kwargs: type("_S", (), {"id": 10, "name": "Client X"})()
            service._upsert_user = lambda **kwargs: 20
            service._upsert_membership = lambda **kwargs: 500
            service.get_grantable_module_keys_for_actor = lambda **kwargs: {"dashboard", "creative"}
            service.set_membership_module_keys = lambda **kwargs: None

            actor = AuthUser(email="sub@example.com", role="subaccount_user", user_id=99)
            with self.assertRaisesRegex(ValueError, "în afara permisiunilor proprii"):
                service.create_subaccount_member(
                    subaccount_id=10,
                    first_name="Ana",
                    last_name="D",
                    email="ANA@EXAMPLE.COM",
                    phone="",
                    extension="",
                    user_role="subaccount_user",
                    password=None,
                    module_keys=["dashboard", "campaigns"],
                    actor_user=actor,
                )
        finally:
            service._resolve_subaccount_by_id = original_resolve
            service._upsert_user = original_upsert_user
            service._upsert_membership = original_upsert_membership
            service.get_grantable_module_keys_for_actor = original_grantable
            service.set_membership_module_keys = original_set_modules

    def test_agency_actor_can_grant_any_valid_modules(self):
        service = team_api.team_members_service
        original_resolve = service._resolve_subaccount_by_id
        original_upsert_user = service._upsert_user
        original_upsert_membership = service._upsert_membership
        original_set = service.set_membership_module_keys
        try:
            service._resolve_subaccount_by_id = lambda **kwargs: type("_S", (), {"id": 10, "name": "Client X"})()
            service._upsert_user = lambda **kwargs: 20
            service._upsert_membership = lambda **kwargs: 500
            captured = {}
            service.set_membership_module_keys = lambda **kwargs: captured.update(kwargs)

            actor = AuthUser(email="admin@example.com", role="agency_admin", user_id=1)
            item = service.create_subaccount_member(
                subaccount_id=10,
                first_name="Ana",
                last_name="D",
                email="ANA@EXAMPLE.COM",
                phone="",
                extension="",
                user_role="subaccount_user",
                password=None,
                module_keys=["dashboard", "campaigns"],
                actor_user=actor,
            )
            self.assertEqual(item["module_keys"], ["dashboard", "campaigns"])
            self.assertEqual(captured["module_keys"], ["dashboard", "campaigns"])
        finally:
            service._resolve_subaccount_by_id = original_resolve
            service._upsert_user = original_upsert_user
            service._upsert_membership = original_upsert_membership
            service.set_membership_module_keys = original_set

    def test_subaccount_list_response_includes_module_keys(self):
        user = AuthUser(email="admin@example.com", role="agency_admin")
        original = team_api.team_members_service.list_subaccount_members
        try:
            team_api.team_members_service.list_subaccount_members = lambda **kwargs: (
                [
                    {
                        "membership_id": 1,
                        "user_id": 4,
                        "display_id": "TM-1",
                        "first_name": "Ana",
                        "last_name": "Ionescu",
                        "email": "ana@example.com",
                        "phone": "",
                        "extension": "",
                        "role_key": "subaccount_user",
                        "role_label": "Subaccount User",
                        "source_scope": "subaccount",
                        "source_label": "Client A",
                        "is_active": True,
                        "is_inherited": False,
                        "module_keys": ["dashboard", "creative"],
                    }
                ],
                1,
            )
            resp = team_api.list_subaccount_team_members(subaccount_id=8, search="", user_role="", page=1, page_size=10, user=user)
            self.assertEqual(resp.items[0].module_keys, ["dashboard", "creative"])
        finally:
            team_api.team_members_service.list_subaccount_members = original

    def test_grantable_modules_endpoint_response_shape(self):
        user = AuthUser(email="admin@example.com", role="agency_admin", user_id=1)
        original_catalog = team_api.team_members_service.list_module_catalog
        original_grantable = team_api.team_members_service.get_grantable_module_keys_for_actor
        try:
            team_api.team_members_service.list_module_catalog = lambda **kwargs: [
                {"key": "dashboard", "label": "Dashboard", "order": 1, "scope": "subaccount"},
                {"key": "campaigns", "label": "Campaigns", "order": 2, "scope": "subaccount"},
            ]
            team_api.team_members_service.get_grantable_module_keys_for_actor = lambda **kwargs: {"dashboard"}

            resp = team_api.get_subaccount_grantable_modules(subaccount_id=8, user=user)

            self.assertEqual(len(resp.items), 2)
            self.assertEqual(resp.items[0].key, "dashboard")
            self.assertEqual(resp.items[0].grantable, True)
            self.assertEqual(resp.items[1].key, "campaigns")
            self.assertEqual(resp.items[1].grantable, False)
        finally:
            team_api.team_members_service.list_module_catalog = original_catalog
            team_api.team_members_service.get_grantable_module_keys_for_actor = original_grantable

    def test_grantable_modules_endpoint_subaccount_actor_only_own_modules(self):
        user = AuthUser(email="sub@example.com", role="subaccount_user", user_id=10, subaccount_id=8)
        original_catalog = team_api.team_members_service.list_module_catalog
        original_grantable = team_api.team_members_service.get_grantable_module_keys_for_actor
        try:
            team_api.team_members_service.list_module_catalog = lambda **kwargs: [
                {"key": "dashboard", "label": "Dashboard", "order": 1, "scope": "subaccount"},
                {"key": "creative", "label": "Creative", "order": 3, "scope": "subaccount"},
            ]
            team_api.team_members_service.get_grantable_module_keys_for_actor = lambda **kwargs: {"creative"}

            resp = team_api.get_subaccount_grantable_modules(subaccount_id=8, user=user)
            flags = {item.key: item.grantable for item in resp.items}
            self.assertEqual(flags, {"dashboard": False, "creative": True})
        finally:
            team_api.team_members_service.list_module_catalog = original_catalog
            team_api.team_members_service.get_grantable_module_keys_for_actor = original_grantable

    def test_grantable_modules_endpoint_agency_actor_can_grant_full_catalog(self):
        user = AuthUser(email="admin@example.com", role="agency_admin", user_id=1)
        original_catalog = team_api.team_members_service.list_module_catalog
        original_grantable = team_api.team_members_service.get_grantable_module_keys_for_actor
        try:
            team_api.team_members_service.list_module_catalog = lambda **kwargs: [
                {"key": "dashboard", "label": "Dashboard", "order": 1, "scope": "subaccount"},
                {"key": "campaigns", "label": "Campaigns", "order": 2, "scope": "subaccount"},
            ]
            team_api.team_members_service.get_grantable_module_keys_for_actor = lambda **kwargs: {"dashboard", "campaigns"}

            resp = team_api.get_subaccount_grantable_modules(subaccount_id=8, user=user)
            self.assertTrue(all(item.grantable for item in resp.items))
        finally:
            team_api.team_members_service.list_module_catalog = original_catalog
            team_api.team_members_service.get_grantable_module_keys_for_actor = original_grantable


if __name__ == "__main__":
    unittest.main()
