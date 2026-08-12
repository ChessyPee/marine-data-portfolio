-- Analysis 2: geographic spread of the invasive long-spined sea urchin
-- (Centrostephanus rodgersii). Three views, one per metric, all from
-- rls_clean_invertebrate filtered to this one species. This is the first
-- analysis built (per the suggested build order) because it's the most
-- visually compelling and least dependent on getting any threshold right
-- -- pure presence/absence and counts, no judgment calls.

DROP VIEW IF EXISTS vw_urchin_first_detection;
DROP VIEW IF EXISTS vw_urchin_colonized_sites_by_year;
DROP VIEW IF EXISTS vw_urchin_southern_extent;

-- (a) First-detection year per site -- the main map. total > 0 means the
-- species was actually counted at that site on that survey, not just
-- listed as a possible species for the region.
--
-- CAVEAT (found by cross-checking against each site's own survey
-- history, not assumed): "first detected" is confounded with "first
-- surveyed" wherever a site's first-ever invertebrate survey happens to
-- be the same year the urchin was first recorded there -- in that case
-- the data cannot distinguish "the urchin arrived recently" from "nobody
-- looked here before this year". This affects 81 of 120 detection sites
-- (67.5%) in this dataset. is_confounded flags exactly those rows so the
-- map/chart can show the distinction rather than imply a false precision
-- on when the urchin actually arrived.
CREATE VIEW vw_urchin_first_detection AS
WITH first_survey AS (
    SELECT site_code, MIN(EXTRACT(YEAR FROM survey_date))::int AS first_survey_year
    FROM rls_clean_invertebrate
    GROUP BY site_code
),
first_detection AS (
    SELECT site_code,
           MIN(latitude) AS latitude,
           MIN(longitude) AS longitude,
           MIN(EXTRACT(YEAR FROM survey_date))::int AS first_detected_year
    FROM rls_clean_invertebrate
    WHERE species_name = 'Centrostephanus rodgersii' AND total > 0
    GROUP BY site_code
)
SELECT d.site_code, d.latitude, d.longitude, d.first_detected_year,
       (d.first_detected_year = s.first_survey_year) AS is_confounded
FROM first_detection d
JOIN first_survey s ON s.site_code = d.site_code;

-- (b) Colonized site count per year -- the spread-rate line chart.
CREATE VIEW vw_urchin_colonized_sites_by_year AS
SELECT EXTRACT(YEAR FROM survey_date)::int AS yr,
       COUNT(DISTINCT site_code) AS colonized_sites
FROM rls_clean_invertebrate
WHERE species_name = 'Centrostephanus rodgersii' AND total > 0
GROUP BY yr
ORDER BY yr;

-- (c) Southernmost extent per year -- lower latitude = further south.
CREATE VIEW vw_urchin_southern_extent AS
SELECT EXTRACT(YEAR FROM survey_date)::int AS yr,
       MIN(latitude) AS southernmost_latitude
FROM rls_clean_invertebrate
WHERE species_name = 'Centrostephanus rodgersii' AND total > 0
GROUP BY yr
ORDER BY yr;
