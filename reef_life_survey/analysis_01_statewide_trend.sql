-- Analysis 1 (revised): trend near Maria Island specifically, not
-- statewide -- restricted to the 10 nearest, densest-surveyed Maria
-- Island Reserve (MIR) monitoring sites, 14-23km from the Maria Island
-- NRS mooring (profiled directly against the NRS station's own
-- lat/lon). There are 12 MIR sites with near-annual survey coverage
-- (39-43 surveys each, 1992-2026): this keeps the 10 closest by distance
-- and drops the 2 farthest (MIR-S13 at 23.8km, MIR-S14 at 25.7km) so the
-- Maria Island temperature "proxy" stays a genuinely local comparison
-- while using the largest sample the dense-coverage tier supports.

DROP VIEW IF EXISTS vw_statewide_trend;

CREATE VIEW vw_statewide_trend AS
WITH mi_sites AS (
    SELECT unnest(ARRAY['MIR-S11','MIR-S1','MIR-S2','MIR-S8','MIR-S3',
                          'MIR-S7','MIR-S5','MIR-S9','MIR-S10','MIR-S12']) AS site_code
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
