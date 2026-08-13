-- Shared combined CTE for Analyses 3 (canopy vs. urchin density), 4
-- (fish vs. barren status), and 6 (native vs. invasive correlation).
-- One row per (site_code, yr), anchored on the UNION of site-years
-- present in any of the three tables -- not just invertebrate -- so a
-- site with fish+benthic data but no invertebrate survey that year
-- isn't silently dropped.
--
-- Restricted to the 25 sites nearest the Maria Island NRS mooring
-- (profiled directly against real site coordinates, <=23.2km), matching
-- the same "near Maria Island" scoping as vw_statewide_trend -- these
-- charts pool many site-years per group, so the mix of 12 densely-
-- surveyed MIR sites plus sparser nearby TAS-coded points is fine here
-- (unlike a line-over-time chart, a sparse site just contributes fewer
-- points, it doesn't create a gap).

DROP VIEW IF EXISTS vw_site_year_combined;

CREATE VIEW vw_site_year_combined AS
WITH mi_sites AS (
    SELECT unnest(ARRAY[
        'TAS101','TAS257','TAS258','TAS253','MIR-S17','TAS62','TAS464','MIR-S16',
        'MIR-S11','MIR-S1','MIR-S2','MIR-S8','MIR-S3','TAS64','MIR-S7','MIR-S5',
        'TAS61','MIR-S9','TAS476','TAS254','TAS259','TAS100','MIR-S18','MIR-S10','MIR-S12'
    ]) AS site_code
),
site_years AS (
    SELECT DISTINCT site_code, EXTRACT(YEAR FROM survey_date)::int AS yr FROM rls_clean_invertebrate
    WHERE site_code IN (SELECT site_code FROM mi_sites)
    UNION
    SELECT DISTINCT site_code, EXTRACT(YEAR FROM survey_date)::int AS yr FROM rls_clean_benthic
    WHERE site_code IN (SELECT site_code FROM mi_sites)
    UNION
    SELECT DISTINCT site_code, EXTRACT(YEAR FROM survey_date)::int AS yr FROM rls_clean_fish
    WHERE site_code IN (SELECT site_code FROM mi_sites)
),
urchin AS (
    SELECT site_code, EXTRACT(YEAR FROM survey_date)::int AS yr,
        SUM(CASE WHEN species_name = 'Centrostephanus rodgersii' THEN total ELSE 0 END) AS invasive_urchin_count,
        SUM(CASE WHEN species_name = 'Heliocidaris erythrogramma' THEN total ELSE 0 END) AS native_urchin_count
    FROM rls_clean_invertebrate
    WHERE site_code IN (SELECT site_code FROM mi_sites)
    GROUP BY site_code, EXTRACT(YEAR FROM survey_date)::int
),
canopy AS (
    SELECT site_code, EXTRACT(YEAR FROM survey_date)::int AS yr,
        AVG(CASE WHEN habitat_groups = 'Canopy' THEN total END) AS canopy_pct
    FROM rls_clean_benthic
    WHERE site_code IN (SELECT site_code FROM mi_sites)
    GROUP BY site_code, EXTRACT(YEAR FROM survey_date)::int
),
fish AS (
    SELECT site_code, EXTRACT(YEAR FROM survey_date)::int AS yr,
        COUNT(DISTINCT species_name) AS fish_richness,
        SUM(biomass) AS fish_biomass,
        SUM(total) AS fish_count
    FROM rls_clean_fish
    WHERE site_code IN (SELECT site_code FROM mi_sites)
    GROUP BY site_code, EXTRACT(YEAR FROM survey_date)::int
)
SELECT
    sy.site_code, sy.yr,
    COALESCE(u.invasive_urchin_count, 0) AS invasive_urchin_count,
    COALESCE(u.native_urchin_count, 0) AS native_urchin_count,
    c.canopy_pct, f.fish_richness, f.fish_biomass, f.fish_count
FROM site_years sy
LEFT JOIN urchin u ON u.site_code = sy.site_code AND u.yr = sy.yr
LEFT JOIN canopy c ON c.site_code = sy.site_code AND c.yr = sy.yr
LEFT JOIN fish f ON f.site_code = sy.site_code AND f.yr = sy.yr;
