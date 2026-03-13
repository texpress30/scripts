from app.services.tiktok_account_daily_identity_resolver import resolve_tiktok_account_daily_persistence_identity


def test_single_provider_id_selects_canonical_identity():
    resolution = resolve_tiktok_account_daily_persistence_identity(
        attached_account_id="401",
        provider_ids_in_scope=["401"],
    )

    assert resolution.canonical_persistence_customer_id == "401"
    assert resolution.identity_source == "provider_scope"
    assert resolution.provider_ids_seen == ("401",)
    assert resolution.is_ambiguous is False
    assert resolution.ambiguity_reason is None


def test_repeated_provider_id_rows_resolve_to_same_canonical_identity():
    resolution = resolve_tiktok_account_daily_persistence_identity(
        attached_account_id="401",
        provider_ids_in_scope=["401", " 401 ", "401"],
    )

    assert resolution.canonical_persistence_customer_id == "401"
    assert resolution.provider_ids_seen == ("401",)
    assert resolution.is_ambiguous is False


def test_conflicting_provider_ids_are_ambiguous():
    resolution = resolve_tiktok_account_daily_persistence_identity(
        attached_account_id="401",
        provider_ids_in_scope=["401", "999"],
    )

    assert resolution.canonical_persistence_customer_id is None
    assert resolution.identity_source == "ambiguous"
    assert resolution.provider_ids_seen == ("401", "999")
    assert resolution.is_ambiguous is True
    assert resolution.ambiguity_reason == "conflicting_provider_identities_in_scope"
