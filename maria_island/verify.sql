-- Step 4: VERIFY / GOVERN

-- 1. Coverage check -- how many months of data per decade? Flags gaps in
--    the historical record you'd want to caveat when presenting a trend.
SELECT
    (EXTRACT(YEAR FROM month_date)::int / 10) * 10 AS decade,
    COUNT(*) AS n_months
FROM fact_maria_island_temp
GROUP BY decade
ORDER BY decade;

-- 2. Required fields / plausibility bounds (redundant with the CHECK
--    constraint, but explicit is better for a demo you're narrating live).
SELECT * FROM fact_maria_island_temp WHERE temp_c IS NULL OR temp_c NOT BETWEEN 0 AND 30;

-- 3. Duplicate check.
SELECT month_date, depth_bin, COUNT(*)
FROM fact_maria_island_temp
GROUP BY month_date, depth_bin
HAVING COUNT(*) > 1;

-- 4. Sanity check on the warming trend using plain SQL (linear regression
--    slope via regr_slope, no Python needed) -- degrees C per year.
SELECT
    ROUND(
        regr_slope(temp_c, EXTRACT(EPOCH FROM month_date) / (365.25 * 24 * 3600))::numeric,
        4
    ) AS deg_c_per_year
FROM fact_maria_island_temp;

-- 5. Most recent warm spells (see vw_warm_spell_groups in schema.sql) --
--    this is the number you'd actually put in front of a panel.
SELECT * FROM vw_warm_spell_groups ORDER BY spell_start DESC LIMIT 10;
