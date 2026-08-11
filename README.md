# Marine Data Portfolio -- Tasmania Data Analyst Application

Two end-to-end ETL projects built for the NRE Tas Marine Resources (Data
Analyst, Band 5) application. Both follow the same pipeline shape --
**extract -> clean -> model -> load to Postgres -> verify -> dashboard**
-- deliberately, so the panel can see one repeatable pattern applied to
two very different kinds of data.

| | Rock Lobster (`rock_lobster/`) | Maria Island (`maria_island/`) |
|---|---|---|
| Source | fishing.tas.gov.au (scraped HTML tables) | IMOS/AODN (NetCDF ocean data) |
| Ties to | Wild Fisheries / TACC monitoring | "Report Signs of a Marine Heatwave" |
| Python skills | requests, BeautifulSoup, pandas | xarray, pandas |
| SQL skills | star schema, reconciliation query | window functions, gaps-and-islands |
| Dashboard | Tableau Public (Mac) / Power BI (Windows) | Streamlit |

Status: extract/clean logic for both is built and tested (Rock Lobster
against a real-data fixture, Maria Island against synthetic data with a
known trend, since this sandbox can't reach either external source
directly). Nothing here has been run against your live database yet --
that's the part you do, following the steps below.

## 0. One-time setup (~20 min)

**Prerequisites (macOS, via Terminal):**
```bash
# Homebrew, if you don't have it:
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Check what you already have before installing:
python3 --version
git --version

# Install anything missing:
brew install python git
```
A code editor (VS Code from code.visualstudio.com) isn't strictly
required -- Terminal + `nano` works -- but it makes editing `.env` and
reading CSVs a lot easier.

```bash
cd marine-data-portfolio
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

**Get a free Postgres database (Supabase):**
1. supabase.com -> New project (free tier: 500MB storage, plenty for this).
2. Project Settings -> Database -> copy the connection string.
3. Paste it into `.env` as `DATABASE_URL`.
4. Note: free projects pause after 7 days idle. Run any query (e.g. open
   `verify.sql` in a client) the morning of your interview to wake it up.

## 1. Rock Lobster pipeline

```bash
cd rock_lobster
python extract.py                 # scrapes the live catch-updates page
python clean.py                    # unit conversion, typo/anomaly flags,
                                    #   reconciles against published totals
python load.py                     # creates schema.sql tables, loads data
# then run verify.sql in a Postgres client (Supabase's SQL editor works)
```

`extract.py` was tested against a fixture built from real rows off the
live page (`data/raw/_test_fixture.html`) covering all three table formats
the site actually uses (current tonnes format, older kg format, earliest
3-column format). Run `python extract.py data/raw/_test_fixture.html` any
time to re-check the parsing logic offline, without hitting the live site.

**Real data quality issues you'll be able to talk about**, because they're
genuinely in this source: pre-2015 tables report catch in kg, later ones
in tonnes (unit bug if missed); a stray typo in the source ("393..07");
months with no data yet (must stay NULL, not 0); months where catch
exceeded quota (negative "uncaught", not a bug, a real event).

## 2. Maria Island pipeline

```bash
cd maria_island
# One manual step first: get the NetCDF URL from https://portal.aodn.org.au/
# (search "Maria Island temperature salinity") -- see the docstring at the
# top of extract.py for exact navigation steps. Paste it into .env as
# AODN_NETCDF_URL.
python extract.py --list-vars <downloaded-file>.nc   # confirm variable names first
python extract.py                  # downloads + extracts to raw CSV
python clean.py                    # monthly resample, climatology, warm-month flags
python load.py
# then run verify.sql
```

`clean.py` was validated against a synthetic 82-year series with a known
+0.022°C/year injected trend plus two fake sensor-fault readings -- the
pipeline recovered a 0.021°C/year trend and correctly dropped both faults,
which is the kind of check you'd want to be able to describe if asked "how
do you know your pipeline works."

## 3. Dashboards

- Rock Lobster, on a Mac: `dashboards/tableau_public_guide.md` -- Power BI
  Desktop is Windows-only, so on macOS use Tableau Public instead (free,
  native Mac app). Run `python rock_lobster/export_for_tableau.py` first
  to generate the CSVs Tableau Public needs (it can't hold a live DB
  connection). `dashboards/powerbi_guide.md` is kept for reference if
  you're ever on Windows.
- Maria Island: `streamlit run dashboards/streamlit_app.py`, then deploy
  free at share.streamlit.io (see docstring in that file).

## Suggested 3-day schedule

**Day 1** -- Run both `extract.py` + `clean.py` scripts for real. Scope
Rock Lobster to the last 5 years if the full 19-year scrape is slow to
verify by hand. Read the flagged/anomaly output for both and make sure you
can explain every flag.

**Day 2** -- Set up Supabase, run both `load.py` scripts, work through
`verify.sql` for each until every check passes (or you can explain why
not). This is the "data governance" evidence -- keep a copy of the
verify.sql output, you'll want to screenshot it.

**Day 3** -- Build the Power BI report and the Streamlit app, deploy both,
write a one-page summary (architecture + screenshots + links) for the
actual interview, since live demos over unfamiliar wifi are a risk.

If day 3 runs short: finish Rock Lobster properly and leave Maria Island
at "pipeline done, dashboard in progress, here's the architecture and
what's next." That's a fine thing to say to a panel -- better than a
rushed, half-working second dashboard.

## What this demonstrates against the job description

- "Data extraction, cleansing, manipulation, and analysis" -- both
  pipelines, end to end.
- "Data management, curation, and security practices" -- the verify.sql
  gates, the CHECK constraints, the explicit anomaly flags kept (not
  hidden) in the data.
- "Develop and maintain dashboards, reports" -- Power BI (gov-standard
  tool) and Streamlit (code-forward), covering two different audiences.
- "Extract insights ... support informed decision-making" -- the season
  progress and warm-spell views are built to answer a manager's actual
  question, not just display data.
