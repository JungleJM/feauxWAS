#!/usr/bin/env python3
"""Turn one Telescope pull's parquets into the two files the study runs on.

Put this script in the folder with the pull's parquets and run it:

    python build_group_parquet.py              # finds hat_* or ctrl_* by itself
    python build_group_parquet.py --dir PATH   # parquets somewhere else

It reads <p>_Patients, <p>_Encounters, <p>_Diagnoses and <p>_Labs (p = hat or
ctrl) and writes, beside them:

    hat_group.parquet               one row per patient: what matching needs
    hat_group_diagnoses.parquet     one row per patient, ICD-10-CM code and date
    hat_group_report.txt            counts and value lists, to check by eye
    hat_patient_keys.parquet        (hat only) the keys to upload to the ctrl_ pull

or control_group.parquet and friends for ctrl_. The walkthrough is README.md;
the study's choices it applies are in reference/plan/decisions.md (D-numbers
below). Needs pandas and pyarrow only.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

HAT_CODE = "D89.44"
MAST_CELL_PREFIX = "D89.4"                       # D89.40-D89.49
CLINIC_TYPES = {"Office Visit", "Follow-Up"}     # D31
COMPLETE = "Complete"
TRYPTASE_BASELINE = {2287, 59082}                # serum tryptase, ng/mL
DROP_STATUS_WORDS = ("rule", "error", "delete", "cancel")  # dropped DiagnosisStatus values
D8944_FIRST_USABLE = pd.Timestamp("2021-10-01")  # cases before this get no controls (D30)

PATIENT_COLS = ["PatientDurableKey", "IndexDate", "AgeAtIndex", "Sex", "ReliableSex",
                "FirstRace", "MultiRacial", "Ethnicity", "BirthDate", "DeathDate"]
ENCOUNTER_COLS = ["PatientDurableKey", "DateKey", "DerivedEncounterStatus",
                  "DerivedEncounterType_X", "IsEdVisit", "IsHospitalAdmission"]
DIAGNOSIS_COLS = ["PatientDurableKey", "DiagnosisDate", "DiagnosisCode", "Vocabulary",
                  "DiagnosisStatus"]
LAB_COLS = ["PatientDurableKey", "LabComponentKey", "PrioritizedDateKey", "NumericValue",
            "Unit", "IsBlankOrUnsuccessfulAttempt"]


def datekey(s: pd.Series) -> pd.Series:
    """Cosmos DateKeys (20230517) to dates; negative or odd keys become NaT."""
    s = pd.to_numeric(s, errors="coerce")
    s = s.where(s > 19000000)
    return pd.to_datetime(s.astype("Int64").astype(str), format="%Y%m%d", errors="coerce")


def unknown_if_blank(s: pd.Series) -> pd.Series:
    """Blank, missing and '*'-prefixed values ('*Unspecified') become Unknown (D10)."""
    t = s.astype("string").str.strip()
    bad = t.isna() | (t == "") | t.str.startswith("*")
    return t.mask(bad, "Unknown")


def read(folder: Path, prefix: str, table: str, cols: list[str]) -> pd.DataFrame:
    path = folder / f"{prefix}_{table}.parquet"
    if not path.exists():
        raise SystemExit(f"Missing {path.name}. Put this script beside the pull's parquets, "
                         f"or point --dir at them.")
    have = set(pq.read_schema(path).names)
    missing = [c for c in cols if c not in have]
    if missing:
        raise SystemExit(f"{path.name} lacks column(s) {missing}. Was it pulled from the "
                         f"study's blueprint?")
    return pd.read_parquet(path, columns=cols)


def count_days(events: pd.DataFrame, index: pd.Series, lo: int, hi: int) -> pd.Series:
    """Distinct event dates per patient with lo <= (date - index) days < hi."""
    days = (events["Date"] - events["PatientDurableKey"].map(index)).dt.days
    hit = events[(days >= lo) & (days < hi)]
    return hit.groupby("PatientDurableKey")["Date"].nunique()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", type=Path, default=Path(__file__).resolve().parent,
                    help="folder with the pull's parquets (default: this script's folder)")
    ap.add_argument("--prefix", choices=["hat", "ctrl"],
                    help="which pull (default: whichever *_Patients.parquet is there)")
    ap.add_argument("--data-end", default="2026-06-01",
                    help="last date in the pull (max_date_key); ends observation")
    args = ap.parse_args()
    folder = args.dir

    prefix = args.prefix
    if prefix is None:
        found = [p for p in ("hat", "ctrl") if (folder / f"{p}_Patients.parquet").exists()]
        if len(found) != 1:
            raise SystemExit(f"Found {found or 'no'} *_Patients.parquet in {folder}; "
                             f"say which with --prefix hat or --prefix ctrl.")
        prefix = found[0]
    is_hat = prefix == "hat"
    group = "hat" if is_hat else "control"
    report: list[str] = [f"{group} group, built from {folder}"]
    say = report.append

    # 1. Read only the columns the study uses.
    pts = read(folder, prefix, "Patients", PATIENT_COLS)
    enc = read(folder, prefix, "Encounters", ENCOUNTER_COLS)
    dx = read(folder, prefix, "Diagnoses", DIAGNOSIS_COLS)
    labs = read(folder, prefix, "Labs", LAB_COLS)
    say(f"read: {len(pts):,} patients, {len(enc):,} encounters, {len(dx):,} diagnosis rows, "
        f"{len(labs):,} lab rows")

    # 2. Diagnoses: drop ruled-out and error statuses, then one row per patient, code, date.
    say("\nDiagnosisStatus values (dropped ones marked x):")
    status = dx["DiagnosisStatus"].astype("string").fillna("(blank)")
    drop = status.str.lower().str.contains("|".join(DROP_STATUS_WORDS), regex=True)
    for value, n in status.value_counts().items():
        mark = "x" if any(w in value.lower() for w in DROP_STATUS_WORDS) else " "
        say(f"  {mark} {value}: {n:,}")
    dx = dx[~drop].copy()
    dx["Date"] = datekey(dx["DiagnosisDate"])
    dx["DiagnosisCode"] = dx["DiagnosisCode"].astype("string").str.strip().str.upper()
    dx = (dx.dropna(subset=["Date", "DiagnosisCode"])
            .drop_duplicates(["PatientDurableKey", "DiagnosisCode", "Date"]))
    say(f"diagnoses kept: {len(dx):,} patient-code-date rows")

    # 3. Index date. Cases: the first D89.44 that survived the status filter (D4, D24);
    #    the PK's IndexDate took any status. Controls: their sampled clinic visit (D30).
    pts = pts.drop_duplicates("PatientDurableKey").set_index("PatientDurableKey")
    pk_index = datekey(pts["IndexDate"])
    hat_dx = dx[dx["DiagnosisCode"] == HAT_CODE]
    hat_dates = hat_dx.groupby("PatientDurableKey")["Date"]
    if is_hat:
        index = hat_dates.min().reindex(pts.index)
        moved = (index != pk_index) & index.notna()
        lost = index.isna()
        say(f"index: {moved.sum():,} cases moved to a later D89.44 by the status filter; "
            f"{lost.sum():,} had no D89.44 left and are dropped")
        index = index[~lost]
        # Cosmos's age is at the PK's index; add the years the index moved.
        shift = ((index - pk_index.reindex(index.index)).dt.days // 365).fillna(0)
        age = pd.to_numeric(pts["AgeAtIndex"], errors="coerce").reindex(index.index) + shift
    else:
        index = pk_index.dropna()
        age = pd.to_numeric(pts["AgeAtIndex"], errors="coerce").reindex(index.index)
        with_hat = hat_dates.size()
        if len(with_hat):
            say(f"controls with a D89.44 in their diagnoses, dropped: {len(with_hat):,}")
            index = index.drop(with_hat.index, errors="ignore")
            age = age.reindex(index.index)

    out = pd.DataFrame(index=index.index)
    out["Group"] = group
    out["HaT_Flag"] = int(is_hat)
    out["IndexDate"] = index
    out["IndexYear"] = index.dt.year
    out["IndexQuarter"] = index.dt.to_period("Q").astype(str)
    out["AgeAtIndex"] = age
    out["IndexBeforeD8944Existed"] = (index < D8944_FIRST_USABLE).astype(int)

    # 4. Demographics (D10, D25).
    p = pts.reindex(out.index)
    reliable = p["ReliableSex"].astype("string")
    admin = p["Sex"].astype("string")
    sex = reliable.where(reliable.isin(["Female", "Male"]), admin)
    out["Sex"] = sex.where(sex.isin(["Female", "Male"]))      # anything else: missing
    out["Race"] = unknown_if_blank(p["FirstRace"])
    out["MultiRacial"] = pd.to_numeric(p["MultiRacial"], errors="coerce")
    out["Ethnicity"] = unknown_if_blank(p["Ethnicity"])
    out["BirthDate"] = pd.to_datetime(p["BirthDate"], errors="coerce")
    out["DeathDate"] = pd.to_datetime(p["DeathDate"], errors="coerce")
    say(f"\nsex: {out['Sex'].value_counts(dropna=False).to_dict()}")
    say(f"race: {out['Race'].value_counts().to_dict()}")
    say(f"ethnicity: {out['Ethnicity'].value_counts().to_dict()}")

    # 5. Observation time and visits, from completed encounters (D8, D31).
    say(f"\nencounter statuses: {enc['DerivedEncounterStatus'].value_counts().to_dict()}")
    enc = enc[enc["DerivedEncounterStatus"] == COMPLETE].copy()
    enc["Date"] = datekey(enc["DateKey"])
    enc = enc.dropna(subset=["Date"])
    first = enc.groupby("PatientDurableKey")["Date"].min()
    last = enc.groupby("PatientDurableKey")["Date"].max()
    data_end = pd.Timestamp(args.data_end)
    out["ObservationStartDate"] = first.reindex(out.index)
    end = pd.concat([last.reindex(out.index), out["DeathDate"]], axis=1).min(axis=1)
    out["ObservationEndDate"] = end.clip(upper=data_end)
    out["YearsBeforeIndex"] = (out["IndexDate"] - out["ObservationStartDate"]).dt.days / 365.25
    out["YearsAfterIndex"] = (out["ObservationEndDate"] - out["IndexDate"]).dt.days / 365.25

    clinic = enc[enc["DerivedEncounterType_X"].isin(CLINIC_TYPES)]
    ed = enc[pd.to_numeric(enc["IsEdVisit"], errors="coerce") == 1]
    adm = enc[pd.to_numeric(enc["IsHospitalAdmission"], errors="coerce") == 1]
    for name, events, lo, hi in [("ClinicVisits365Before", clinic, -365, 0),
                                 ("ClinicVisits365After", clinic, 1, 366),
                                 ("EdVisits365Before", ed, -365, 0),
                                 ("Admissions365Before", adm, -365, 0)]:
        out[name] = count_days(events, out["IndexDate"], lo, hi).reindex(out.index).fillna(0).astype(int)

    # 6. HaT codes: D89.44 dates (the 2+ sensitivity analysis, D24) and an earlier
    #    mast-cell code (Attending Questions, question 1).
    out["HaTDateCount"] = hat_dates.nunique().reindex(out.index).fillna(0).astype(int)
    mc = dx[dx["DiagnosisCode"].str.startswith(MAST_CELL_PREFIX) & (dx["DiagnosisCode"] != HAT_CODE)]
    mc = mc[mc["Date"] < mc["PatientDurableKey"].map(out["IndexDate"])]
    mc_first = mc.sort_values("Date").drop_duplicates("PatientDurableKey").set_index("PatientDurableKey")
    out["EarlierMastCellCode"] = mc_first["DiagnosisCode"].reindex(out.index)
    out["EarlierMastCellCodeDate"] = mc_first["Date"].reindex(out.index)

    # 7. Tryptase: baseline serum results in ng/mL only (HaT Considerations).
    labs = labs[labs["LabComponentKey"].isin(TRYPTASE_BASELINE)
                & labs["Unit"].astype("string").str.lower().str.strip().eq("ng/ml")
                & (pd.to_numeric(labs["IsBlankOrUnsuccessfulAttempt"], errors="coerce").fillna(0) != 1)].copy()
    labs["Date"] = datekey(labs["PrioritizedDateKey"])
    labs = labs.dropna(subset=["NumericValue"])
    t = labs.groupby("PatientDurableKey")
    out["TryptaseCount"] = t.size().reindex(out.index).fillna(0).astype(int)
    out["TryptaseMax"] = t["NumericValue"].max().reindex(out.index)
    tf = labs.sort_values("Date").drop_duplicates("PatientDurableKey").set_index("PatientDurableKey")
    out["TryptaseFirst"] = tf["NumericValue"].reindex(out.index)
    out["TryptaseFirstDate"] = tf["Date"].reindex(out.index)

    # 8. Eligibility for matching (D8): two clinic visits in the year before index,
    #    a known sex, and (cases) an index from when D89.44 existed.
    out["EligibleForMatching"] = ((out["ClinicVisits365Before"] >= 2)
                                  & out["Sex"].notna()
                                  & (out["IndexBeforeD8944Existed"] == 0)).astype(int)

    # 9. Write.
    out = out.reset_index()
    diag = dx[dx["PatientDurableKey"].isin(out["PatientDurableKey"])]
    diag = diag.assign(DiagnosisDate=diag["Date"],
                       DaysFromIndex=(diag["Date"] - diag["PatientDurableKey"].map(
                           out.set_index("PatientDurableKey")["IndexDate"])).dt.days)
    diag = diag[["PatientDurableKey", "DiagnosisCode", "Vocabulary", "DiagnosisDate", "DaysFromIndex"]]

    out.to_parquet(folder / f"{group}_group.parquet", index=False)
    diag.to_parquet(folder / f"{group}_group_diagnoses.parquet", index=False)
    if is_hat:
        out[["PatientDurableKey"]].to_parquet(folder / "hat_patient_keys.parquet", index=False)

    say(f"\nwrote {group}_group.parquet: {len(out):,} patients, "
        f"{out['EligibleForMatching'].sum():,} eligible for matching")
    say(f"  not eligible: {(out['ClinicVisits365Before'] < 2).sum():,} with under 2 clinic visits "
        f"in the year before index; {out['Sex'].isna().sum():,} with no usable sex; "
        f"{out['IndexBeforeD8944Existed'].sum():,} indexed before 2021-10-01")
    say(f"wrote {group}_group_diagnoses.parquet: {len(diag):,} rows")
    if is_hat:
        say(f"  {(out['HaTDateCount'] >= 2).sum():,} with D89.44 on 2+ dates; "
            f"{out['EarlierMastCellCode'].notna().sum():,} with an earlier D89.4x; "
            f"{(out['TryptaseCount'] > 0).sum():,} with a baseline tryptase")
        say("wrote hat_patient_keys.parquet: upload it to the ctrl_ pull")
    text = "\n".join(report)
    (folder / f"{group}_group_report.txt").write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
