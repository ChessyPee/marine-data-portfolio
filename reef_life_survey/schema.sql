-- Reef Life Survey (RLS) raw tables. Per project instructions: load raw
-- data as-is with only basic NOT NULL/type guarantees on the join-key
-- columns every analysis depends on (site_code, survey_id, survey_date,
-- species_name) -- the real cleaning/filtering logic lives in each
-- analysis's own CTEs, not a blanket cleaning pass, since different
-- analyses need different aggregation grains (species-level vs.
-- habitat-group-level vs. site-year-level).
--
-- Deliberately no DROP TABLE here (unlike this project's other schema.sql
-- files) -- re-running this script must never be able to wipe loaded
-- data. CREATE TABLE IF NOT EXISTS makes it safe to run repeatedly.

-- Shared structure: fish and invertebrate are both species-abundance
-- long-format tables from the same RLS survey method.
CREATE TABLE IF NOT EXISTS rls_raw_fish (
    fid              TEXT PRIMARY KEY,
    survey_id         TEXT NOT NULL,
    country            TEXT,
    area                 TEXT,
    ecoregion              TEXT,
    realm                    TEXT,
    location                   TEXT,
    site_code                    TEXT NOT NULL,
    site_name                      TEXT,
    latitude                          NUMERIC,
    longitude                           NUMERIC,
    survey_date                           DATE NOT NULL,
    depth                                    NUMERIC,
    program                                     TEXT,
    visibility                                    NUMERIC,
    hour                                             TIME,
    survey_latitude                                     NUMERIC,
    survey_longitude                                      NUMERIC,
    method                                                   TEXT,
    block                                                       TEXT,
    phylum                                                        TEXT,
    class                                                            TEXT,
    "order"                                                             TEXT,
    family                                                                 TEXT,
    species_name                                                              TEXT NOT NULL,
    reporting_name                                                                TEXT,
    size_class                                                                       TEXT,
    total                                                                              NUMERIC,
    biomass                                                                              NUMERIC,
    geom                                                                                  TEXT
);

CREATE TABLE IF NOT EXISTS rls_raw_invertebrate (
    fid              TEXT PRIMARY KEY,
    survey_id         TEXT NOT NULL,
    country            TEXT,
    area                 TEXT,
    ecoregion              TEXT,
    realm                    TEXT,
    location                   TEXT,
    site_code                    TEXT NOT NULL,
    site_name                      TEXT,
    latitude                          NUMERIC,
    longitude                           NUMERIC,
    survey_date                           DATE NOT NULL,
    depth                                    NUMERIC,
    program                                     TEXT,
    visibility                                    NUMERIC,
    hour                                             TIME,
    survey_latitude                                     NUMERIC,
    survey_longitude                                      NUMERIC,
    method                                                   TEXT,
    block                                                       TEXT,
    phylum                                                        TEXT,
    class                                                            TEXT,
    "order"                                                             TEXT,
    family                                                                 TEXT,
    species_name                                                              TEXT NOT NULL,
    reporting_name                                                                TEXT,
    size_class                                                                       TEXT,
    total                                                                              NUMERIC,
    biomass                                                                              NUMERIC,
    geom                                                                                  TEXT
);

-- Different structure: benthic cover is percent-cover-by-category, not a
-- mobile species count -- no biomass/size_class, but has habitat_groups
-- (Canopy/Understorey/Substrate/etc.) and quadrat, which the other two
-- tables don't.
CREATE TABLE IF NOT EXISTS rls_raw_benthic (
    fid              TEXT PRIMARY KEY,
    survey_id         TEXT NOT NULL,
    country            TEXT,
    area                 TEXT,
    ecoregion              TEXT,
    realm                    TEXT,
    location                   TEXT,
    site_code                    TEXT NOT NULL,
    site_name                      TEXT,
    latitude                          NUMERIC,
    longitude                           NUMERIC,
    survey_date                           DATE NOT NULL,
    depth                                    NUMERIC,
    program                                     TEXT,
    visibility                                    NUMERIC,
    hour                                             TIME,
    survey_latitude                                     NUMERIC,
    survey_longitude                                      NUMERIC,
    method                                                   TEXT,
    phylum                                                      TEXT,
    class                                                          TEXT,
    "order"                                                           TEXT,
    family                                                               TEXT,
    species_name                                                            TEXT NOT NULL,
    reporting_name                                                              TEXT,
    report_group                                                                  TEXT,
    habitat_groups                                                                  TEXT,
    quadrat                                                                            TEXT,
    total                                                                                NUMERIC,
    geom                                                                                  TEXT
);

CREATE INDEX IF NOT EXISTS idx_rls_raw_fish_site_year ON rls_raw_fish (site_code, survey_date);
CREATE INDEX IF NOT EXISTS idx_rls_raw_fish_species ON rls_raw_fish (species_name);
CREATE INDEX IF NOT EXISTS idx_rls_raw_invertebrate_site_year ON rls_raw_invertebrate (site_code, survey_date);
CREATE INDEX IF NOT EXISTS idx_rls_raw_invertebrate_species ON rls_raw_invertebrate (species_name);
CREATE INDEX IF NOT EXISTS idx_rls_raw_benthic_site_year ON rls_raw_benthic (site_code, survey_date);
CREATE INDEX IF NOT EXISTS idx_rls_raw_benthic_habitat ON rls_raw_benthic (habitat_groups);
