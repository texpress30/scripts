import unittest

from app.api import team as team_api
from app.schemas.team import CreateTeamMemberRequest
from app.services.auth import AuthUser
from app.services.team_members import TeamMembersService, team_members_service


class _FakeCursor:
    def __init__(self):
        self.queries: list[str] = []
        self.params: list[tuple | None] = []
        self._next_fetchone = None

    def execute(self, query, params=None):
        self.queries.append(str(query).strip())
        self.params.append(tuple(params) if params is not None else None)
        if "SELECT COUNT(*)" in str(query):
            self._next_fetchone = (0,)
        if "RETURNING id" in str(query):
            self._next_fetchone = (11,)

    def fetchone(self):
        return self._next_fetchone

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _ListMembersCursor:
    def __init__(self, rows):
        self._rows = rows
        self._fetchone = (len(rows),)

    def execute(self, query, params=None):
        if "SELECT COUNT(*)" in str(query):
            self._fetchone = (len(self._rows),)

    def fetchone(self):
        return self._fetchone

    def fetchall(self):
        return self._rows

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _ListMembersConnection:
    def __init__(self, rows):
        self._cursor = _ListMembersCursor(rows)

    def cursor(self):
        return self._cursor

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


class _SubMembersCursor:
    def __init__(self, rows, total):
        self.rows = rows
        self.total = total
        self._next_fetchone = (total,)
        self.queries: list[str] = []
        self.params: list[tuple | None] = []

    def execute(self, query, params=None):
        sql = str(query)
        self.queries.append(sql)
        self.params.append(tuple(params) if params is not None else None)
        if "SELECT COUNT(*) FROM (" in sql:
            self._next_fetchone = (self.total,)

    def fetchone(self):
        return self._next_fetchone

    def fetchall(self):
        return self.rows

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _SubMembersConn:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor

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
        self.assertIn("ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash", joined)
        self.assertIn("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active", joined)
        self.assertIn("CREATE TABLE IF NOT EXISTS user_memberships", joined)
        self.assertGreaterEqual(conn.commit_count, 2)

    def test_upsert_user_uses_placeholder_for_must_reset_password_and_persists_true_without_password(self):
        service = TeamMembersService()
        conn = _FakeConnection()
        service._connect = lambda: conn

        user_id = service._upsert_user(
            first_name="Ana",
            last_name="Pop",
            email="ana@example.com",
            phone="",
            extension="",
            avatar_url="",
            password=None,
        )

        self.assertEqual(user_id, 11)
        insert_query = conn.cursor_obj.queries[-1]
        insert_params = conn.cursor_obj.params[-1]
        self.assertIn("VALUES (%s, %s, %s, %s, %s, %s, 'ro', COALESCE(%s, ''), TRUE, %s)", insert_query)
        self.assertEqual(len(insert_params or ()), 9)
        self.assertIsNone((insert_params or (None,))[6])
        self.assertEqual(bool((insert_params or (None,))[7]), True)

    def test_upsert_user_persists_false_must_reset_when_password_is_explicit(self):
        service = TeamMembersService()
        conn = _FakeConnection()
        service._connect = lambda: conn

        user_id = service._upsert_user(
            first_name="Ana",
            last_name="Pop",
            email="ana@example.com",
            phone="",
            extension="",
            avatar_url="",
            password="StrongPassword123!",
        )

        self.assertEqual(user_id, 11)
        insert_params = conn.cursor_obj.params[-1]
        self.assertEqual(len(insert_params or ()), 9)
        self.assertEqual(bool((insert_params or (True,))[7]), False)

    def test_create_agency_member_uses_canonical_role_mapping(self):
        service = TeamMembersService()
        service._upsert_user = lambda **kwargs: 11
        service._upsert_membership = lambda **kwargs: 101
        service.set_membership_module_keys = lambda **kwargs: None

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

    def test_create_agency_owner_uses_canonical_role_mapping(self):
        service = TeamMembersService()
        service._upsert_user = lambda **kwargs: 11
        service._upsert_membership = lambda **kwargs: 101
        service.set_membership_module_keys = lambda **kwargs: None
        service.set_membership_allowed_subaccount_ids = lambda **kwargs: None
        service.get_membership_allowed_subaccount_ids = lambda **kwargs: []

        item = service.create_member(
            first_name="Owner",
            last_name="One",
            email="owner@example.com",
            phone="",
            extension="",
            user_type="agency",
            user_role="owner",
            location="România",
            subaccount="Toate",
            password=None,
        )
        self.assertEqual(item["user_role"], "owner")
        self.assertEqual(item["allowed_subaccount_ids"], [])
        self.assertFalse(item["has_restricted_subaccount_access"])

    def test_create_agency_member_persists_allowed_subaccount_grants(self):
        service = TeamMembersService()
        service._upsert_user = lambda **kwargs: 11
        service._upsert_membership = lambda **kwargs: 101
        service.set_membership_module_keys = lambda **kwargs: None
        captured: dict[str, object] = {}
        service.set_membership_allowed_subaccount_ids = lambda **kwargs: captured.update(kwargs)
        service.get_membership_allowed_subaccount_ids = lambda **kwargs: [4, 9]
        service._build_allowed_subaccount_payload = lambda **kwargs: ([4, 9], [{"id": 4, "name": "A", "label": "A"}, {"id": 9, "name": "B", "label": "B"}], True)

        item = service.create_member(
            first_name="Member",
            last_name="One",
            email="member@example.com",
            phone="",
            extension="",
            user_type="agency",
            user_role="member",
            location="România",
            subaccount="Toate",
            password=None,
            allowed_subaccount_ids=[9, 4, 9],
        )
        self.assertEqual(captured["allowed_subaccount_ids"], [4, 9])
        self.assertEqual(item["allowed_subaccount_ids"], [4, 9])
        self.assertTrue(item["has_restricted_subaccount_access"])

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
        service.set_membership_module_keys = lambda **kwargs: None

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
            self.assertEqual(resp.items[0].membership_status, "active")
        finally:
            team_api.team_members_service.list_members = original

    def test_list_members_endpoint_returns_empty_when_db_is_unavailable(self):
        original = team_api.team_members_service.list_members
        try:
            team_api.team_members_service.list_members = lambda **kwargs: (_ for _ in ()).throw(RuntimeError("connection refused"))
            resp = team_api.list_team_members(search="", user_type="", user_role="", subaccount="", page=1, page_size=10, user=self.user)
            self.assertEqual(resp.total, 0)
            self.assertEqual(resp.items, [])
        finally:
            team_api.team_members_service.list_members = original

    def test_subaccount_inherited_query_excludes_owner_admin_and_checks_grants(self):
        service = TeamMembersService()
        service._resolve_subaccount_by_id = lambda **kwargs: type("_S", (), {"id": 8, "name": "Client A"})()
        service._membership_module_keys_map = lambda rows: {int(row[0]): ["dashboard"] for row in rows}
        rows = [
            (501, 21, "Mia", "A", "mia@example.com", "", "", "agency_member", "active", "agency", True, "Agency access"),
        ]
        cursor = _SubMembersCursor(rows=rows, total=1)
        service._connect = lambda: _SubMembersConn(cursor)

        items, total = service.list_subaccount_members(subaccount_id=8, search="", user_role="", page=1, page_size=10)
        self.assertEqual(total, 1)
        self.assertEqual(items[0]["role_key"], "agency_member")
        joined = "\n".join(cursor.queries)
        self.assertIn("um.role_key IN ('agency_member', 'agency_viewer')", joined)
        self.assertIn("membership_subaccount_access_grants", joined)

    def test_list_members_endpoint_normalizes_malformed_rows(self):
        original = team_api.team_members_service.list_members
        try:
            team_api.team_members_service.list_members = lambda **kwargs: (
                [
                    {"id": "bad", "email": "skip@example.com"},
                    {
                        "id": "10",
                        "membership_id": "x",
                        "user_id": "2",
                        "first_name": "Ana",
                        "last_name": None,
                        "email": "ana@example.com",
                        "user_type": "agency",
                        "user_role": "admin",
                        "module_keys": ["Dashboard", "dashboard", None],
                    },
                ],
                2,
            )
            resp = team_api.list_team_members(search="", user_type="", user_role="", subaccount="", page=1, page_size=10, user=self.user)
            self.assertEqual(resp.total, 2)
            self.assertEqual(len(resp.items), 1)
            self.assertEqual(resp.items[0].id, 10)
            self.assertIsNone(resp.items[0].membership_id)
            self.assertEqual(resp.items[0].module_keys, ["dashboard"])
            self.assertEqual(resp.items[0].membership_status, "active")
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

    def test_subaccount_options_endpoint_skips_invalid_legacy_rows(self):
        original = team_api.client_registry_service.list_clients
        try:
            team_api.client_registry_service.list_clients = lambda: [
                {"id": "legacy", "display_id": None, "name": "Broken"},
                {"id": 5, "display_id": "X5", "name": ""},
                {"id": 6, "display_id": 11, "name": "Client Gamma"},
            ]
            resp = team_api.list_subaccount_options(user=self.user)
            self.assertEqual(len(resp.items), 2)
            self.assertEqual(resp.items[0].id, 5)
            self.assertEqual(resp.items[0].name, "Sub-account 5")
            self.assertEqual(resp.items[0].label, "#X5 — Sub-account 5")
            self.assertEqual(resp.items[1].id, 6)
        finally:
            team_api.client_registry_service.list_clients = original

    def test_subaccount_options_endpoint_returns_empty_when_db_is_unavailable(self):
        original = team_api.client_registry_service.list_clients
        try:
            team_api.client_registry_service.list_clients = lambda: (_ for _ in ()).throw(RuntimeError("connection failed"))
            resp = team_api.list_subaccount_options(user=self.user)
            self.assertEqual(resp.items, [])
        finally:
            team_api.client_registry_service.list_clients = original

    def test_list_members_tolerates_legacy_role_key_and_invalid_numeric_rows(self):
        service = TeamMembersService()
        rows = [
            ("broken", 9, "Skip", "Me", "skip@example.com", "", "", "agency_admin", "Toate", "agency"),
            (10, 20, "Ana", "Ionescu", "ana@example.com", "", "", "legacy_owner", "Toate", "agency"),
            (11, 21, "Ion", "Pop", "ion@example.com", "", "", "legacy_client", "Client A", "subaccount"),
        ]
        service._connect = lambda: _ListMembersConnection(rows)

        items, total = service.list_members(search="", user_type="", user_role="", subaccount="", page=1, page_size=10)

        self.assertEqual(total, 3)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["user_type"], "agency")
        self.assertEqual(items[0]["user_role"], "member")
        self.assertEqual(items[1]["user_type"], "client")
        self.assertEqual(items[1]["user_role"], "member")

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


    def test_initialize_schema_creates_membership_module_permissions_table(self):
        service = TeamMembersService()
        conn = _FakeConnection()
        service._connect = lambda: conn

        service.initialize_schema()

        joined = "\n".join(conn.cursor_obj.queries)
        self.assertIn("CREATE TABLE IF NOT EXISTS membership_module_permissions", joined)
        self.assertIn("idx_membership_module_permissions_unique", joined)

    def test_create_subaccount_member_with_module_keys(self):
        service = TeamMembersService()
        service._upsert_user = lambda **kwargs: 13
        service._upsert_membership = lambda **kwargs: 103
        service._resolve_subaccount_ref = lambda **kwargs: type("_S", (), {"id": 9, "name": "Client X"})()

        captured: dict[str, object] = {}

        def _set_membership_module_keys(**kwargs):
            captured.update(kwargs)

        service.set_membership_module_keys = _set_membership_module_keys

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
            module_keys=["dashboard", "creative"],
        )

        self.assertEqual(item["module_keys"], ["dashboard", "creative"])
        self.assertEqual(captured["scope_type"], "subaccount")
        self.assertEqual(captured["module_keys"], ["dashboard", "creative"])

    def test_create_subaccount_member_without_module_keys_uses_defaults(self):
        service = TeamMembersService()
        service._upsert_user = lambda **kwargs: 13
        service._upsert_membership = lambda **kwargs: 103
        service._resolve_subaccount_ref = lambda **kwargs: type("_S", (), {"id": 9, "name": "Client X"})()
        service.set_membership_module_keys = lambda **kwargs: None

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
            module_keys=None,
        )

        self.assertEqual(item["module_keys"], ["dashboard", "campaigns", "rules", "creative", "recommendations", "settings"])

    def test_create_agency_member_with_agency_navigation_keys(self):
        service = TeamMembersService()
        service._upsert_user = lambda **kwargs: 11
        service._upsert_membership = lambda **kwargs: 101
        service.set_membership_module_keys = lambda **kwargs: None

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
            module_keys=["agency_dashboard", "settings", "settings_my_team"],
        )
        self.assertEqual(item["module_keys"], ["agency_dashboard", "settings", "settings_my_team"])

    def test_create_agency_member_without_module_keys_uses_agency_defaults(self):
        service = TeamMembersService()
        service._upsert_user = lambda **kwargs: 11
        service._upsert_membership = lambda **kwargs: 101
        service.set_membership_module_keys = lambda **kwargs: None

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
            module_keys=None,
        )

        self.assertIn("agency_dashboard", item["module_keys"])
        self.assertIn("settings_my_team", item["module_keys"])
        self.assertIn("settings", item["module_keys"])

    def test_create_agency_member_with_subaccount_navigation_keys_rejected(self):
        service = TeamMembersService()
        service._upsert_user = lambda **kwargs: 11
        service._upsert_membership = lambda **kwargs: 101

        with self.assertRaisesRegex(ValueError, "scope-ul agency"):
            service.create_member(
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
                module_keys=["dashboard"],
            )

    def test_invalid_module_key_rejected(self):
        service = TeamMembersService()
        service._upsert_user = lambda **kwargs: 13
        service._upsert_membership = lambda **kwargs: 103
        service._resolve_subaccount_ref = lambda **kwargs: type("_S", (), {"id": 9, "name": "Client X"})()

        with self.assertRaisesRegex(ValueError, "Modul invalid"):
            service.create_member(
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
                module_keys=["dashboard", "invalid-module"],
            )

    def test_create_subaccount_member_with_agency_navigation_key_rejected(self):
        service = TeamMembersService()
        service._upsert_user = lambda **kwargs: 13
        service._upsert_membership = lambda **kwargs: 103
        service._resolve_subaccount_ref = lambda **kwargs: type("_S", (), {"id": 9, "name": "Client X"})()

        with self.assertRaisesRegex(ValueError, "scope-ul subaccount"):
            service.create_member(
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
                module_keys=["agency_dashboard"],
            )

    def test_module_catalog_endpoint_contract(self):
        original = team_api.team_members_service.list_module_catalog
        try:
            team_api.team_members_service.list_module_catalog = lambda **kwargs: [
                {
                    "key": "dashboard",
                    "label": "Dashboard",
                    "order": 1,
                    "scope": "subaccount",
                    "group_key": "main_nav",
                    "group_label": "Main Navigation",
                    "is_container": False,
                },
                {
                    "key": "campaigns",
                    "label": "Campaigns",
                    "order": 2,
                    "scope": "subaccount",
                    "group_key": "main_nav",
                    "group_label": "Main Navigation",
                    "is_container": False,
                },
            ]
            resp = team_api.get_team_module_catalog(scope="subaccount", user=self.user)
            self.assertEqual(len(resp.items), 2)
            self.assertEqual(resp.items[0].key, "dashboard")
            self.assertEqual(resp.items[0].group_key, "main_nav")
            self.assertFalse(resp.items[0].is_container)
        finally:
            team_api.team_members_service.list_module_catalog = original

    def test_module_catalog_endpoint_agency_scope_contract(self):
        original = team_api.team_members_service.list_module_catalog
        try:
            team_api.team_members_service.list_module_catalog = lambda **kwargs: [
                {
                    "key": "settings",
                    "label": "Settings",
                    "order": 100,
                    "scope": "agency",
                    "group_key": "settings",
                    "group_label": "Settings",
                    "parent_key": None,
                    "is_container": True,
                },
                {
                    "key": "settings_my_team",
                    "label": "My Team",
                    "order": 130,
                    "scope": "agency",
                    "group_key": "settings",
                    "group_label": "Settings",
                    "parent_key": "settings",
                    "is_container": False,
                },
            ]
            resp = team_api.get_team_module_catalog(scope="agency", user=self.user)
            self.assertEqual(len(resp.items), 2)
            self.assertEqual(resp.items[0].key, "settings")
            self.assertTrue(resp.items[0].is_container)
            self.assertEqual(resp.items[1].parent_key, "settings")
        finally:
            team_api.team_members_service.list_module_catalog = original

    def test_module_catalog_agency_contains_settings_children_metadata(self):
        service = TeamMembersService()
        items = service.list_module_catalog(scope="agency")
        by_key = {str(item["key"]): item for item in items}
        self.assertEqual(
            set(by_key.keys()),
            {
                "agency_dashboard",
                "agency_clients",
                "agency_accounts",
                "integrations",
                "feed_management",
                "agency_audit",
                "creative",
                "email_templates",
                "notifications",
                "settings",
                "settings_profile",
                "settings_company",
                "settings_my_team",
                "settings_tags",
                "settings_audit_logs",
                "settings_ai_agents",
                "settings_media_storage_usage",
            },
        )
        self.assertIn("settings", by_key)
        self.assertTrue(bool(by_key["settings"]["is_container"]))
        self.assertEqual(by_key["settings_my_team"]["parent_key"], "settings")
        self.assertEqual(by_key["settings_my_team"]["group_key"], "settings")

    def test_module_catalog_subaccount_contains_expected_keys(self):
        service = TeamMembersService()
        items = service.list_module_catalog(scope="subaccount")
        keys = [str(item["key"]) for item in items]
        self.assertEqual(
            keys,
            [
                "dashboard",
                "campaigns",
                "rules",
                "creative",
                "recommendations",
                "media",
                "settings",
                "settings_personal_profile",
                "settings_profile",
                "settings_team",
                "settings_integrations",
                "settings_accounts",
                "settings_tags",
                "settings_audit_logs",
                "settings_ai_agents",
            ],
        )

    def test_module_catalog_endpoint_returns_empty_when_db_is_unavailable(self):
        original = team_api.team_members_service.list_module_catalog
        try:
            team_api.team_members_service.list_module_catalog = lambda **kwargs: (_ for _ in ()).throw(RuntimeError("connection refused"))
            resp = team_api.get_team_module_catalog(scope="subaccount", user=self.user)
            self.assertEqual(resp.items, [])
        finally:
            team_api.team_members_service.list_module_catalog = original


    def test_create_member_endpoint_passes_module_keys_for_client_user(self):
        original = team_api.team_members_service.create_member
        try:
            def _fake_create(**kwargs):
                self.assertEqual(kwargs["module_keys"], ["dashboard", "creative"])
                return {
                    "id": 99,
                    "first_name": "Ana",
                    "last_name": "Ionescu",
                    "email": "ana@example.com",
                    "phone": "",
                    "extension": "",
                    "user_type": "client",
                    "user_role": "member",
                    "location": "România",
                    "subaccount": "Client A",
                    "module_keys": ["dashboard", "creative"],
                }

            team_api.team_members_service.create_member = _fake_create
            payload = CreateTeamMemberRequest(
                first_name="Ana",
                last_name="Ionescu",
                email="ana@example.com",
                user_type="client",
                user_role="member",
                subaccount="Client A",
                module_keys=["dashboard", "creative"],
            )
            resp = team_api.create_team_member(payload=payload, user=self.user)
            self.assertEqual(resp.item.module_keys, ["dashboard", "creative"])
        finally:
            team_api.team_members_service.create_member = original

    def test_create_member_endpoint_rejects_scope_mismatched_module_keys_for_agency_user(self):
        original = team_api.team_members_service.create_member
        try:
            team_api.team_members_service.create_member = lambda **kwargs: (_ for _ in ()).throw(
                ValueError("Cheie de navigare invalidă pentru scope-ul agency: dashboard")
            )
            payload = CreateTeamMemberRequest(
                first_name="Ana",
                last_name="Ionescu",
                email="ana@example.com",
                user_type="agency",
                user_role="member",
                module_keys=["dashboard"],
            )
            with self.assertRaises(team_api.HTTPException) as ctx:
                team_api.create_team_member(payload=payload, user=self.user)
            self.assertEqual(ctx.exception.status_code, 400)
        finally:
            team_api.team_members_service.create_member = original

    def test_create_agency_member_grant_ceiling_for_scoped_actor(self):
        service = TeamMembersService()
        service._upsert_user = lambda **kwargs: 11
        service._upsert_membership = lambda **kwargs: 101
        service.set_membership_module_keys = lambda **kwargs: None
        service.get_grantable_module_keys_for_actor = lambda **kwargs: {"agency_dashboard"}
        actor = AuthUser(email="member@example.com", role="agency_member")

        with self.assertRaisesRegex(ValueError, "în afara permisiunilor proprii"):
            service.create_member(
                first_name="Ana",
                last_name="Ionescu",
                email="ana@example.com",
                phone="",
                extension="",
                user_type="agency",
                user_role="member",
                location="RO",
                subaccount="Toate",
                password=None,
                module_keys=["agency_dashboard", "agency_clients"],
                actor_user=actor,
            )

    def tearDown(self):
        # reset shared singleton monkeypatching safety for other tests
        assert team_members_service is not None


if __name__ == "__main__":
    unittest.main()
