-- Analysis 1 (revised): trend near Maria Island specifically, not
-- statewide -- restricted to the 5 densest-surveyed Maria Island Reserve
-- (MIR) monitoring sites, ~12-15km from the Maria Island NRS mooring
-- (confirmed by profiling actual site coordinates against the NRS
-- station's own lat/lon, not assumed). These 5 were chosen over the
-- handful of sites literally closest by distance because those closest
-- points turned out to be one-off surveys (1-2 visits ever) -- too
-- sparse for a trend; the MIR sites have near-annual coverage 1992-2026.
-- This scoping also makes the Maria Island temperature "proxy" far more
-- defensible: these are genuinely nearby reefs, not the whole state.

DROP VIEW IF EXISTS vw_statewide_trend;

CREATE VIEW vw_statewide_trend AS
WITH mi_sites AS (
    SELECT unnest(ARRAY['MIR-S14','MIR-S2','MIR-S5','MIR-S3','MIR-S13']) AS site_code
),
urchin_yearly AS (
    SELECT
        EXTRACT(YEAR FROM survey_date)::int AS yr,
        SUM(CASE WHEN species_name = 'Centrostephanus rodgersii' THEN total ELSE 0 END) AS invasive_urchin,
        SUM(CASE WHEN species_name = 'Heliocidaris erythrogramma' THEN total ELSE 0 END) AS native_urchin,
        SUM(CASE WHEN species_name = 'Jasus edwardsii' THEN total ELSE 0 END) AS lobster,
        SUM(CASE WHEN species_name LIKE 'Haliotis%' THEN total ELSE 0 END) AS abalone
    FROM rls_clean_invertebrate
    WHERE site_code IN (SELECT site_code FROM mi_sites)
    GROUP BY yr
),
canopy_yearly AS (
    SELECT
        EXTRACT(YEAR FROM survey_date)::int AS yr,
        AVG(CASE WHEN habitat_groups = 'Canopy' THEN total END) AS canopy_pct
    FROM rls_clean_benthic
    WHERE site_code IN (SELECT site_code FROM mi_sites)
    GROUP BY yr
)
SELECT u.yr, u.invasive_urchin, u.native_urchin, u.lobster, u.abalone, c.canopy_pct
FROM urchin_yearly u
JOIN canopy_yearly c ON u.yr = c.yr
ORDER BY u.yr;
