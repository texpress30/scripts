"""Generic API-key integration package.

A single set of CRUD endpoints + a single Pydantic schema set + a single
service module that handles every "URL + API key (+ optional secret)"
e-commerce platform we support but for which we don't have a dedicated
connector yet:

* PrestaShop
* OpenCart
* Shopware
* Lightspeed
* Volusion
* Shift4Shop (a.k.a. 3dcart, Cart Storefront)

Each platform gets its own router instance via :func:`build_router` —
``main.py`` mounts six instances under
``/integrations/{platform}/sources``. The shared router is parametrised
by a :class:`PlatformDefinition` (label, placeholders, help URL,
``feed_sources`` enum value, ``has_api_secret`` flag) so adding a 7th
platform later is one new entry in :data:`PLATFORM_DEFINITIONS` plus a
single mount in ``main.py``.

The full sync pipeline (connector + normalizer) lives in a follow-up
PR. For now these endpoints persist credentials encrypted-at-rest in
``integration_secrets`` and surface the source row in the wizard so
agency admins can already wire the merchant up — the wizard just
displays a "Sync coming soon" badge until the connector lands.
"""
