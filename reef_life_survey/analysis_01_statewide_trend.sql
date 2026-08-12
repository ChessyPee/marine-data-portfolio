-- Analysis 1: statewide trend -- invasive urchin, canopy cover, key
-- predator/harvest species, all by year, 1992-2026. Temperature joined
-- separately in the dashboard (different table, different real date
-- range -- 2022-2026 only) rather than forced into this same view, so a
-- LEFT JOIN mismatch here can't silently hide rows.

DROP VIEW IF EXISTS vw_statewide_trend;

CREATE VIEW vw_statewide_trend AS
WITH urchin_yearly AS (
    SELECT
        EXTRACT(YEAR FROM survey_date)::int AS yr,
        SUM(CASE WHEN species_name = 'Centrostephanus rodgersii' THEN total ELSE 0 END) AS invasive_urchin,
        SUM(CASE WHEN species_name = 'Heliocidaris erythrogramma' THEN total ELSE 0 END) AS native_urchin,
        SUM(CASE WHEN species_name = 'Jasus edwardsii' THEN total ELSE 0 END) AS lobster,
        SUM(CASE WHEN species_name LIKE 'Haliotis%' THEN total ELSE 0 END) AS abalone
    FROM rls_clean_invertebrate
    GROUP BY yr
),
canopy_yearly AS (
    SELECT
        EXTRACT(YEAR FROM survey_date)::int AS yr,
        AVG(CASE WHEN habitat_groups = 'Canopy' THEN total END) AS canopy_pct
    FROM rls_clean_benthic
    GROUP BY yr
)
SELECT u.yr, u.invasive_urchin, u.native_urchin, u.lobster, u.abalone, c.canopy_pct
FROM urchin_yearly u
JOIN canopy_yearly c ON u.yr = c.yr
ORDER BY u.yr;
