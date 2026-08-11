-- Step 5 (hi-res): VERIFY / GOVERN

-- 1. Coverage per deployment -- gaps you'd want to caveat before quoting a trend.
SELECT
    d.deployment_code, d.nominal_depth_m,
    d.deployment_start, d.deployment_end,
    COUNT(r.reading_id) AS n_readings
FROM dim_sensor_deployment d
LEFT JOIN fact_sensor_reading r ON r.deployment_id = d.deployment_id
GROUP BY d.deployment_code, d.nominal_depth_m, d.deployment_start, d.deployment_end
ORDER BY d.deployment_start;

-- 2. Plausibility check (redundant with CHECK constraints, but explicit
--    is better for a demo you're narrating live).
SELECT * FROM fact_sensor_reading
WHERE temp_c IS NULL OR temp_c NOT BETWEEN 0 AND 30
   OR (psal IS NOT NULL AND psal NOT BETWEEN 0 AND 40);

-- 3. Duplicate check on the natural key.
SELECT deployment_id, "timestamp", COUNT(*)
FROM fact_sensor_reading
GROUP BY deployment_id, "timestamp"
HAVING COUNT(*) > 1;

-- 4. Warming trend at each depth, plain SQL linear regression slope.
SELECT
    d.nominal_depth_m,
    ROUND(
        regr_slope(r.temp_c, EXTRACT(EPOCH FROM r."timestamp") / (365.25 * 24 * 3600))::numeric,
        4
    ) AS deg_c_per_year
FROM fact_sensor_reading r
JOIN dim_sensor_deployment d ON d.deployment_id = r.deployment_id
WHERE r.temp_qc IN (1, 2)
GROUP BY d.nominal_depth_m;

-- 5. Most recent warm spells at each depth (see vw_warm_spell_groups_hires).
SELECT * FROM vw_warm_spell_groups_hires ORDER BY spell_start DESC LIMIT 10;

-- 6. Stratification snapshot -- surface-minus-bottom temp diff, the number
--    that answers the "is the water column stratifying more" question.
SELECT * FROM vw_stratification ORDER BY day DESC LIMIT 30;

-- 7. How many readings were caught by spike / deployment-boundary flags
--    vs. IMOS's own bad-QC flag -- shows the extra SQL-side logic is
--    catching something beyond what quality_control already flagged.
SELECT
    COUNT(*) AS total_good_or_probable_qc,
    COUNT(*) FILTER (WHERE flag_spike) AS n_spike_flagged,
    COUNT(*) FILTER (WHERE flag_boundary) AS n_boundary_flagged
FROM vw_reading_flags;
