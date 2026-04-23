CREATE SCHEMA IF NOT EXISTS sampleext;

CREATE TABLE IF NOT EXISTS sampleext.items (
    id text PRIMARY KEY,
    content jsonb NOT NULL
);
