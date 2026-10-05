#!/usr/bin/env python3
"""Turn the matched cohort and the groups' diagnoses into pheauxWAS input CSVs.

This is the step between matching and the PheWAS. It does three things that
pheauxWAS cannot do itself:

1. Keeps only diagnoses of people in the matched cohort.
2. Drops the codes that define the exposure (HaT = D89.44). Otherwise the
   exposure code maps to its own phecode (GE_969.4) and comes back as a
   guaranteed, meaningless top hit.
3. Keeps only diagnoses in the chosen window relative to each person's index
   date. pheauxWAS counts every event it is given, so the window has to be
   applied here.

Windows (index day itself is left out of pre and post, since codes entered on
the diagnosis day are usually part of the HaT workup):
    pre   diagnoses before the index date: phenotypes present before diagnosis
    post  diagnoses after the index date: includes post-diagnosis workup
    all   every diagnosis, any date

--lookback-years N limits pre to the N years before index, so everyone gets the
same window (the HaT study uses 3). It is ignored for post and all.

Inputs are the files adapting-cosmos/build_group_parquet.py writes: the matched
cohort (from matchit_example.R) and both groups' *_group_diagnoses.parquet.

Example, from the repo root:

    python3 tutorial/prepare_phewas_inputs.py \\
        --cohort tutorial/work/matched_cohort.parquet \\
        --diagnoses tutorial/synthetic_cosmos/hat/hat_group_diagnoses.parquet \\
                    tutorial/synthetic_cosmos/ctrl/control_group_diagnoses.parquet \\
        --window pre --lookback-years 3 \\
        --out-dir tutorial/work
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cohort", required=True, help="matched cohort parquet, one row per patient")
    ap.add_argument("--diagnoses", nargs="+", required=True,
                    help="the groups' *_group_diagnoses.parquet files")
    ap.add_argument("--window", choices=["pre", "post", "all"], required=True)
    ap.add_argument("--lookback-years", type=float,
                    help="with --window pre: keep only diagnoses this many years before index")
    ap.add_argument("--exclude-codes", nargs="+", default=["D89.44"],
                    help="exposure-defining ICD codes to drop (default: D89.44)")
    ap.add_argument("--out-dir", default="tutorial/work")
    args = ap.parse_args()

    people = pd.read_parquet(args.cohort)
    dx = pd.concat([pd.read_parquet(f) for f in args.diagnoses], ignore_index=True)
    n_start = len(dx)

    dx = dx[dx["PatientDurableKey"].isin(people["PatientDurableKey"])]
    n_in_cohort = len(dx)

    excluded = dx["DiagnosisCode"].astype(str).str.strip().str.upper().isin(
        [c.strip().upper() for c in args.exclude_codes])
    dx = dx[~excluded]

    days = dx["DaysFromIndex"]
    if args.window == "pre":
        keep = days < 0
        if args.lookback_years:
            keep &= days >= -args.lookback_years * 365.25
        dx = dx[keep]
    elif args.window == "post":
        dx = dx[days > 0]

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    people_csv = out / "people_matched.csv"
    events_csv = out / f"diagnosis_events_{args.window}.csv"
    people.to_csv(people_csv, index=False)
    dx.to_csv(events_csv, index=False)

    print(f"people:     {len(people):>8} rows -> {people_csv}")
    print(f"diagnoses:  {n_start:>8} rows in the group files")
    print(f"            {n_in_cohort:>8} rows for matched patients")
    print(f"            {int(excluded.sum()):>8} rows dropped as exposure codes {args.exclude_codes}")
    lookback = f", {args.lookback_years:g}-year lookback" if args.window == "pre" and args.lookback_years else ""
    print(f"            {len(dx):>8} rows kept in window '{args.window}'{lookback} -> {events_csv}")


if __name__ == "__main__":
    main()
