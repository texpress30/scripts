import unittest

from app.api import team as team_api
from app.schemas.team import CreateTeamMemberRequest
from app.services.auth import AuthUser
from app.services.team_members import TeamMembersService, team_members_service


class _FakeCursor:
    def __init__(self):
        self.queries: list[str] = []
        self._next_fetchone = None

    def execute(self, query, params=None):
        self.queries.append(str(query).strip())
        if "SELECT COUNT(*)" in str(query):
            self._next_fetchone = (0,)

    def fetchone(self):
        return self._next_fetchone

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeConnection:
    def __init__(self):
        self.cursor_obj = _FakeCursor()
        self.commit_count = 0

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.commit_count += 1

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class TeamMembersFoundationTests(unittest.TestCase):
    def setUp(self):
        self.user = AuthUser(email="owner@example.com", role="agency_admin")

    def test_initialize_schema_is_idempotent(self):
        service = TeamMembersService()
        conn = _FakeConnection()
        service._connect = lambda: conn

        service.initialize_schema()
        service.initialize_schema()

        joined = "\n".join(conn.cursor_obj.queries)
        self.assertIn("CREATE TABLE IF NOT EXISTS users", joined)
        self.assertIn("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active", joined)
        self.assertIn("CREATE TABLE IF NOT EXISTS user_memberships", joined)
        self.assertGreaterEqual(conn.commit_count, 2)

    def test_create_agency_member_uses_canonical_role_mapping(self):
        service = TeamMembersService()
        service._upsert_user = lambda **kwargs: 11
        service._upsert_membership = lambda **kwargs: 101

        item = service.create_member(
            first_name="Ana",
            last_name="Ionescu",
            email="ANA@EXAMPLE.COM",
            phone="+40 700",
            extension="12",
            user_type="agency",
            user_role="admin",
            location="România",
            subaccount="Toate",
            password=None,
        )

        self.assertEqual(item["id"], 101)
        self.assertEqual(item["email"], "ana@example.com")
        self.assertEqual(item["user_type"], "agency")
        self.assertEqual(item["user_role"], "admin")
        self.assertEqual(item["subaccount"], "Toate")

    def test_create_subaccount_member_requires_real_subaccount(self):
        service = TeamMembersService()
        service._upsert_user = lambda **kwargs: 12
        service._upsert_membership = lambda **kwargs: 102
        service._resolve_subaccount_ref = lambda **kwargs: (_ for _ in ()).throw(
            ValueError("Pentru utilizatorii de tip client trebuie selectat un sub-account valid")
        )

        with self.assertRaisesRegex(ValueError, "sub-account valid"):
            service.create_member(
                first_name="Ion",
                last_name="Pop",
                email="ion@example.com",
                phone="",
                extension="",
                user_type="client",
                user_role="member",
                location="România",
                subaccount="Toate",
                password=None,
            )

    def test_create_subaccount_member_success(self):
        service = TeamMembersService()
        service._upsert_user = lambda **kwargs: 13
        service._upsert_membership = lambda **kwargs: 103
        service._resolve_subaccount_ref = lambda **kwargs: type("_S", (), {"id": 9, "name": "Client X"})()

        item = service.create_member(
            first_name="Mara",
            last_name="Dobre",
            email="mara@example.com",
            phone="",
            extension="",
            user_type="client",
            user_role="viewer",
            location="România",
            subaccount="Client X",
            password=None,
        )

        self.assertEqual(item["id"], 103)
        self.assertEqual(item["user_type"], "client")
        self.assertEqual(item["user_role"], "viewer")
        self.assertEqual(item["subaccount"], "Client X")

    def test_list_members_endpoint_passes_filters_and_contract(self):
        original = team_api.team_members_service.list_members
        try:
            def _fake_list_members(**kwargs):
                self.assertEqual(kwargs["search"], "ana")
                self.assertEqual(kwargs["user_type"], "agency")
                self.assertEqual(kwargs["user_role"], "admin")
                self.assertEqual(kwargs["subaccount"], "")
                return ([{
                    "id": 1,
                    "first_name": "Ana",
                    "last_name": "Ionescu",
                    "email": "ana@example.com",
                    "phone": "",
                    "extension": "",
                    "user_type": "agency",
                    "user_role": "admin",
                    "location": "România",
                    "subaccount": "Toate",
                }], 1)

            team_api.team_members_service.list_members = _fake_list_members
            resp = team_api.list_team_members(search="ana", user_type="agency", user_role="admin", subaccount="", page=1, page_size=10, user=self.user)
            self.assertEqual(resp.total, 1)
            self.assertEqual(resp.items[0].email, "ana@example.com")
        finally:
            team_api.team_members_service.list_members = original

    def test_subaccount_options_endpoint(self):
        original = team_api.client_registry_service.list_clients
        try:
            team_api.client_registry_service.list_clients = lambda: [
                {"id": 3, "display_id": 7, "name": "Client Alpha"},
                {"id": 4, "display_id": 8, "name": "Client Beta"},
            ]
            resp = team_api.list_subaccount_options(user=self.user)
            self.assertEqual(len(resp.items), 2)
            self.assertEqual(resp.items[0].id, 3)
            self.assertIn("Client Alpha", resp.items[0].label)
        finally:
            team_api.client_registry_service.list_clients = original

    def test_create_member_endpoint_returns_400_for_validation(self):
        original = team_api.team_members_service.create_member
        try:
            def _fake_create(**kwargs):
                raise ValueError("Email este obligatoriu")

            team_api.team_members_service.create_member = _fake_create
            with self.assertRaises(team_api.HTTPException) as ctx:
                team_api.create_team_member(
                    payload=CreateTeamMemberRequest(first_name="A", last_name="B", email="abc@example.com", user_type="agency", user_role="member"),
                    user=self.user,
                )
            self.assertEqual(ctx.exception.status_code, 400)
            self.assertIn("Email este obligatoriu", str(ctx.exception.detail))
        finally:
            team_api.team_members_service.create_member = original

    def tearDown(self):
        # reset shared singleton monkeypatching safety for other tests
        assert team_members_service is not None


if __name__ == "__main__":
    unittest.main()
