-- Step 4: VERIFY / GOVERN
-- Run these after load.py. Every query should return zero rows (or an
-- expected, explainable count) before you trust the dashboard on top of it.
-- This is the "data curation and quality" step the job description asks for
-- -- treat it as a real gate, not a formality.

-- 1. Row counts per quota year -- sanity check against how many months
--    you'd expect (roughly 11-12 per season; some months are closed season).
SELECT quota_year, COUNT(*) AS n_months
FROM fact_rock_lobster_catch
GROUP BY quota_year
ORDER BY quota_year;

-- 2. Required fields should never be null.
SELECT * FROM fact_rock_lobster_catch WHERE month_date IS NULL OR quota_year IS NULL;

-- 3. Reconciliation: do the monthly rows sum to the season TOTAL that
--    Fishing Tasmania itself published? Anything returned here means the
--    scrape or the cleaning step dropped or double-counted a month.
SELECT
    f.quota_year,
    ROUND(SUM(f.catch_tonnes), 2)      AS summed_tonnes,
    q.catch_tonnes_published,
    ROUND(SUM(f.catch_tonnes) - q.catch_tonnes_published, 2) AS diff_tonnes
FROM fact_rock_lobster_catch f
JOIN qa_season_totals_published q USING (quota_year)
GROUP BY f.quota_year, q.catch_tonnes_published
HAVING ABS(SUM(f.catch_tonnes) - q.catch_tonnes_published) > 0.5;

-- 4. Rows flagged during cleaning (typos, over-quota months, % mismatches)
--    -- review these manually before presenting the numbers.
SELECT quota_year, month_date, catch_tonnes, uncaught_tonnes,
       flag_over_quota, flag_pct_mismatch, any_flag
FROM fact_rock_lobster_catch
WHERE any_flag = TRUE
ORDER BY quota_year, month_date;

-- 5. Duplicate check (should be impossible given the UNIQUE constraint,
--    but a good habit to check explicitly).
SELECT quota_year, month_date, COUNT(*)
FROM fact_rock_lobster_catch
GROUP BY quota_year, month_date
HAVING COUNT(*) > 1;
