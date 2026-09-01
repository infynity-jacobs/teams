-- Adds the place_area and referred_by columns to the leads table.
-- setting_options (the admin-managed "Referred By" list) is a brand
-- new table, so it doesn't need a migration - Base.metadata.create_all()
-- creates it automatically the next time the backend starts, since
-- create_all() only ever creates *missing tables*, never missing
-- *columns* on tables that already exist.

ALTER TABLE leads ADD COLUMN IF NOT EXISTS place_area VARCHAR(200);
ALTER TABLE leads ADD COLUMN IF NOT EXISTS referred_by VARCHAR(200);

CREATE INDEX IF NOT EXISTS ix_leads_place_area ON leads (place_area);
CREATE INDEX IF NOT EXISTS ix_leads_referred_by ON leads (referred_by);
