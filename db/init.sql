-- Minimal initialization for the starter database.
-- This keeps the stack usable out-of-the-box with a neutral schema/data set.

CREATE TABLE IF NOT EXISTS records (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO records (name)
VALUES
  ('Example record A'),
  ('Example record B'),
  ('Example record C')
ON CONFLICT DO NOTHING;


