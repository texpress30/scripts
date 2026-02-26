# TODO — Show attached client name in Agency Accounts dropdown

- [x] Inspect current attach dropdown behavior in `/agency-accounts` and identify why it resets to placeholder.
- [x] Update UI mapping logic so each Google account row displays attached client name after successful attach.
- [x] Keep dropdown options limited to manual Agency Clients and allow re-attach to another client.
- [x] Validate via frontend build and visual check.
- [x] Commit changes and create PR.

## Review
- Converted the account-client selector to a controlled dropdown based on persisted `clients[].google_customer_id` mapping.
- After attach, UI now reloads clients and each account row resolves to selected client value; placeholder appears only when no mapping exists.
- Added explicit `Atașat la: <client name>` label per Google account row for clear confirmation.
- Dropdown keeps manual clients list and still allows changing attachment by selecting a different client.

