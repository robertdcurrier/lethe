-- lethe SQLite schema
-- Species and their signal profiles + a catalog of noise
-- sources, consulted by --species/--profile/--noise-source
-- flags. Designed for both human inspection and agent
-- discovery via --list-* commands.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS species (
  id              INTEGER PRIMARY KEY,
  scientific_name TEXT    NOT NULL UNIQUE,
  common_name     TEXT    NOT NULL,
  notes           TEXT
);

CREATE INDEX IF NOT EXISTS idx_species_common
  ON species(common_name);

CREATE TABLE IF NOT EXISTS signal_profile (
  id         INTEGER PRIMARY KEY,
  species_id INTEGER NOT NULL REFERENCES species(id),
  name       TEXT    NOT NULL,
  freq_lo    INTEGER NOT NULL,
  freq_hi    INTEGER NOT NULL,
  notes      TEXT,
  UNIQUE(species_id, name),
  CHECK (freq_lo > 0 AND freq_hi > freq_lo)
);

CREATE INDEX IF NOT EXISTS idx_profile_species
  ON signal_profile(species_id);

CREATE TABLE IF NOT EXISTS noise_source (
  id                  INTEGER PRIMARY KEY,
  name                TEXT    NOT NULL UNIQUE,
  category            TEXT    NOT NULL,
  freq_lo             INTEGER,
  freq_hi             INTEGER,
  temporal_character  TEXT,
  notes               TEXT
);

CREATE INDEX IF NOT EXISTS idx_noise_category
  ON noise_source(category);
