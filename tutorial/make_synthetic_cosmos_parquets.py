#!/usr/bin/env python3
"""Write fake Cosmos pulls shaped like the real ones, for the tutorial.

    synthetic_cosmos/hat/   hat_Patients, hat_Encounters, hat_Diagnoses, hat_Labs
    synthetic_cosmos/ctrl/  ctrl_Patients, ctrl_Encounters, ctrl_Diagnoses, ctrl_Labs

Table and column names match the HaT pull (reference/hat_cosmos_blueprint.yaml),
keeping only the columns study/build_group_parquet.py reads plus each
table's keys. Dates are Cosmos DateKeys (20230517). The data are made up, with
a few patterns planted so each step of the tutorial has something to show:
D89.44 itself (the exposure code), earlier D89.40 codes, single-date cases,
ruled-out diagnoses, cancelled visits, IgE tryptase rows, and more diagnoses
after index than before for HaT patients.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent / "synthetic_cosmos"
RNG = np.random.default_rng(20261003)
N_CASES, N_CONTROLS = 400, 16000           # the real pull: ~6,000 and 300,000
DATA_START, DATA_END = pd.Timestamp("2015-01-01"), pd.Timestamp("2026-06-01")
CODE_START = pd.Timestamp("2021-10-01")    # D89.44 in use

BACKGROUND = ["J45.909", "I10", "K21.9", "G43.909", "L50.9", "R53.83", "M79.7", "R10.9",
              "F41.9", "E78.5"]
BASE_P = np.array([0.08, 0.12, 0.11, 0.09, 0.06, 0.10, 0.04, 0.08, 0.08, 0.10])
HAT_PRE = np.array([0.04, 0.00, 0.05, 0.02, 0.12, 0.08, 0.04, 0.05, 0.02, 0.00])
HAT_POST = np.array([0.04, 0.00, 0.08, 0.02, 0.20, 0.15, 0.04, 0.10, 0.08, 0.00])
ENC_TYPES = ["Office Visit", "Follow-Up", "Telephone", "Refill", "Hospital Outpatient Visit",
             "Emergency", "Hospital Encounter", "Patient Message"]
ENC_P = [0.33, 0.10, 0.20, 0.10, 0.12, 0.05, 0.03, 0.07]


def key(d) -> int:
    return int(pd.Timestamp(d).strftime("%Y%m%d"))


def rand_dates(lo: pd.Timestamp, hi: pd.Timestamp, n: int) -> pd.DatetimeIndex:
    span = max((hi - lo).days, 1)
    return lo + pd.to_timedelta(RNG.integers(0, span, n), unit="D")


def index_dates(is_hat: bool, n: int) -> pd.DatetimeIndex:
    if not is_hat:                                   # a random clinic visit (D30)
        return rand_dates(CODE_START, DATA_END - pd.Timedelta(days=1), n)
    # Cases: a few before the code existed, then more each quarter.
    early = RNG.random(n) < 0.02
    quarters = pd.period_range("2021Q4", "2026Q2", freq="Q")
    w = np.linspace(1.0, 2.0, len(quarters))
    q = RNG.choice(len(quarters), n, p=w / w.sum())
    starts = quarters[q].start_time
    late = starts + pd.to_timedelta(RNG.integers(0, 90, n), unit="D")
    late = late.where(late < DATA_END, DATA_END - pd.Timedelta(days=1))
    return pd.DatetimeIndex(np.where(early, rand_dates(pd.Timestamp("2016-01-01"), CODE_START, n), late))


def patients(prefix: str, ids: np.ndarray, idx: pd.DatetimeIndex) -> pd.DataFrame:
    n, is_hat = len(ids), prefix == "hat"
    age = np.clip(RNG.normal(40 if is_hat else 50, 15 if is_hat else 18, n), 18, 89).round()
    sex = RNG.choice(["Female", "Male"], n, p=[0.76, 0.24] if is_hat else [0.55, 0.45])
    reliable = np.where(RNG.random(n) < 0.02, "Ambiguous", sex)
    race = RNG.choice(["White", "Black or African American", "Asian", "Other Race", "", "*Unspecified"],
                      n, p=[0.78, 0.08, 0.04, 0.03, 0.05, 0.02])
    eth = RNG.choice(["Not Hispanic or Latino", "Hispanic or Latino", "*Unspecified"],
                     n, p=[0.85, 0.08, 0.07])
    birth = idx - pd.to_timedelta((age * 365.25 + RNG.integers(0, 365, n)).astype(int), unit="D")
    death = pd.Series(pd.NaT, index=range(n), dtype="datetime64[ns]")
    dies = RNG.random(n) < 0.01
    death[dies] = (idx[dies] + pd.to_timedelta(RNG.integers(30, 900, dies.sum()), unit="D")).values
    death = death.where(death < DATA_END)
    return pd.DataFrame({
        "PatientDurableKey": ids,
        "IndexDate": [key(d) for d in idx],
        "AgeAtIndex": age.astype(int),
        "Sex": sex, "ReliableSex": reliable,
        "FirstRace": race, "MultiRacial": (RNG.random(n) < 0.03).astype(int),
        "Ethnicity": eth,
        "BirthDate": birth.date, "DeathDate": death.dt.date,
    })


def encounters(prefix: str, pts: pd.DataFrame, idx, start, end) -> pd.DataFrame:
    is_hat = prefix == "hat"
    rows = []
    for pid, i, s, e in zip(pts["PatientDurableKey"], idx, start, end):
        years = (e - s).days / 365.25
        n = RNG.poisson((9 if is_hat else 6) * years) + 2
        dates = rand_dates(s, e, n)
        types = RNG.choice(ENC_TYPES, n, p=ENC_P)
        status = RNG.choice(["Complete", "Canceled", "No Show"], n, p=[0.92, 0.05, 0.03])
        dates = dates.append(pd.DatetimeIndex([s, i]))           # the first visit, and the index visit
        types = np.append(types, ["Office Visit", "Office Visit"])
        status = np.append(status, ["Complete", "Complete"])
        for d, t, st in zip(dates, types, status):
            rows.append((pid, key(d), st, t, int(t == "Emergency"), int(t == "Hospital Encounter")))
    df = pd.DataFrame(rows, columns=["PatientDurableKey", "DateKey", "DerivedEncounterStatus",
                                     "DerivedEncounterType_X", "IsEdVisit", "IsHospitalAdmission"])
    df.insert(1, "EncounterKey", np.arange(len(df)) + (1 if is_hat else 50_000_000))
    return df


def diagnoses(prefix: str, pts: pd.DataFrame, idx, start, end) -> pd.DataFrame:
    is_hat = prefix == "hat"
    rows = []
    for pid, i, s, e in zip(pts["PatientDurableKey"], idx, start, end):
        for lo, hi, shift in [(s, i - pd.Timedelta(days=1), HAT_PRE), (i + pd.Timedelta(days=1), e, HAT_POST)]:
            if hi <= lo:
                continue
            years = (hi - lo).days / 365.25
            n = RNG.poisson(2 + 3 * years)
            p = BASE_P + (shift if is_hat else 0)
            for c, d in zip(RNG.choice(BACKGROUND, n, p=p / p.sum()), rand_dates(lo, hi, n)):
                rows.append((pid, key(d), c))
        if is_hat:
            n_dates = 1 if RNG.random() < 0.38 else RNG.integers(2, 7)   # single-date cases
            for k in range(n_dates):
                d = i if k == 0 else min(i + pd.Timedelta(days=int(RNG.integers(1, 400))), e)
                rows.append((pid, key(d), "D89.44"))
            if RNG.random() < 0.25:                                     # an earlier D89.40
                d = max(i - pd.Timedelta(days=int(RNG.integers(30, 1500))), s)
                rows.append((pid, key(d), "D89.40"))
    df = pd.DataFrame(rows, columns=["PatientDurableKey", "DiagnosisDate", "DiagnosisCode"])
    dup = df.sample(frac=0.10, random_state=1)                          # billing repeats, same day
    df = pd.concat([df, dup], ignore_index=True)
    df["Vocabulary"] = "ICD-10-CM"
    df["DiagnosisStatus"] = RNG.choice(["Active", "Resolved", "Ruled Out"], len(df), p=[0.85, 0.10, 0.05])
    df.loc[df["DiagnosisCode"] == "D89.44", "DiagnosisStatus"] = "Active"
    df.insert(1, "DiagnosisEventKey", np.arange(len(df)) + (1 if is_hat else 80_000_000))
    return df


def labs(prefix: str, pts: pd.DataFrame, idx) -> pd.DataFrame:
    is_hat = prefix == "hat"
    rows = []
    for pid, i in zip(pts["PatientDurableKey"], idx):
        if RNG.random() < (0.55 if is_hat else 0.01):
            for _ in range(RNG.integers(1, 4)):
                d = min(i + pd.Timedelta(days=int(RNG.integers(-200, 300))), DATA_END)
                v = RNG.lognormal(np.log(12 if is_hat else 5), 0.3)
                rows.append((pid, 2287, key(d), round(v, 1), "ng/mL", 0))
        if is_hat and RNG.random() < 0.10:                               # IgE to tryptase: not a level
            rows.append((pid, 8166, key(i), round(RNG.uniform(0, 1), 2), "kU/L", 0))
        if RNG.random() < 0.01:
            rows.append((pid, 2287, key(i), None, "ng/mL", 1))           # an unsuccessful draw
    df = pd.DataFrame(rows, columns=["PatientDurableKey", "LabComponentKey", "PrioritizedDateKey",
                                     "NumericValue", "Unit", "IsBlankOrUnsuccessfulAttempt"])
    df.insert(1, "LabComponentResultKey", np.arange(len(df)) + 1)
    return df


def write_pull(prefix: str, n: int, first_id: int) -> None:
    ids = np.arange(n) + first_id
    idx = index_dates(prefix == "hat", n)
    pts = patients(prefix, ids, idx)
    before = np.clip(RNG.gamma(3.0, 1.5, n) + (prefix == "hat") * RNG.gamma(1.2, 0.8, n), 0.3, 12)
    after = np.clip(RNG.gamma(2.0, 1.0, n), 0.05, 7)
    start = pd.Series(idx - pd.to_timedelta((before * 365.25).astype(int), unit="D")).clip(lower=DATA_START)
    end = pd.Series(idx + pd.to_timedelta((after * 365.25).astype(int), unit="D")).clip(upper=DATA_END)
    folder = OUT / prefix
    folder.mkdir(parents=True, exist_ok=True)
    pts.to_parquet(folder / f"{prefix}_Patients.parquet", index=False)
    encounters(prefix, pts, idx, start, end).to_parquet(folder / f"{prefix}_Encounters.parquet", index=False)
    diagnoses(prefix, pts, idx, start, end).to_parquet(folder / f"{prefix}_Diagnoses.parquet", index=False)
    labs(prefix, pts, idx).to_parquet(folder / f"{prefix}_Labs.parquet", index=False)
    print(f"wrote {folder}: {n:,} patients")


def main() -> None:
    write_pull("hat", N_CASES, 10_000_000)
    write_pull("ctrl", N_CONTROLS, 20_000_000)


if __name__ == "__main__":
    main()
