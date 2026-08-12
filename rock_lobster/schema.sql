-- Rock Lobster catch & effort schema
-- Small star-schema: one dimension (quota year / TAC) + one fact table
-- (monthly catch) + one QA reference table used purely for verification.

DROP TABLE IF EXISTS fact_rock_lobster_catch CASCADE;
DROP TABLE IF EXISTS dim_quota_year CASCADE;
DROP TABLE IF EXISTS qa_season_totals_published CASCADE;

CREATE TABLE dim_quota_year (
    quota_year      TEXT PRIMARY KEY,          -- e.g. '2026/27'
    tac_tonnes      NUMERIC(10,2) NOT NULL      -- Total Allowable Catch for that season
);

CREATE TABLE fact_rock_lobster_catch (
    id                       SERIAL PRIMARY KEY,
    quota_year               TEXT NOT NULL REFERENCES dim_quota_year(quota_year),
    month_date                DATE NOT NULL,
    catch_tonnes               NUMERIC(10,4) CHECK (catch_tonnes IS NULL OR catch_tonnes >= 0),
    uncaught_tonnes            NUMERIC(12,4),
    pct_tac_taken_scraped      NUMERIC(6,2),
    pct_tac_taken_computed     NUMERIC(6,2),
    flag_over_quota            BOOLEAN NOT NULL DEFAULT FALSE,
    flag_not_yet_reported      BOOLEAN NOT NULL DEFAULT FALSE,
    flag_pct_mismatch          BOOLEAN NOT NULL DEFAULT FALSE,
    any_flag                   BOOLEAN NOT NULL DEFAULT FALSE,
    source_url                 TEXT,
    scraped_at                 TIMESTAMPTZ,
    UNIQUE (quota_year, month_date)
);

CREATE INDEX idx_fact_rock_lobster_month  ON fact_rock_lobster_catch (month_date);
CREATE INDEX idx_fact_rock_lobster_flags  ON fact_rock_lobster_catch (any_flag) WHERE any_flag = TRUE;

-- QA-only table: the season TOTAL rows published on the source page,
-- kept separately so we can reconcile our monthly fact rows against them
-- (see verify.sql). This table is never used by the dashboard.
CREATE TABLE qa_season_totals_published (
    quota_year               TEXT PRIMARY KEY,
    catch_tonnes_published    NUMERIC(10,2)
);

-- Dashboard-facing view: season-to-date cumulative catch and percent of TAC taken,
-- computed with a window function (running total per quota year).
CREATE OR REPLACE VIEW vw_season_progress AS
SELECT
    f.quota_year,
    f.month_date,
    f.catch_tonnes,
    SUM(f.catch_tonnes) OVER (
        PARTITION BY f.quota_year ORDER BY f.month_date
    )                                                       AS cumulative_catch_tonnes,
    d.tac_tonnes,
    ROUND(
        100.0 * SUM(f.catch_tonnes) OVER (
            PARTITION BY f.quota_year ORDER BY f.month_date
        ) / d.tac_tonnes,
        1
    )                                                       AS cumulative_pct_tac
FROM fact_rock_lobster_catch f
JOIN dim_quota_year d USING (quota_year)
WHERE f.catch_tonnes IS NOT NULL
ORDER BY f.quota_year, f.month_date;

-- Dashboard-facing view: same calendar month compared year-over-year,
-- using LAG() to pull "this month last season".
CREATE OR REPLACE VIEW vw_month_over_month AS
SELECT
    quota_year,
    month_date,
    catch_tonnes,
    LAG(catch_tonnes) OVER (ORDER BY month_date) AS prev_period_catch_tonnes,
    ROUND(
        catch_tonnes - LAG(catch_tonnes) OVER (ORDER BY month_date),
        2
    ) AS change_tonnes
FROM fact_rock_lobster_catch
WHERE catch_tonnes IS NOT NULL
ORDER BY month_date;
