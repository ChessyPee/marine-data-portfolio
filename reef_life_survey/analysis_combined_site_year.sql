-- Shared combined CTE for Analyses 3 (canopy vs. urchin density), 4
-- (fish vs. barren status), and 6 (native vs. invasive correlation).
-- One row per (site_code, yr), anchored on the UNION of site-years
-- present in any of the three tables -- not just invertebrate -- so a
-- site with fish+benthic data but no invertebrate survey that year
-- isn't silently dropped.

DROP VIEW IF EXISTS vw_site_year_combined;

CREATE VIEW vw_site_year_combined AS
WITH site_years AS (
    SELECT DISTINCT site_code, EXTRACT(YEAR FROM survey_date)::int AS yr FROM rls_clean_invertebrate
    UNION
    SELECT DISTINCT site_code, EXTRACT(YEAR FROM survey_date)::int AS yr FROM rls_clean_benthic
    UNION
    SELECT DISTINCT site_code, EXTRACT(YEAR FROM survey_date)::int AS yr FROM rls_clean_fish
),
urchin AS (
    SELECT site_code, EXTRACT(YEAR FROM survey_date)::int AS yr,
        SUM(CASE WHEN species_name = 'Centrostephanus rodgersii' THEN total ELSE 0 END) AS invasive_urchin_count,
        SUM(CASE WHEN species_name = 'Heliocidaris erythrogramma' THEN total ELSE 0 END) AS native_urchin_count
    FROM rls_clean_invertebrate
    GROUP BY site_code, EXTRACT(YEAR FROM survey_date)::int
),
canopy AS (
    SELECT site_code, EXTRACT(YEAR FROM survey_date)::int AS yr,
        AVG(CASE WHEN habitat_groups = 'Canopy' THEN total END) AS canopy_pct
    FROM rls_clean_benthic
    GROUP BY site_code, EXTRACT(YEAR FROM survey_date)::int
),
fish AS (
    SELECT site_code, EXTRACT(YEAR FROM survey_date)::int AS yr,
        COUNT(DISTINCT species_name) AS fish_richness,
        SUM(biomass) AS fish_biomass
    FROM rls_clean_fish
    GROUP BY site_code, EXTRACT(YEAR FROM survey_date)::int
)
SELECT
    sy.site_code, sy.yr,
    COALESCE(u.invasive_urchin_count, 0) AS invasive_urchin_count,
    COALESCE(u.native_urchin_count, 0) AS native_urchin_count,
    c.canopy_pct, f.fish_richness, f.fish_biomass
FROM site_years sy
LEFT JOIN urchin u ON u.site_code = sy.site_code AND u.yr = sy.yr
LEFT JOIN canopy c ON c.site_code = sy.site_code AND c.yr = sy.yr
LEFT JOIN fish f ON f.site_code = sy.site_code AND f.yr = sy.yr;
