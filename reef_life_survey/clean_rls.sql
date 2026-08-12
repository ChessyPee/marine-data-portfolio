-- Basic cleaning/validation layer, sitting between the raw tables
-- (verbatim, untouched) and each analysis's own aggregation CTEs. This is
-- NOT a replacement for per-analysis logic -- it only removes rows that
-- are structurally unusable for every downstream analysis (missing
-- coordinates, negative counts, wrong state) and scopes the whole project
-- to Tasmania. Deeper aggregation (species-year rollups, barren
-- thresholds, etc.) still happens per-analysis, since different analyses
-- need different grains.
--
-- Deliberately additive: CREATE TABLE IF NOT EXISTS + INSERT ... ON
-- CONFLICT DO NOTHING. Raw tables are never touched, and re-running this
-- script never truncates or loses data -- it only ever adds rows that
-- aren't already present.

CREATE TABLE IF NOT EXISTS rls_clean_fish (
    fid              TEXT PRIMARY KEY REFERENCES rls_raw_fish(fid),
    survey_id         TEXT NOT NULL,
    site_code           TEXT NOT NULL,
    site_name             TEXT,
    latitude                 NUMERIC NOT NULL,
    longitude                   NUMERIC NOT NULL,
    survey_date                    DATE NOT NULL,
    depth                             NUMERIC,
    method                              TEXT,
    species_name                          TEXT NOT NULL,
    reporting_name                           TEXT,
    size_class                                  TEXT,
    total                                          NUMERIC NOT NULL CHECK (total >= 0),
    biomass                                           NUMERIC CHECK (biomass IS NULL OR biomass >= 0)
);

CREATE TABLE IF NOT EXISTS rls_clean_invertebrate (
    fid              TEXT PRIMARY KEY REFERENCES rls_raw_invertebrate(fid),
    survey_id         TEXT NOT NULL,
    site_code           TEXT NOT NULL,
    site_name             TEXT,
    latitude                 NUMERIC NOT NULL,
    longitude                   NUMERIC NOT NULL,
    survey_date                    DATE NOT NULL,
    depth                             NUMERIC,
    method                              TEXT,
    species_name                          TEXT NOT NULL,
    reporting_name                           TEXT,
    size_class                                  TEXT,
    total                                          NUMERIC NOT NULL CHECK (total >= 0),
    biomass                                           NUMERIC CHECK (biomass IS NULL OR biomass >= 0)
);

CREATE TABLE IF NOT EXISTS rls_clean_benthic (
    fid              TEXT PRIMARY KEY REFERENCES rls_raw_benthic(fid),
    survey_id         TEXT NOT NULL,
    site_code           TEXT NOT NULL,
    site_name             TEXT,
    latitude                 NUMERIC NOT NULL,
    longitude                   NUMERIC NOT NULL,
    survey_date                    DATE NOT NULL,
    depth                             NUMERIC,
    method                              TEXT,
    species_name                          TEXT NOT NULL,
    reporting_name                           TEXT,
    habitat_groups                              TEXT,
    quadrat                                        TEXT,
    total                                             NUMERIC NOT NULL CHECK (total >= 0)
);

-- Tasmania scope + structurally-required fields only. Fish is already
-- entirely Tasmania already in this export (checked directly against the raw file),
-- so the area filter is a no-op safety net there, not dead weight -- it
-- protects against a future re-download that includes other states.
INSERT INTO rls_clean_fish (fid, survey_id, site_code, site_name, latitude, longitude,
                              survey_date, depth, method, species_name, reporting_name,
                              size_class, total, biomass)
SELECT fid, survey_id, site_code, site_name, latitude, longitude,
       survey_date, depth, method, species_name, reporting_name, size_class, total, biomass
FROM rls_raw_fish
WHERE area = 'Tasmania'
  AND latitude IS NOT NULL AND longitude IS NOT NULL
  AND total IS NOT NULL AND total >= 0
  AND (biomass IS NULL OR biomass >= 0)
ON CONFLICT (fid) DO NOTHING;

INSERT INTO rls_clean_invertebrate (fid, survey_id, site_code, site_name, latitude, longitude,
                                       survey_date, depth, method, species_name, reporting_name,
                                       size_class, total, biomass)
SELECT fid, survey_id, site_code, site_name, latitude, longitude,
       survey_date, depth, method, species_name, reporting_name, size_class, total, biomass
FROM rls_raw_invertebrate
WHERE area = 'Tasmania'
  AND latitude IS NOT NULL AND longitude IS NOT NULL
  AND total IS NOT NULL AND total >= 0
  AND (biomass IS NULL OR biomass >= 0)
ON CONFLICT (fid) DO NOTHING;

INSERT INTO rls_clean_benthic (fid, survey_id, site_code, site_name, latitude, longitude,
                                  survey_date, depth, method, species_name, reporting_name,
                                  habitat_groups, quadrat, total)
SELECT fid, survey_id, site_code, site_name, latitude, longitude,
       survey_date, depth, method, species_name, reporting_name, habitat_groups, quadrat, total
FROM rls_raw_benthic
WHERE area = 'Tasmania'
  AND latitude IS NOT NULL AND longitude IS NOT NULL
  AND total IS NOT NULL AND total >= 0
ON CONFLICT (fid) DO NOTHING;
