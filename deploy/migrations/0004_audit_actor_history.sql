-- Lead CRM 2.5.8: preserve audit actor identity independently of user lifetime.

ALTER TABLE audit_logs
    ADD COLUMN IF NOT EXISTS actor_name VARCHAR(200),
    ADD COLUMN IF NOT EXISTS actor_username VARCHAR(80),
    ADD COLUMN IF NOT EXISTS actor_role VARCHAR(50);

-- Backfill existing audit rows while their user records still exist.
UPDATE audit_logs a
SET actor_name = u.full_name,
    actor_username = u.username,
    actor_role = u.role::text
FROM users u
WHERE a.user_id = u.id
  AND (a.actor_name IS NULL OR a.actor_username IS NULL OR a.actor_role IS NULL);

-- Keep historical audit entries when the referenced user is permanently deleted.
ALTER TABLE audit_logs
    DROP CONSTRAINT IF EXISTS audit_logs_user_id_fkey;

ALTER TABLE audit_logs
    ADD CONSTRAINT audit_logs_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL;
