"""
Step 5 (governance): automated data-quality gate.
verify_hires.sql is informational -- it prints query results for a human
to read and judge. This script runs the same kind of checks but as real
pass/fail assertions: it exits non-zero if anything in the FAIL tier
trips, so it can be wired into a CI job, a cron alert, or just run after
every load without anyone having to remember to eyeball a query result.

FAIL (exit 1): the kind of thing that means the data is actually wrong --
duplicates, out-of-range values, orphaned foreign keys.
WARN (does not fail the gate, but prints loudly): the kind of thing that's
expected sometimes (a deployment gap, a noisy instrument) but worth a
human's attention if it's trending the wrong way.

Run:
    python validate_hires.py
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from db import get_engine  # noqa: E402

FRESHNESS_WARN_DAYS = 14
QC_BAD_RATE_WARN_PCT = 15.0
REJECTION_RATE_WARN_PCT = 5.0


def main():
    engine = get_engine()
    failures = []
    warnings = []

    with engine.connect() as conn:
        # --- FAIL tier ---------------------------------------------------
        dupes = conn.exec_driver_sql(
            'SELECT COUNT(*) FROM ('
            '  SELECT deployment_id, "timestamp" FROM fact_sensor_reading'
            '  GROUP BY deployment_id, "timestamp" HAVING COUNT(*) > 1'
            ') d'
        ).scalar()
        if dupes:
            failures.append(f"{dupes} duplicate (deployment_id, timestamp) row(s) in fact_sensor_reading")

        out_of_range = conn.exec_driver_sql(
            "SELECT COUNT(*) FROM fact_sensor_reading "
            "WHERE temp_c NOT BETWEEN 0 AND 30 "
            "   OR (psal IS NOT NULL AND psal NOT BETWEEN 0 AND 40)"
        ).scalar()
        if out_of_range:
            failures.append(f"{out_of_range} row(s) outside physically plausible temp/psal bounds")

        orphans = conn.exec_driver_sql(
            "SELECT COUNT(*) FROM fact_sensor_reading r "
            "LEFT JOIN dim_sensor_deployment d ON d.deployment_id = r.deployment_id "
            "WHERE d.deployment_id IS NULL"
        ).scalar()
        if orphans:
            failures.append(f"{orphans} fact row(s) with no matching dim_sensor_deployment (FK integrity)")

        # --- WARN tier -----------------------------------------------------
        latest = conn.exec_driver_sql('SELECT MAX("timestamp") FROM fact_sensor_reading').scalar()
        if latest:
            age_days = (datetime.now(timezone.utc) - latest).days
            if age_days > FRESHNESS_WARN_DAYS:
                warnings.append(
                    f"Latest reading is {age_days} days old ({latest}) -- "
                    f"exceeds the {FRESHNESS_WARN_DAYS}-day freshness threshold. "
                    "Could be a normal gap between deployments, or a stalled pipeline."
                )

        qc_rates = conn.exec_driver_sql(
            "SELECT d.deployment_code, d.nominal_depth_m, "
            "  ROUND(100.0 * COUNT(*) FILTER (WHERE r.temp_qc IN (3,4)) / COUNT(*), 1) AS bad_pct "
            "FROM fact_sensor_reading r "
            "JOIN dim_sensor_deployment d ON d.deployment_id = r.deployment_id "
            "GROUP BY d.deployment_code, d.nominal_depth_m "
            "HAVING ROUND(100.0 * COUNT(*) FILTER (WHERE r.temp_qc IN (3,4)) / COUNT(*), 1) > %s"
            % QC_BAD_RATE_WARN_PCT
        ).fetchall()
        for code, depth, pct in qc_rates:
            warnings.append(
                f"{code} @ {depth}m has {pct}% of readings IMOS-flagged suspect/bad (temp_qc 3/4) "
                f"-- exceeds the {QC_BAD_RATE_WARN_PCT}% threshold, worth checking for a sensor fault."
            )

        last_load = conn.exec_driver_sql(
            "SELECT pipeline, rows_source, rows_loaded, rows_rejected, finished_at "
            "FROM etl_load_log ORDER BY finished_at DESC LIMIT 1"
        ).fetchone()
        if last_load:
            pipeline, rows_source, rows_loaded, rows_rejected, finished_at = last_load
            rejection_pct = 100.0 * rows_rejected / rows_source if rows_source else 0
            if rejection_pct > REJECTION_RATE_WARN_PCT:
                warnings.append(
                    f"Last load ({pipeline}, {finished_at}) rejected {rejection_pct:.1f}% of source rows "
                    f"({rows_rejected}/{rows_source}) -- exceeds the {REJECTION_RATE_WARN_PCT}% threshold. "
                    "A sudden jump usually means a schema/format change, not just normal noise."
                )
        else:
            warnings.append("No entries in etl_load_log yet -- run load_hires.py or the SQL ETL path first.")

    print("=== Data quality gate: fact_sensor_reading / dim_sensor_deployment ===\n")
    if failures:
        print(f"FAIL ({len(failures)}):")
        for f in failures:
            print(f"  ✗ {f}")
    else:
        print("FAIL tier: clean.")

    print()
    if warnings:
        print(f"WARN ({len(warnings)}):")
        for w in warnings:
            print(f"  ! {w}")
    else:
        print("WARN tier: clean.")

    if failures:
        print("\nGate result: FAILED")
        sys.exit(1)
    print("\nGate result: PASSED" + (" (with warnings)" if warnings else ""))


if __name__ == "__main__":
    main()
