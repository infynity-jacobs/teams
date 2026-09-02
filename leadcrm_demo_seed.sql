-- Lead CRM demo data seed
-- Creates 3 demo teams, 15 team members (3 Team Leaders + 12 Marketing Staff),
-- plus 2 Marketing Managers and 1 Site Admin, then 10 demo leads with
-- randomized lifecycle statuses and populated lead/history/follow-up fields.
--
-- All demo user passwords: Demo@12345
--
-- Run on the Lead CRM database:
--   sudo -u postgres psql -d leadcrm -f leadcrm_demo_seed.sql
--
-- The script is idempotent for usernames/team names and will not duplicate
-- the demo users/leads if it is run again.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

BEGIN;

-- ---------------------------------------------------------------------------
-- Teams
-- ---------------------------------------------------------------------------
INSERT INTO teams (name, description, is_active)
VALUES
  ('Demo Team Alpha', 'Demo team for CRM testing - Alpha', TRUE),
  ('Demo Team Beta',  'Demo team for CRM testing - Beta', TRUE),
  ('Demo Team Gamma', 'Demo team for CRM testing - Gamma', TRUE)
ON CONFLICT (name) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Higher-level demo users
-- ---------------------------------------------------------------------------
INSERT INTO users (username, email, full_name, hashed_password, role, team_id, is_active, session_version)
VALUES
  ('demo_manager_01', 'demo.manager01@example.com', 'Demo Marketing Manager 01',
   crypt('Demo@12345', gen_salt('bf', 12)), 'marketing_manager', NULL, TRUE, 0),
  ('demo_manager_02', 'demo.manager02@example.com', 'Demo Marketing Manager 02',
   crypt('Demo@12345', gen_salt('bf', 12)), 'marketing_manager', NULL, TRUE, 0),
  ('demo_site_admin', 'demo.siteadmin@example.com', 'Demo Site Administrator',
   crypt('Demo@12345', gen_salt('bf', 12)), 'site_admin', NULL, TRUE, 0)
ON CONFLICT (username) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Team Alpha: 1 leader + 4 staff
-- ---------------------------------------------------------------------------
INSERT INTO users (username, email, full_name, hashed_password, role, team_id, is_active, session_version)
SELECT 'demo_alpha_leader', 'demo.alpha.leader@example.com', 'Demo Alpha Team Leader',
       crypt('Demo@12345', gen_salt('bf', 12)), 'team_leader', t.id, TRUE, 0
FROM teams t WHERE t.name = 'Demo Team Alpha'
ON CONFLICT (username) DO NOTHING;

INSERT INTO users (username, email, full_name, hashed_password, role, team_id, is_active, session_version)
SELECT x.username, x.email, x.full_name, crypt('Demo@12345', gen_salt('bf', 12)),
       'marketing_staff', t.id, TRUE, 0
FROM teams t
CROSS JOIN (VALUES
  ('demo_alpha_staff01','demo.alpha.staff01@example.com','Demo Alpha Staff 01'),
  ('demo_alpha_staff02','demo.alpha.staff02@example.com','Demo Alpha Staff 02'),
  ('demo_alpha_staff03','demo.alpha.staff03@example.com','Demo Alpha Staff 03'),
  ('demo_alpha_staff04','demo.alpha.staff04@example.com','Demo Alpha Staff 04')
) AS x(username,email,full_name)
WHERE t.name = 'Demo Team Alpha'
ON CONFLICT (username) DO NOTHING;

-- Team Beta
INSERT INTO users (username, email, full_name, hashed_password, role, team_id, is_active, session_version)
SELECT 'demo_beta_leader', 'demo.beta.leader@example.com', 'Demo Beta Team Leader',
       crypt('Demo@12345', gen_salt('bf', 12)), 'team_leader', t.id, TRUE, 0
FROM teams t WHERE t.name = 'Demo Team Beta'
ON CONFLICT (username) DO NOTHING;

INSERT INTO users (username, email, full_name, hashed_password, role, team_id, is_active, session_version)
SELECT x.username, x.email, x.full_name, crypt('Demo@12345', gen_salt('bf', 12)),
       'marketing_staff', t.id, TRUE, 0
FROM teams t
CROSS JOIN (VALUES
  ('demo_beta_staff01','demo.beta.staff01@example.com','Demo Beta Staff 01'),
  ('demo_beta_staff02','demo.beta.staff02@example.com','Demo Beta Staff 02'),
  ('demo_beta_staff03','demo.beta.staff03@example.com','Demo Beta Staff 03'),
  ('demo_beta_staff04','demo.beta.staff04@example.com','Demo Beta Staff 04')
) AS x(username,email,full_name)
WHERE t.name = 'Demo Team Beta'
ON CONFLICT (username) DO NOTHING;

-- Team Gamma
INSERT INTO users (username, email, full_name, hashed_password, role, team_id, is_active, session_version)
SELECT 'demo_gamma_leader', 'demo.gamma.leader@example.com', 'Demo Gamma Team Leader',
       crypt('Demo@12345', gen_salt('bf', 12)), 'team_leader', t.id, TRUE, 0
FROM teams t WHERE t.name = 'Demo Team Gamma'
ON CONFLICT (username) DO NOTHING;

INSERT INTO users (username, email, full_name, hashed_password, role, team_id, is_active, session_version)
SELECT x.username, x.email, x.full_name, crypt('Demo@12345', gen_salt('bf', 12)),
       'marketing_staff', t.id, TRUE, 0
FROM teams t
CROSS JOIN (VALUES
  ('demo_gamma_staff01','demo.gamma.staff01@example.com','Demo Gamma Staff 01'),
  ('demo_gamma_staff02','demo.gamma.staff02@example.com','Demo Gamma Staff 02'),
  ('demo_gamma_staff03','demo.gamma.staff03@example.com','Demo Gamma Staff 03'),
  ('demo_gamma_staff04','demo.gamma.staff04@example.com','Demo Gamma Staff 04')
) AS x(username,email,full_name)
WHERE t.name = 'Demo Team Gamma'
ON CONFLICT (username) DO NOTHING;

-- Assign team leaders
UPDATE teams t
SET leader_id = u.id
FROM users u
WHERE t.name = 'Demo Team Alpha' AND u.username = 'demo_alpha_leader';

UPDATE teams t
SET leader_id = u.id
FROM users u
WHERE t.name = 'Demo Team Beta' AND u.username = 'demo_beta_leader';

UPDATE teams t
SET leader_id = u.id
FROM users u
WHERE t.name = 'Demo Team Gamma' AND u.username = 'demo_gamma_leader';

-- ---------------------------------------------------------------------------
-- 10 demo leads
-- ---------------------------------------------------------------------------
-- Status distribution intentionally covers every supported lifecycle state.
INSERT INTO leads
(first_name,last_name,email,phone,company,source,place_area,referred_by,status,
 assigned_to_id,team_id,notes,dedup_key,created_by_id,created_at,updated_at,
 converted_at,lost_reason)
SELECT
  d.first_name,d.last_name,d.email,d.phone,d.company,d.source,d.place_area,d.referred_by,
  d.status::leadstatusenum,
  u.id,t.id,d.notes,d.email,m.id,
  NOW() - (d.days_old || ' days')::interval,
  NOW() - (d.days_old || ' days')::interval,
  CASE WHEN d.status = 'converted' THEN NOW() - ((d.days_old-2) || ' days')::interval ELSE NULL END,
  CASE WHEN d.status = 'lost' THEN d.lost_reason ELSE NULL END
FROM (VALUES
  ('Arun','Nair','demo.lead01@example.com','9000001001','Demo Retail 01','Website','Kochi','Website','new','demo_alpha_staff01','Demo Team Alpha','New website enquiry - first contact pending.',30,NULL),
  ('Meera','Joseph','demo.lead02@example.com','9000001002','Demo Solutions 02','Facebook','Ernakulam','Facebook Campaign','contacted','demo_alpha_staff02','Demo Team Alpha','Initial call completed; customer requested details.',25,NULL),
  ('Rahul','Menon','demo.lead03@example.com','9000001003','Demo Traders 03','Referral','Thrissur','Existing Customer','follow_up','demo_beta_staff01','Demo Team Beta','Positive discussion; follow-up scheduled.',20,NULL),
  ('Anjali','Thomas','demo.lead04@example.com','9000001004','Demo Foods 04','Website','Kottayam','Website','pending','demo_beta_staff02','Demo Team Beta','Waiting for management approval.',18,NULL),
  ('Vivek','Kumar','demo.lead05@example.com','9000001005','Demo Services 05','Google Ads','Calicut','Google Ads','converted','demo_beta_staff03','Demo Team Beta','Successfully converted after product demonstration.',15,NULL),
  ('Sreya','Pillai','demo.lead06@example.com','9000001006','Demo Interiors 06','Instagram','Trivandrum','Instagram','lost','demo_gamma_staff01','Demo Team Gamma','Customer selected another supplier.',12,'Price / competitor'),
  ('Nikhil','Varma','demo.lead07@example.com','9000001007','Demo Tech 07','Referral','Alappuzha','Partner','closed','demo_gamma_staff02','Demo Team Gamma','Lead closed after final discussion.',10,NULL),
  ('Devika','Rao','demo.lead08@example.com','9000001008','Demo Healthcare 08','Website','Kannur','Website','contacted','demo_gamma_staff03','Demo Team Gamma','Second contact attempt required.',8,NULL),
  ('Faisal','Ali','demo.lead09@example.com','9000001009','Demo Logistics 09','Facebook','Malappuram','Facebook Campaign','follow_up','demo_alpha_staff03','Demo Team Alpha','Quotation requested; follow-up scheduled.',6,NULL),
  ('Kiran','Das','demo.lead10@example.com','9000001010','Demo Education 10','Google Ads','Kollam','Google Ads','converted','demo_alpha_staff04','Demo Team Alpha','Converted from Google Ads campaign.',4,NULL)
) AS d(first_name,last_name,email,phone,company,source,place_area,referred_by,status,assignee,team_name,notes,days_old,lost_reason)
JOIN users u ON u.username = d.assignee
JOIN teams t ON t.name = d.team_name
JOIN users m ON m.username = 'demo_manager_01'
WHERE NOT EXISTS (SELECT 1 FROM leads l WHERE l.dedup_key = d.email);

-- ---------------------------------------------------------------------------
-- Status history for demo leads
-- ---------------------------------------------------------------------------
INSERT INTO lead_status_history (lead_id, old_status, new_status, changed_by_id, note, changed_at)
SELECT l.id, NULL, l.status::text, l.created_by_id,
       'Demo seed: initial status', l.created_at
FROM leads l
WHERE l.email LIKE 'demo.lead%@example.com'
  AND NOT EXISTS (
    SELECT 1 FROM lead_status_history h
    WHERE h.lead_id = l.id AND h.old_status IS NULL
  );

-- ---------------------------------------------------------------------------
-- One follow-up per demo lead, with varied outcomes
-- ---------------------------------------------------------------------------
INSERT INTO follow_ups
(lead_id,staff_id,follow_up_type,scheduled_at,completed_at,outcome,notes,created_at)
SELECT
  l.id,l.assigned_to_id,
  CASE (l.id % 4) WHEN 0 THEN 'call' WHEN 1 THEN 'email' WHEN 2 THEN 'meeting' ELSE 'other' END,
  l.created_at + interval '3 days',
  CASE WHEN l.status::text IN ('converted','closed','lost') THEN l.created_at + interval '4 days' ELSE NULL END,
  CASE
    WHEN l.status::text = 'converted' THEN 'Converted'
    WHEN l.status::text = 'lost' THEN 'Not interested'
    WHEN l.status::text = 'closed' THEN 'Closed successfully'
    WHEN l.status::text = 'follow_up' THEN 'Callback requested'
    ELSE NULL
  END,
  'Demo follow-up record for testing CRM workflow.',
  l.created_at
FROM leads l
WHERE l.email LIKE 'demo.lead%@example.com'
  AND NOT EXISTS (SELECT 1 FROM follow_ups f WHERE f.lead_id = l.id);

COMMIT;

-- Verification summary
SELECT 'Demo teams' AS item, COUNT(*) AS count
FROM teams WHERE name LIKE 'Demo Team %'
UNION ALL
SELECT 'Demo users', COUNT(*)
FROM users WHERE username LIKE 'demo_%'
UNION ALL
SELECT 'Demo leads', COUNT(*)
FROM leads WHERE email LIKE 'demo.lead%@example.com'
UNION ALL
SELECT 'Demo follow-ups', COUNT(*)
FROM follow_ups f JOIN leads l ON l.id=f.lead_id
WHERE l.email LIKE 'demo.lead%@example.com';
