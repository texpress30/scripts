"""File source (CSV / JSON / XML / Google Sheets) integration package.

Stores the optional HTTP Basic Auth credentials that file-based feeds can
require for the remote URL fetch. Credentials live encrypted-at-rest in
the shared ``integration_secrets`` table (Fernet, via
``integration_secrets_store``), keyed on the ``feed_sources.id`` UUID —
the same pattern used by the Magento 2 integration.

Google Sheets sources intentionally don't use this package because
Google's share model is "public URL" or "share with service account",
not HTTP Basic Auth. The wizard only surfaces the auth panel for
CSV / JSON / XML.
"""
