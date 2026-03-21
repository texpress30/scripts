-- Agency membership restrictions by sub-account grants.

CREATE TABLE IF NOT EXISTS membership_subaccount_access_grants (
    id BIGSERIAL PRIMARY KEY,
    membership_id BIGINT NOT NULL REFERENCES user_memberships(id) ON DELETE CASCADE,
    subaccount_id INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_membership_subaccount_access_grants_unique
ON membership_subaccount_access_grants (membership_id, subaccount_id);

CREATE INDEX IF NOT EXISTS idx_membership_subaccount_access_grants_membership_id
ON membership_subaccount_access_grants (membership_id);

ALTER TABLE user_memberships DROP CONSTRAINT IF EXISTS user_memberships_role_key_check;
ALTER TABLE user_memberships
ADD CONSTRAINT user_memberships_role_key_check
CHECK (role_key IN (
    'agency_owner',
    'agency_admin',
    'agency_member',
    'agency_viewer',
    'subaccount_admin',
    'subaccount_user',
    'subaccount_viewer'
));
