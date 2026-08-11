"""
Step 1: EXTRACT
Downloads the IMOS/AODN long-term Maria Island National Reference Station
temperature product (NetCDF) and pulls it into a raw CSV.

IMPORTANT -- getting the download URL is a manual, one-time step:
    1. Go to https://portal.aodn.org.au/
    2. Search "Maria Island temperature salinity" (or "National Reference
       Station Maria Island")
    3. Open the long-term Temperature and Salinity product (CSIRO/IMOS,
       record runs from the 1940s to present -- this is the dataset behind
       NRE Tas's own "Report Signs of a Marine Heatwave" function)
    4. Use the portal's download/OPeNDAP link to get a direct .nc URL, and
       paste it into .env as AODN_NETCDF_URL (see .env.example)
    The portal itself is a JavaScript app, which is why this has to be a
    manual step rather than something this script can discover on its own.

Run:
    python extract.py                  # uses AODN_NETCDF_URL from .env
    python extract.py path/to/file.nc  # or point at an already-downloaded file
    python extract.py --list-vars path/to/file.nc   # inspect variable names
                                                        first (AODN products
                                                        vary; adjust TEMP_VAR
                                                        below if needed)
Output:
    data/raw/maria_island_temp_raw.csv
"""

import os
import sys
from pathlib import Path

import pandas as pd
import requests
import xarray as xr
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

RAW_DIR = Path(__file__).parent / "data" / "raw"
NC_PATH = RAW_DIR / "maria_island_source.nc"
OUT_PATH = RAW_DIR / "maria_island_temp_raw.csv"

# Adjust these if --list-vars shows different names for your downloaded file
# (AODN NetCDF products aren't perfectly consistent in variable naming).
TIME_VAR_CANDIDATES = ["TIME", "time"]
TEMP_VAR_CANDIDATES = ["TEMP", "temperature", "sea_water_temperature"]
DEPTH_VAR_CANDIDATES = ["DEPTH", "depth", "NOMINAL_DEPTH"]


def download(url: str, dest: Path):
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        print(f"Using already-downloaded file: {dest}")
        return
    print(f"Downloading {url} ...")
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
    print(f"Saved -> {dest}")


def pick_var(ds, candidates, kind):
    for c in candidates:
        if c in ds.variables:
            return c
    raise KeyError(
        f"Could not find a {kind} variable among {candidates}. "
        f"Run with --list-vars to see what's actually in this file, "
        f"then add the real name to *_VAR_CANDIDATES at the top of extract.py."
    )


def main():
    args = sys.argv[1:]
    list_vars = "--list-vars" in args
    args = [a for a in args if a != "--list-vars"]

    if args:
        nc_path = Path(args[0])
    else:
        url = os.getenv("AODN_NETCDF_URL")
        if not url:
            raise SystemExit(
                "No file given and AODN_NETCDF_URL is not set in .env.\n"
                "Get the download URL from https://portal.aodn.org.au/ "
                "(see the instructions at the top of this script) and set it in .env."
            )
        nc_path = NC_PATH
        download(url, nc_path)

    ds = xr.open_dataset(nc_path)

    if list_vars:
        print("Variables in this file:")
        for v in ds.variables:
            print(f"  {v}  dims={ds[v].dims}  shape={ds[v].shape}")
        return

    time_var = pick_var(ds, TIME_VAR_CANDIDATES, "time")
    temp_var = pick_var(ds, TEMP_VAR_CANDIDATES, "temperature")

    df = ds[[temp_var]].to_dataframe().reset_index()
    df = df.rename(columns={time_var: "time", temp_var: "temp_c"})

    depth_var = next((c for c in DEPTH_VAR_CANDIDATES if c in df.columns), None)
    if depth_var:
        df = df.rename(columns={depth_var: "depth_m"})
    else:
        df["depth_m"] = None

    df = df[["time", "depth_m", "temp_c"]].dropna(subset=["temp_c"])

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_PATH, index=False)
    print(f"Extracted {len(df)} observations -> {OUT_PATH}")
    print(f"Date range: {df['time'].min()} to {df['time'].max()}")


if __name__ == "__main__":
    main()
