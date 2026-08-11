-- Maria Island ocean warming schema.
-- Single fact table (monthly surface temperature + climatology + anomaly),
-- plus a "gaps and islands" view that groups consecutive warm months into
-- discrete warm-spell events using window functions.

DROP TABLE IF EXISTS fact_maria_island_temp CASCADE;

CREATE TABLE fact_maria_island_temp (
    id                    SERIAL PRIMARY KEY,
    month_date             DATE NOT NULL,
    depth_bin               TEXT NOT NULL,
    temp_c                   NUMERIC(5,2) NOT NULL CHECK (temp_c BETWEEN 0 AND 30),
    climatology_mean_c        NUMERIC(5,2),
    climatology_p90_c         NUMERIC(5,2),
    anomaly_c                 NUMERIC(5,2),
    is_warm_month              BOOLEAN NOT NULL DEFAULT FALSE,
    source_url                 TEXT,
    UNIQUE (month_date, depth_bin)
);

CREATE INDEX idx_maria_island_month ON fact_maria_island_temp (month_date);

-- Dashboard-facing view: plain monthly series with a 12-month rolling
-- average (window function), which is what you actually plot against the
-- raw noisy monthly points.
CREATE OR REPLACE VIEW vw_temp_rolling_avg AS
SELECT
    month_date,
    temp_c,
    anomaly_c,
    is_warm_month,
    ROUND(
        AVG(temp_c) OVER (
            ORDER BY month_date
            ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
        ), 2
    ) AS rolling_12mo_avg_c
FROM fact_maria_island_temp
ORDER BY month_date;

-- "Gaps and islands": group consecutive is_warm_month = TRUE rows into
-- discrete spells, keep only spells of 3+ months -- a simplified stand-in
-- for a marine heatwave event, computed purely in SQL.
CREATE OR REPLACE VIEW vw_warm_spell_groups AS
WITH flagged AS (
    SELECT
        month_date,
        temp_c,
        anomaly_c,
        is_warm_month,
        ROW_NUMBER() OVER (ORDER BY month_date)
        - ROW_NUMBER() OVER (PARTITION BY is_warm_month ORDER BY month_date) AS grp
    FROM fact_maria_island_temp
)
SELECT
    MIN(month_date) AS spell_start,
    MAX(month_date) AS spell_end,
    COUNT(*)          AS n_months,
    ROUND(AVG(anomaly_c), 2) AS avg_anomaly_c,
    ROUND(MAX(anomaly_c), 2) AS peak_anomaly_c
FROM flagged
WHERE is_warm_month = TRUE
GROUP BY grp
HAVING COUNT(*) >= 3
ORDER BY spell_start;
