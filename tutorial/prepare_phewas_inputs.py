#!/usr/bin/env python3
"""Turn a matched cohort and a diagnosis-event table into pheauxWAS input CSVs.

This is the step between matching and the PheWAS. It does three things that
pheauxWAS cannot do itself:

1. Keeps only events from people in the matched cohort.
2. Drops the codes that define the exposure (HaT = D89.44). Otherwise the
   exposure code maps to its own phecode (GE_969.4) and comes back as a
   guaranteed, meaningless top hit.
3. Keeps only events in the chosen time window relative to each person's
   index date. pheauxWAS counts every event it is given, so the window has to
   be applied here.

Windows (index day itself is left out of pre and post, since codes entered on
the diagnosis day are usually part of the HaT workup):
    pre   events before the index date: phenotypes present before diagnosis
    post  events after the index date: includes post-diagnosis workup
    all   every event, any date

--lookback-years N limits pre to the N years before index, so everyone gets the
same window (the HaT study uses 3). It is ignored for post and all.

Dates may be real dates or Cosmos DateKeys (integers like 20260129).

Example, from the repo root:

    python3 tutorial/prepare_phewas_inputs.py \
        --cohort tutorial/synthetic_parquets/matchit_4to1_matched.parquet \
        --events tutorial/synthetic_parquets/diagnosis_events.parquet \
        --window pre --lookback-years 3 \
        --out-dir tutorial/work
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def to_date(s: pd.Series) -> pd.Series:
    """Parse real dates or integer DateKeys (YYYYMMDD) into datetimes."""
    if pd.api.types.is_numeric_dtype(s):
        return pd.to_datetime(s.astype("Int64").astype(str), format="%Y%m%d", errors="coerce")
    return pd.to_datetime(s, errors="coerce")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cohort", required=True, help="matched cohort parquet, one row per patient")
    ap.add_argument("--events", required=True, help="diagnosis-event parquet, one row per event")
    ap.add_argument("--window", choices=["pre", "post", "all"], required=True)
    ap.add_argument("--lookback-years", type=float,
                    help="with --window pre: keep only events this many years before index")
    ap.add_argument("--exclude-codes", nargs="+", default=["D89.44"],
                    help="exposure-defining ICD codes to drop (default: D89.44)")
    ap.add_argument("--id-col", default="Patient_ID")
    ap.add_argument("--index-col", default="IndexDate")
    ap.add_argument("--date-col", default="DiagnosisDate")
    ap.add_argument("--code-col", default="DiagnosisCode")
    ap.add_argument("--out-dir", default="tutorial/work")
    args = ap.parse_args()

    people = pd.read_parquet(args.cohort)
    events = pd.read_parquet(args.events)
    n_start = len(events)

    events = events[events[args.id_col].isin(people[args.id_col])]
    n_in_cohort = len(events)

    excluded = events[args.code_col].astype(str).str.strip().str.upper().isin(
        [c.strip().upper() for c in args.exclude_codes])
    events = events[~excluded]

    index = people.set_index(args.id_col)[args.index_col].pipe(to_date)
    days = (to_date(events[args.date_col]) - events[args.id_col].map(index)).dt.days
    if args.window == "pre":
        keep = days < 0
        if args.lookback_years:
            keep &= days >= -args.lookback_years * 365.25
        events = events[keep]
    elif args.window == "post":
        events = events[days > 0]

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    people_csv = out / "hat_people_matched.csv"
    events_csv = out / f"hat_diagnosis_events_{args.window}.csv"
    people.to_csv(people_csv, index=False)
    events.to_csv(events_csv, index=False)

    print(f"people:  {len(people):>8} rows -> {people_csv}")
    print(f"events:  {n_start:>8} rows in source")
    print(f"         {n_in_cohort:>8} rows for cohort members")
    print(f"         {int(excluded.sum()):>8} rows dropped as exposure codes {args.exclude_codes}")
    lookback = f", {args.lookback_years:g}-year lookback" if args.window == "pre" and args.lookback_years else ""
    print(f"         {len(events):>8} rows kept in window '{args.window}'{lookback} -> {events_csv}")


if __name__ == "__main__":
    main()
