-- Lead CRM 2.6.0: preserve sales/incentive attribution at conversion time.
-- sold_by_id identifies the assigned marketing staff at the time of sale;
-- converted_by_id remains the actual user who performed the conversion.

ALTER TABLE conversions
    ADD COLUMN IF NOT EXISTS sold_by_id INTEGER,
    ADD COLUMN IF NOT EXISTS sold_by_name VARCHAR(200),
    ADD COLUMN IF NOT EXISTS sold_by_username VARCHAR(80),
    ADD COLUMN IF NOT EXISTS sold_by_team_name VARCHAR(120);

ALTER TABLE conversions
    DROP CONSTRAINT IF EXISTS conversions_sold_by_id_fkey;

ALTER TABLE conversions
    ADD CONSTRAINT conversions_sold_by_id_fkey
    FOREIGN KEY (sold_by_id) REFERENCES users(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS ix_conversions_sold_by_id ON conversions(sold_by_id);

-- Backfill existing conversions from the lead's current assignment. Historical
-- assignment changes that happened before 2.6.0 cannot be reconstructed, but
-- this gives existing sales a usable attribution where the lead is assigned.
UPDATE conversions c
SET sold_by_id = l.assigned_to_id,
    sold_by_name = u.full_name,
    sold_by_username = u.username,
    sold_by_team_name = t.name
FROM leads l
LEFT JOIN users u ON u.id = l.assigned_to_id
LEFT JOIN teams t ON t.id = u.team_id
WHERE c.lead_id = l.id
  AND c.sold_by_id IS NULL
  AND l.assigned_to_id IS NOT NULL;
