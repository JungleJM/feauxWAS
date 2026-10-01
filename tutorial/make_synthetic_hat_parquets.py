#!/usr/bin/env python3
"""Generate synthetic HaT/control parquet files for the tutorial.

The data are fake, but the columns are shaped like a practical extraction plan:
one patient-level table, one index-event table, diagnosis events, candidate
control pools at multiple ratios, a MatchIt-ready cohort, and an example
matched cohort.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


OUT = Path(__file__).resolve().parent / "synthetic_parquets"
RNG = np.random.default_rng(20260927)

# The real ICD-10-CM code for HaT. It maps to phecode GE_969.4, so it must be
# removed from the PheWAS events (see prepare_phewas_inputs.py).
HAT_ICD = "D89.44"


def random_dates(n: int, start: str, end: str) -> pd.Series:
    start_ts = pd.Timestamp(start).value // 10**9
    end_ts = pd.Timestamp(end).value // 10**9
    vals = RNG.integers(start_ts, end_ts, n)
    return pd.Series(pd.to_datetime(vals, unit="s").normalize())


def make_people(n_cases: int = 200, n_controls: int = 10000) -> pd.DataFrame:
    n = n_cases + n_controls
    hat = np.r_[np.ones(n_cases, dtype=int), np.zeros(n_controls, dtype=int)]
    ids = [f"HAT{i:05d}" for i in range(n_cases)]
    ids += [f"CTRL{i:06d}" for i in range(n_controls)]

    sex = RNG.choice(["Female", "Male"], n, p=[0.64, 0.36])
    race = RNG.choice(
        ["White", "Black", "Asian", "Other", "Unknown"],
        n,
        p=[0.68, 0.12, 0.07, 0.05, 0.08],
    )
    ethnicity = RNG.choice(
        ["Not Hispanic or Latino", "Hispanic or Latino", "Unknown"],
        n,
        p=[0.82, 0.10, 0.08],
    )
    birth_year = RNG.integers(1938, 2006, n)
    index_date = random_dates(n, "2016-01-01", "2025-01-01")
    age = np.clip(index_date.dt.year.to_numpy() - birth_year + RNG.normal(0, 1.8, n), 18, 88)

    # HaT patients are usually identified after more contact with the system.
    years_before = np.clip(RNG.gamma(3.0, 1.5, n) + hat * RNG.gamma(1.2, 0.8, n), 0.1, 12)
    years_after = np.clip(RNG.gamma(2.0, 1.0, n), 0.05, 7)
    visits_pre = RNG.poisson(5 + years_before * 2.4 + hat * 4)
    visits_post = RNG.poisson(3 + years_after * 2.0 + hat * 2)
    dx_pre = RNG.poisson(8 + visits_pre * 1.4)
    problem_count = RNG.poisson(5 + hat * 3 + years_before * 0.7)
    repeated_index_dx = np.where(hat == 1, RNG.integers(2, 7, n), 0)
    mast_cell_prior = np.where(
        hat == 1,
        RNG.binomial(1, 0.28, n),
        RNG.binomial(1, 0.015, n),
    )

    obs_start = index_date - pd.to_timedelta((years_before * 365.25).astype(int), unit="D")
    obs_end = index_date + pd.to_timedelta((years_after * 365.25).astype(int), unit="D")

    df = pd.DataFrame(
        {
            "Patient_ID": ids,
            "HaT_Flag": hat,
            "Sex": sex,
            "Race": race,
            "Ethnicity": ethnicity,
            "BirthYear": birth_year,
            "IndexDate": index_date,
            "IndexYear": index_date.dt.year,
            "IndexQuarter": index_date.dt.to_period("Q").astype(str),
            "AgeAtIndex": np.round(age, 1),
            "ObservationStartDate": obs_start,
            "ObservationEndDate": obs_end,
            "YearsBeforeIndex": np.round(years_before, 2),
            "YearsAfterIndex": np.round(years_after, 2),
            "ClinicVisitCountPreIndex": visits_pre,
            "ClinicVisitCountPostIndex": visits_post,
            "DiagnosisEventCountPreIndex": dx_pre,
            "ProblemListCount": problem_count,
            "RepeatedHaTDiagnosisCount": repeated_index_dx,
            "PriorMastCellDiagnosisFlag": mast_cell_prior,
            "NoKnownHaTDiagnosis": 1 - hat,
        }
    )

    df["EligibleForControlPool"] = (
        (df["HaT_Flag"] == 0)
        & (df["NoKnownHaTDiagnosis"] == 1)
        & (df["YearsBeforeIndex"] >= 1.0)
        & (df["YearsAfterIndex"] >= 0.25)
        & (df["ClinicVisitCountPreIndex"] >= 2)
    ).astype(int)
    return df


def make_index_events(people: pd.DataFrame) -> pd.DataFrame:
    event_type = np.where(people["HaT_Flag"].eq(1), "HaT diagnosis", "pseudo-index encounter")
    index_icd = np.where(people["HaT_Flag"].eq(1), HAT_ICD, "Z00.00")
    definition = np.where(
        people["HaT_Flag"].eq(1),
        "Synthetic HaT case: repeated HaT-like diagnosis flag",
        "Synthetic control: eligible encounter date sampled from source population",
    )
    return pd.DataFrame(
        {
            "Patient_ID": people["Patient_ID"],
            "HaT_Flag": people["HaT_Flag"],
            "IndexDate": people["IndexDate"],
            "AgeAtIndex": people["AgeAtIndex"],
            "IndexEventType": event_type,
            "IndexICD": index_icd,
            "IndexDefinition": definition,
        }
    )


def make_diagnosis_events(people: pd.DataFrame) -> pd.DataFrame:
    rows = []
    background_codes = [
        ("J45.909", "asthma"),
        ("I10", "hypertension"),
        ("K21.9", "GERD"),
        ("G43.909", "migraine"),
        ("L50.9", "urticaria"),
        ("R53.83", "fatigue"),
        ("M79.7", "fibromyalgia"),
        ("R10.9", "abdominal pain"),
        ("F41.9", "anxiety"),
        ("E78.5", "hyperlipidemia"),
    ]
    base_probs = np.array([0.08, 0.12, 0.11, 0.09, 0.06, 0.10, 0.04, 0.08, 0.08, 0.10])
    # Pre-index enrichment: the part of the HaT phenotype present before diagnosis.
    hat_pre = np.array([0.04, 0.00, 0.05, 0.02, 0.12, 0.08, 0.04, 0.05, 0.02, 0.00])
    # Post-index enrichment is larger and different: workup after diagnosis
    # (surveillance) finds more urticaria, fatigue, GI pain and anxiety.
    hat_post = np.array([0.04, 0.00, 0.08, 0.02, 0.20, 0.15, 0.04, 0.10, 0.08, 0.00])
    for row in people.itertuples(index=False):
        windows = [
            ("pre-index", row.ClinicVisitCountPreIndex, hat_pre, -1, row.YearsBeforeIndex),
            ("post-index", row.ClinicVisitCountPostIndex, hat_post, 1, row.YearsAfterIndex),
        ]
        for timing, visits, hat_shift, sign, years in windows:
            n_events = max(1, int(RNG.poisson(3 + visits / 3)))
            probs = base_probs + (hat_shift if row.HaT_Flag else 0)
            probs = probs / probs.sum()
            for ix in RNG.choice(len(background_codes), n_events, p=probs):
                code, label = background_codes[ix]
                days = int(RNG.uniform(10, max(years, 0.2) * 365.25))
                event_date = row.IndexDate + sign * pd.to_timedelta(days, unit="D")
                rows.append((row.Patient_ID, event_date.normalize(), code, "ICD10CM", label, timing))
        if row.HaT_Flag:
            # First HaT code is on the index date; repeats follow within a few months.
            for k in range(int(row.RepeatedHaTDiagnosisCount)):
                days = 0 if k == 0 else int(RNG.uniform(1, 120))
                event_date = row.IndexDate + pd.to_timedelta(days, unit="D")
                rows.append((row.Patient_ID, event_date.normalize(), HAT_ICD, "ICD10CM", "hereditary alpha tryptasemia", "index"))
    return pd.DataFrame(
        rows,
        columns=["Patient_ID", "DiagnosisDate", "DiagnosisCode", "Vocabulary", "DiagnosisLabel", "Timing"],
    )


def make_control_samples(people: pd.DataFrame, n_cases: int) -> dict[str, pd.DataFrame]:
    eligible = people.query("EligibleForControlPool == 1").copy()
    samples = {}
    for ratio in [4, 8, 20, 50]:
        n = min(len(eligible), n_cases * ratio)
        samples[f"candidate_controls_{ratio}x"] = eligible.sample(n=n, random_state=ratio).sort_values("Patient_ID")
    return samples


def make_example_matches(people: pd.DataFrame, ratio: int = 4) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Greedy illustration of 4:1 matching, NOT MatchIt.

    Shows what a matched-pairs file looks like. The real match comes from
    matchit_example.R, which writes matchit_4to1_matched.parquet.
    """
    cases = people.query("HaT_Flag == 1").copy()
    controls = people.query("EligibleForControlPool == 1").copy()
    used = set()
    match_rows = []
    selected_control_ids = set()

    for case in cases.sort_values(["IndexQuarter", "Sex", "Patient_ID"]).itertuples(index=False):
        pool = controls[
            (controls["Sex"] == case.Sex)
            & (controls["IndexQuarter"] == case.IndexQuarter)
            & (~controls["Patient_ID"].isin(used))
        ].copy()
        if pool.empty:
            continue
        pool["MatchDistance"] = (
            (pool["AgeAtIndex"] - case.AgeAtIndex).abs() / 2.0
            + (pool["YearsBeforeIndex"] - case.YearsBeforeIndex).abs() / 2.0
            + (np.log1p(pool["ClinicVisitCountPreIndex"]) - np.log1p(case.ClinicVisitCountPreIndex)).abs()
        )
        picked = pool.sort_values(["MatchDistance", "Patient_ID"]).head(ratio)
        for control in picked.itertuples(index=False):
            used.add(control.Patient_ID)
            selected_control_ids.add(control.Patient_ID)
            match_rows.append(
                {
                    "MatchedSetID": f"SET_{case.Patient_ID}",
                    "CasePatient_ID": case.Patient_ID,
                    "ControlPatient_ID": control.Patient_ID,
                    "ExactSex": case.Sex,
                    "ExactIndexQuarter": case.IndexQuarter,
                    "CaseAgeAtIndex": case.AgeAtIndex,
                    "ControlAgeAtIndex": control.AgeAtIndex,
                    "CaseYearsBeforeIndex": case.YearsBeforeIndex,
                    "ControlYearsBeforeIndex": control.YearsBeforeIndex,
                    "CaseClinicVisitCountPreIndex": case.ClinicVisitCountPreIndex,
                    "ControlClinicVisitCountPreIndex": control.ClinicVisitCountPreIndex,
                    "MatchDistance": round(float(control.MatchDistance), 4),
                }
            )

    matched_ids = set(cases["Patient_ID"]) | selected_control_ids
    matched_cohort = people[people["Patient_ID"].isin(matched_ids)].copy()
    return pd.DataFrame(match_rows), matched_cohort


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    people = make_people()
    n_cases = int(people["HaT_Flag"].sum())
    index_events = make_index_events(people)
    diagnosis_events = make_diagnosis_events(people)
    samples = make_control_samples(people, n_cases)
    matches, matched_cohort = make_example_matches(people)

    people.query("HaT_Flag == 1").to_parquet(OUT / "hat_patients.parquet", index=False)
    people.query("HaT_Flag == 0").to_parquet(OUT / "non_hat_patient_pool.parquet", index=False)
    people.to_parquet(OUT / "all_patients.parquet", index=False)
    index_events.to_parquet(OUT / "index_events.parquet", index=False)
    diagnosis_events.to_parquet(OUT / "diagnosis_events.parquet", index=False)
    people.query("HaT_Flag == 1 or EligibleForControlPool == 1").to_parquet(
        OUT / "match_ready_cohort.parquet", index=False
    )
    matches.to_parquet(OUT / "example_4to1_matches.parquet", index=False)
    matched_cohort.to_parquet(OUT / "example_4to1_matched_cohort.parquet", index=False)

    for name, df in samples.items():
        df.to_parquet(OUT / f"{name}.parquet", index=False)

    dictionary = pd.DataFrame(
        [
            ("Patient_ID", "Stable synthetic patient identifier."),
            ("HaT_Flag", "1 = known HaT case; 0 = no known HaT diagnosis."),
            ("IndexDate", "Case diagnosis date or candidate control pseudo-index date."),
            ("IndexQuarter", "Calendar quarter used for exact 3-month-period matching."),
            ("AgeAtIndex", "Patient age at index date."),
            ("YearsBeforeIndex", "Observation history before index date."),
            ("YearsAfterIndex", "Observation follow-up after index date."),
            ("ClinicVisitCountPreIndex", "Pre-index utilization proxy."),
            ("DiagnosisEventCountPreIndex", "Pre-index diagnosis count. Not used for matching: these diagnoses are the pre-index outcomes."),
            ("ProblemListCount", "Problem-list count. Not used, for the same reason."),
            ("EligibleForControlPool", "Synthetic flag showing basic non-HaT control eligibility."),
        ],
        columns=["Column", "Meaning"],
    )
    dictionary.to_csv(OUT / "data_dictionary.csv", index=False)

    manifest = pd.DataFrame(
        {
            "file": sorted(p.name for p in OUT.glob("*")),
        }
    )
    manifest.to_csv(OUT / "manifest.csv", index=False)
    print(f"Wrote tutorial synthetic parquets to {OUT}")


if __name__ == "__main__":
    main()
