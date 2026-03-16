from app.services import dashboard as dashboard_module
from app.services.dashboard import unified_dashboard_service


class _FakeCursor:
    def __init__(self, state):
        self._state = state
        self._last_sql = ""
        self._last_params = ()

    def execute(self, sql, params=None):
        self._last_sql = " ".join(str(sql).split())
        self._last_params = tuple(params or ())

        if "UPDATE media_buying_configs" in self._last_sql:
            next_currency = str(self._last_params[0])
            config_id = int(self._last_params[1])
            for row in self._state["configs"]:
                if int(row["id"]) == config_id:
                    row["display_currency"] = next_currency
                    self._state["updates"] += 1
                    break

    def fetchall(self):
        if "SELECT id, display_currency FROM media_buying_configs" in self._last_sql:
            client_id = int(self._last_params[0])
            return [
                (item["id"], item["display_currency"])
                for item in self._state["configs"]
                if int(item["client_id"]) == client_id
            ]
        return []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeConn:
    def __init__(self, state):
        self._state = state

    def cursor(self):
        return _FakeCursor(self._state)

    def commit(self):
        self._state["commits"] += 1

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _run_with_state(*, clients, decisions, configs, dry_run=True, client_id=None):
    state = {"configs": [dict(item) for item in configs], "updates": 0, "commits": 0}

    original_connect = unified_dashboard_service._connect
    original_list_clients = dashboard_module.client_registry_service.list_clients
    original_decision = dashboard_module.client_registry_service.get_client_reporting_currency_decision
    try:
        unified_dashboard_service._connect = lambda: _FakeConn(state)
        dashboard_module.client_registry_service.list_clients = lambda: clients
        dashboard_module.client_registry_service.get_client_reporting_currency_decision = lambda **kwargs: decisions[int(kwargs["client_id"])]

        payload = unified_dashboard_service.audit_and_repair_client_display_currency_drift(
            client_id=client_id,
            dry_run=dry_run,
        )
    finally:
        unified_dashboard_service._connect = original_connect
        dashboard_module.client_registry_service.list_clients = original_list_clients
        dashboard_module.client_registry_service.get_client_reporting_currency_decision = original_decision

    return payload, state


def test_currency_drift_repair_dry_run_detects_without_mutation():
    payload, state = _run_with_state(
        clients=[{"id": 11}],
        decisions={11: {"client_display_currency": "USD", "display_currency_source": "agency_client_currency"}},
        configs=[{"id": 1, "client_id": 11, "display_currency": "RON"}],
        dry_run=True,
    )

    assert payload["clients_with_drift"] == 1
    assert payload["clients_repaired"] == 0
    assert payload["configs_repaired"] == 0
    assert state["updates"] == 0
    assert state["commits"] == 0
    assert payload["findings"][0]["changes"][0]["action"] == "candidate"


def test_currency_drift_repair_apply_updates_media_buying_config_currency():
    payload, state = _run_with_state(
        clients=[{"id": 12}],
        decisions={12: {"client_display_currency": "EUR", "display_currency_source": "agency_client_currency"}},
        configs=[{"id": 2, "client_id": 12, "display_currency": "USD"}],
        dry_run=False,
    )

    assert payload["clients_with_drift"] == 1
    assert payload["clients_repaired"] == 1
    assert payload["configs_repaired"] == 1
    assert state["updates"] == 1
    assert state["commits"] == 1
    assert state["configs"][0]["display_currency"] == "EUR"


def test_currency_drift_repair_handles_multi_currency_clients():
    payload, state = _run_with_state(
        clients=[{"id": 21}, {"id": 22}, {"id": 23}],
        decisions={
            21: {"client_display_currency": "USD", "display_currency_source": "agency_client_currency"},
            22: {"client_display_currency": "RON", "display_currency_source": "agency_client_currency"},
            23: {"client_display_currency": "EUR", "display_currency_source": "agency_client_currency"},
        },
        configs=[
            {"id": 11, "client_id": 21, "display_currency": "RON"},
            {"id": 12, "client_id": 22, "display_currency": "RON"},
            {"id": 13, "client_id": 23, "display_currency": "USD"},
        ],
        dry_run=False,
    )

    assert payload["total_clients_scanned"] == 3
    assert payload["clients_with_drift"] == 2
    assert payload["clients_repaired"] == 2
    assert payload["configs_repaired"] == 2
    assert state["updates"] == 2
    assert [item["display_currency"] for item in state["configs"]] == ["USD", "RON", "EUR"]


def test_currency_drift_repair_noop_when_aligned():
    payload, state = _run_with_state(
        clients=[{"id": 31}],
        decisions={31: {"client_display_currency": "USD", "display_currency_source": "agency_client_currency"}},
        configs=[{"id": 20, "client_id": 31, "display_currency": "USD"}],
        dry_run=False,
    )

    assert payload["clients_with_drift"] == 0
    assert payload["clients_repaired"] == 0
    assert payload["configs_repaired"] == 0
    assert payload["findings"][0]["status"] == "aligned"
    assert state["updates"] == 0


def test_currency_drift_repair_respects_single_client_filter():
    payload, state = _run_with_state(
        clients=[{"id": 41}, {"id": 42}],
        decisions={
            41: {"client_display_currency": "USD", "display_currency_source": "agency_client_currency"},
            42: {"client_display_currency": "EUR", "display_currency_source": "agency_client_currency"},
        },
        configs=[
            {"id": 30, "client_id": 41, "display_currency": "RON"},
            {"id": 31, "client_id": 42, "display_currency": "RON"},
        ],
        dry_run=False,
        client_id=42,
    )

    assert payload["total_clients_scanned"] == 1
    assert payload["client_id"] == 42
    assert payload["findings"][0]["client_id"] == 42
    assert state["updates"] == 1
    assert [item["display_currency"] for item in state["configs"]] == ["RON", "EUR"]


def test_currency_drift_repair_skips_ambiguous_expected_currency_and_never_touches_metadata():
    payload, state = _run_with_state(
        clients=[{"id": 51}],
        decisions={51: {"client_display_currency": "USD", "display_currency_source": "safe_fallback"}},
        configs=[{"id": 40, "client_id": 51, "display_currency": "RON", "attached_metadata_currency": "GBP"}],
        dry_run=False,
    )

    assert payload["clients_skipped"] == 1
    assert payload["clients_with_drift"] == 0
    assert state["updates"] == 0
    assert state["configs"][0]["attached_metadata_currency"] == "GBP"
