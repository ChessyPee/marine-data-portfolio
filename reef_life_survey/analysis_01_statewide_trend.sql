-- Analysis 1 (revised again): trend near Maria Island, using the same
-- 25-site "near Maria Island" scope as vw_site_year_combined (<=23.2km
-- from the NRS mooring, profiled directly against real site
-- coordinates) -- kept consistent across every "near Maria Island"
-- chart in the dashboard rather than each chart picking its own radius.

DROP VIEW IF EXISTS vw_statewide_trend;

CREATE VIEW vw_statewide_trend AS
WITH mi_sites AS (
    SELECT unnest(ARRAY[
        'TAS101','TAS257','TAS258','TAS253','MIR-S17','TAS62','TAS464','MIR-S16',
        'MIR-S11','MIR-S1','MIR-S2','MIR-S8','MIR-S3','TAS64','MIR-S7','MIR-S5',
        'TAS61','MIR-S9','TAS476','TAS254','TAS259','TAS100','MIR-S18','MIR-S10','MIR-S12'
    ]) AS site_code
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
