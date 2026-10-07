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
the study's choices it applies are in docs/plan/decisions.md (D-numbers
below). Needs pandas and pyarrow only.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
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
    """Cosmos DateKeys (20230517) to dates; negative or odd keys become NaT.

    Parses each distinct key once and maps it back: a string per row runs out of
    memory on the control pull's diagnoses.
    """
    s = pd.to_numeric(s, errors="coerce").astype("float64")
    s = s.where((s > 19000000) & (s % 1 == 0))
    codes, keys = pd.factorize(s)                    # missing keys get code -1
    dates = pd.to_datetime(pd.Series(keys, dtype="int64").astype(str),
                           format="%Y%m%d", errors="coerce").to_numpy()
    dates = np.append(dates, np.array(["NaT"], dtype=dates.dtype))  # code -1 picks this NaT
    return pd.Series(dates[codes], index=s.index)


def unknown_if_blank(s: pd.Series) -> pd.Series:
    """Blank, missing and '*'-prefixed values ('*Unspecified') become Unknown (D10)."""
    t = s.astype("string").str.strip()
    bad = t.isna() | (t == "") | t.str.startswith("*")
    return t.mask(bad, "Unknown")


def tidy(s: pd.Series, fn) -> pd.Series:
    """Apply fn to each distinct value of a categorical, not to every row (memory)."""
    clean = fn(pd.Series(s.cat.categories, dtype="string")).to_numpy(dtype=object)
    remap, cats = pd.factorize(clean)                # two values may tidy to one
    codes = s.cat.codes.to_numpy()
    return pd.Series(pd.Categorical.from_codes(np.where(codes >= 0, remap[codes], -1), cats),
                     index=s.index)


def matching(s: pd.Series, keep) -> pd.Series:
    """Rows of a categorical whose value passes keep(value), tested once per value."""
    return s.isin([c for c in s.cat.categories if keep(c)])


def table_path(folder: Path, prefix: str, table: str, cols: list[str]) -> Path:
    """The pull's parquet for table, checked to exist and to have cols."""
    path = folder / f"{prefix}_{table}.parquet"
    if not path.exists():
        raise SystemExit(f"Missing {path.name}. Put this script beside the pull's parquets, "
                         f"or point --dir at them.")
    have = set(pq.read_schema(path).names)
    missing = [c for c in cols if c not in have]
    if missing:
        raise SystemExit(f"{path.name} lacks column(s) {missing}. Was it pulled from the "
                         f"study's blueprint?")
    return path


def read(folder: Path, prefix: str, table: str, cols: list[str],
         text: list[str] = ()) -> pd.DataFrame:
    """Read cols; the text columns come back categorical, each value stored once."""
    path = table_path(folder, prefix, table, cols)
    return pq.read_table(path, columns=cols, read_dictionary=list(text)).to_pandas(
        self_destruct=True, split_blocks=True)


def count_days(events: pd.DataFrame, index: pd.Series, lo: int, hi: int) -> pd.Series:
    """Distinct event dates per patient with lo <= (date - index) days < hi."""
    days = (events["Date"] - events["PatientDurableKey"].map(index)).dt.days
    hit = events[(days >= lo) & (days < hi)]
    return hit.groupby("PatientDurableKey")["Date"].nunique()


DAY0 = np.datetime64("1900-01-01", "D")
DAY_BITS, CODE_BITS = 17, 20         # a key: patient, then code, then day since DAY0
DATE_DTYPE = datekey(pd.Series([20000101])).dtype   # how this pandas holds a date


class Diagnoses:
    """The kept diagnoses, one int64 key each (patient number, code number, day) and
    a vocabulary number, in the order read. Stored so, the control pull's 92 million
    rows take about 10 bytes each; as a DataFrame they ran out of memory."""

    def __init__(self, patients: pd.Index, keys, vocab, codes: list, vocabs: list):
        self.patients, self.keys, self.vocab = patients, keys, vocab
        self.codes, self.vocabs = codes, vocabs

    def __len__(self) -> int:
        return len(self.keys)

    def code_numbers(self) -> np.ndarray:
        out = np.empty(len(self.keys), dtype="int32")
        for i in range(0, len(self.keys), 10_000_000):        # int64 scratch, a slice at a time
            out[i:i + 10_000_000] = (self.keys[i:i + 10_000_000] >> DAY_BITS) & ((1 << CODE_BITS) - 1)
        return out

    def with_codes(self, keep) -> pd.DataFrame:
        """The rows whose code passes keep(code)."""
        wanted = [i for i, c in enumerate(self.codes) if keep(c)]
        return self.rows(np.flatnonzero(np.isin(self.code_numbers(), wanted)))

    def rows(self, at) -> pd.DataFrame:
        """Rows at these positions (a slice or an index array), as a DataFrame."""
        k, v = self.keys[at], self.vocab[at]
        days = (k & ((1 << DAY_BITS) - 1)).astype("timedelta64[D]")
        return pd.DataFrame({
            "PatientDurableKey": self.patients[k >> (CODE_BITS + DAY_BITS)].to_numpy(),
            "DiagnosisCode": pd.Categorical.from_codes(
                ((k >> DAY_BITS) & ((1 << CODE_BITS) - 1)).astype("int32"),
                pd.Index(self.codes, dtype=object)),
            "Vocabulary": pd.Categorical.from_codes(v, pd.Index(self.vocabs, dtype=object)),
            "Date": (DAY0 + days).astype(DATE_DTYPE)})


def number(s: pd.Series, numbers: dict) -> np.ndarray:
    """Each row's value as its number in numbers (new values added); missing is -1."""
    cat = s.astype("category")
    of_value = np.array([numbers.setdefault(v, len(numbers)) for v in cat.cat.categories]
                        + [-1], dtype="int64")             # code -1 (missing) picks the -1
    return of_value[cat.cat.codes.to_numpy()]


def read_diagnoses(path: Path, patients: pd.Index, say,
                   chunk_rows: int = 5_000_000, bucket_rows: int = 10_000_000) -> Diagnoses:
    """The diagnoses of these patients, ruled-out and error statuses dropped, one row
    per patient, code and date (the first read kept), in the order read.

    Read a chunk at a time and packed into Diagnoses' keys; the text is tested and
    tidied once per distinct value, not per row.
    """
    dropped = lambda v: any(w in v.lower() for w in DROP_STATUS_WORDS)
    status_counts: dict[str, int] = {}
    codes: dict[str, int] = {}
    vocabs: dict[str, int] = {}
    n = pq.read_metadata(path).num_rows
    keys, vocab, m, unknown = np.empty(n, dtype="int64"), np.empty(n, dtype="int16"), 0, 0
    text = ["DiagnosisCode", "Vocabulary", "DiagnosisStatus"]
    for batch in pq.ParquetFile(path, read_dictionary=text).iter_batches(
            batch_size=chunk_rows, columns=DIAGNOSIS_COLS):
        dx = batch.to_pandas()
        for value, c in dx["DiagnosisStatus"].value_counts(dropna=False).items():
            value = "(blank)" if pd.isna(value) else value
            status_counts[value] = status_counts.get(value, 0) + c
        dx = dx[~matching(dx["DiagnosisStatus"], dropped)]
        code = number(tidy(dx["DiagnosisCode"], lambda c: c.str.strip().str.upper()), codes)
        date = datekey(dx["DiagnosisDate"]).to_numpy()
        day = (date.astype("datetime64[D]") - DAY0).astype("int64")
        who = patients.get_indexer(dx["PatientDurableKey"])
        ok = (code >= 0) & ~np.isnat(date)
        if (day[ok] >= 1 << DAY_BITS).any():
            raise SystemExit(f"{path.name} has a DiagnosisDate after 2258 "
                             f"({dx['DiagnosisDate'][ok][day[ok] >= 1 << DAY_BITS].iloc[0]}); "
                             f"filter such placeholder dates out, or widen DAY_BITS.")
        unknown += int((ok & (who < 0)).sum())
        ok &= who >= 0
        k = (who[ok] << (CODE_BITS + DAY_BITS)) | (code[ok] << DAY_BITS) | day[ok]
        first = ~pd.Series(k).duplicated().to_numpy()
        keys[m:m + first.sum()] = k[first]
        vocab[m:m + first.sum()] = number(dx["Vocabulary"], vocabs)[ok][first]
        m += first.sum()
        del dx, code, date, day, who, ok, k, first
    if len(codes) >= 1 << CODE_BITS or len(patients) >= 1 << (63 - CODE_BITS - DAY_BITS):
        raise SystemExit(f"{len(codes):,} codes or {len(patients):,} patients overflow a "
                         f"diagnosis key; widen CODE_BITS in build_group_parquet.py.")

    # Duplicates across chunks, a range of patients at a time so the hash stays small.
    keys, vocab = keys[:m], vocab[:m]
    dup = np.zeros(m, dtype=bool)
    shift = CODE_BITS + DAY_BITS
    buckets = max(1, -(-m // bucket_rows))
    for b in range(buckets):
        lo, hi = len(patients) * b // buckets, len(patients) * (b + 1) // buckets
        at = np.flatnonzero((keys >= lo << shift) & (keys < hi << shift))
        dup[at] = pd.Series(keys[at]).duplicated().to_numpy()
    keys, vocab = keys[~dup], vocab[~dup]

    say("\nDiagnosisStatus values (dropped ones marked x):")
    for value, c in sorted(status_counts.items(), key=lambda kv: -kv[1]):
        say(f"  {'x' if dropped(value) else ' '} {value}: {c:,}")
    if unknown:
        say(f"diagnosis rows of patients not in Patients, dropped: {unknown:,}")
    return Diagnoses(patients, keys, vocab, list(codes), list(vocabs))


def write_diagnoses(dx: Diagnoses, index: pd.Series, path: Path,
                    chunk_rows: int = 5_000_000) -> int:
    """Write the diagnoses of the patients in index, with days from their index date,
    a chunk at a time; return the rows written."""
    writer, written = None, 0
    for i in range(0, max(len(dx), 1), chunk_rows):
        diag = dx.rows(slice(i, i + chunk_rows))
        diag = diag[diag["PatientDurableKey"].isin(index.index)]
        diag = diag.assign(DiagnosisDate=diag["Date"],
                           DaysFromIndex=(diag["Date"] - diag["PatientDurableKey"].map(index)).dt.days)
        diag = diag[["PatientDurableKey", "DiagnosisCode", "Vocabulary", "DiagnosisDate", "DaysFromIndex"]]
        diag = diag.astype({"DiagnosisCode": "string", "Vocabulary": object})
        table = pa.Table.from_pandas(diag, schema=writer and writer.schema, preserve_index=False)
        writer = writer or pq.ParquetWriter(path, table.schema)
        writer.write_table(table)
        written += len(diag)
    writer.close()
    return written


def selftest() -> None:
    """Checks of what ends up in the output; run with --selftest."""
    import tracemalloc
    s = pd.Series([20230517, -1, 20231399, None, 20230517, 20240229], index=[5, 3, 9, 1, 2, 7])
    got = datekey(s)
    want = pd.to_datetime(["2023-05-17", None, None, None, "2023-05-17", "2024-02-29"])
    assert got.index.equals(s.index) and got.tolist() == want.tolist(), got
    assert datekey(pd.Series(["20230517", "x"])).tolist()[0] == pd.Timestamp("2023-05-17")
    assert datekey(pd.Series([], dtype="int64")).empty
    # The control pull's diagnoses ran out of memory with a string per row (~110-160
    # bytes a row); parsing each distinct key once takes ~33.
    n = 1_000_000
    many = pd.Series(20150101 + np.arange(n) % 28)
    tracemalloc.start()
    got = datekey(many)
    peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    assert peak / n < 64, f"datekey used {peak / n:.0f} bytes a row"
    assert got.iloc[27] == pd.Timestamp("2015-01-28") and got.notna().all()

    # Diagnoses, read in chunks of 4 and deduplicated in patient ranges of 5, against
    # the plain per-row version: statuses dropped, codes tidied (' d89.44' is D89.44),
    # the first of each patient, code and date kept with its Vocabulary, and the
    # rows of patients not in Patients dropped.
    import tempfile
    raw = pd.DataFrame({
        "PatientDurableKey": [7, 7, 9, 7, 3, 9, 9, 7, 3, 11, 9, 3, 7, 9],
        "DiagnosisDate": [20230517, 20230517, 20230101, 20230517, 20220202, 20230101, -1,
                          20240301, 20220202, 20230101, 20230102, 20220203, 20230517, 20230101],
        "DiagnosisCode": ["D89.44", " d89.44", "J45.909", "D89.44", "D89.40", "J45.909 ", "J45.909",
                          "D89.44", "d89.40", None, "J45.909", "D89.40", "D89.44", "J45.909"],
        "Vocabulary": ["ICD-10-CM", "first-of-dup?", "ICD-10-CM", "x", "ICD-10-CM", "y", "ICD-10-CM",
                       "ICD-10-CM", "z", "ICD-10-CM", None, "ICD-10-CM", "ICD-10-CM", "ICD-10-CM"],
        "DiagnosisStatus": ["Active", "Active", "Ruled Out", "Active", None, "Active", "Active",
                            "Entered in Error", "Active", "Active", "Active", "Active", "Resolved", "Active"]})
    patients = pd.Index([3, 7, 9], name="PatientDurableKey")
    want = raw.copy()
    want = want[~want["DiagnosisStatus"].fillna("").str.lower().str.contains("rule|error|delete|cancel")]
    want["Date"] = datekey(want["DiagnosisDate"])
    want["DiagnosisCode"] = want["DiagnosisCode"].str.strip().str.upper()
    want = (want[want["PatientDurableKey"].isin(patients)]
            .dropna(subset=["Date", "DiagnosisCode"])
            .drop_duplicates(["PatientDurableKey", "DiagnosisCode", "Date"]))
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "dx.parquet"
        raw.to_parquet(path, index=False)
        lines: list[str] = []
        dx = read_diagnoses(path, patients, lines.append, chunk_rows=4, bucket_rows=5)
        got = dx.rows(slice(None))
        same = lambda c: [None if pd.isna(v) else v for v in c.astype(object)]
        for col in ["PatientDurableKey", "DiagnosisCode", "Vocabulary", "Date"]:
            assert same(got[col]) == same(want[col]), (col, got, want)
        assert dx.with_codes(lambda c: c == "D89.44")["Date"].tolist() == [pd.Timestamp("2023-05-17")]
        assert "  x Ruled Out: 1" in lines and "    (blank): 1" in lines, lines
        assert "diagnosis rows of patients not in Patients, dropped: 0" not in lines
        # None of 11's rows survive (its code is missing), so nothing is reported dropped.

        # Memory: the control pull's 92 million diagnoses ran out of memory as a
        # DataFrame (several hundred bytes a row); packed, a row takes ~25 at the peak
        # (in small chunks, so the chunk's own scratch doesn't count as per row).
        n = 1_000_000
        rng = np.random.default_rng(0)
        pq.write_table(pa.table({
            "PatientDurableKey": rng.integers(0, 20_000, n),
            "DiagnosisDate": 20150101 + rng.integers(0, 28, n),
            "DiagnosisCode": pa.array(np.array(["E11.9", "I10", "J45.909", "D89.44"])[rng.integers(0, 4, n)]),
            "Vocabulary": pa.array(["ICD-10-CM"] * n),
            "DiagnosisStatus": pa.array(["Active"] * n)}), path)
        tracemalloc.start()
        dx = read_diagnoses(path, pd.Index(np.arange(20_000)), lines.append,
                            chunk_rows=100_000, bucket_rows=200_000)
        peak = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()
        assert peak / n < 64, f"read_diagnoses used {peak / n:.0f} bytes a row"
        assert 0 < len(dx) <= n
    print("selftest passed")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selftest", action="store_true", help="run the checks and exit")
    ap.add_argument("--dir", type=Path, default=Path(__file__).resolve().parent,
                    help="folder with the pull's parquets (default: this script's folder)")
    ap.add_argument("--prefix", choices=["hat", "ctrl"],
                    help="which pull (default: whichever *_Patients.parquet is there)")
    ap.add_argument("--data-end", default="2026-06-01",
                    help="last date in the pull (max_date_key); ends observation")
    args = ap.parse_args()
    if args.selftest:
        selftest()
        return
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
    enc = read(folder, prefix, "Encounters", ENCOUNTER_COLS,
               text=["DerivedEncounterStatus", "DerivedEncounterType_X"])
    dx_path = table_path(folder, prefix, "Diagnoses", DIAGNOSIS_COLS)
    labs = read(folder, prefix, "Labs", LAB_COLS, text=["Unit"])
    say(f"read: {len(pts):,} patients, {len(enc):,} encounters, "
        f"{pq.read_metadata(dx_path).num_rows:,} diagnosis rows, {len(labs):,} lab rows")

    # 2. Diagnoses: drop ruled-out and error statuses, then one row per patient, code, date.
    pts = pts.drop_duplicates("PatientDurableKey").set_index("PatientDurableKey")
    dx = read_diagnoses(dx_path, pts.index, say)
    say(f"diagnoses kept: {len(dx):,} patient-code-date rows")

    # 3. Index date. Cases: the first D89.44 that survived the status filter (D4, D24);
    #    the PK's IndexDate took any status. Controls: their sampled clinic visit (D30).
    pk_index = datekey(pts["IndexDate"])
    hat_dx = dx.with_codes(lambda c: c == HAT_CODE)
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
    mc = dx.with_codes(lambda c: c.startswith(MAST_CELL_PREFIX) and c != HAT_CODE)
    mc = mc[mc["Date"] < mc["PatientDurableKey"].map(out["IndexDate"])]
    mc_first = mc.sort_values("Date").drop_duplicates("PatientDurableKey").set_index("PatientDurableKey")
    out["EarlierMastCellCode"] = mc_first["DiagnosisCode"].astype("string").reindex(out.index)
    out["EarlierMastCellCodeDate"] = mc_first["Date"].reindex(out.index)

    # 7. Tryptase: baseline serum results in ng/mL only (HaT Considerations).
    labs = labs[labs["LabComponentKey"].isin(TRYPTASE_BASELINE)
                & matching(labs["Unit"], lambda u: u.lower().strip() == "ng/ml")
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
    out.to_parquet(folder / f"{group}_group.parquet", index=False)
    n_diag = write_diagnoses(dx, out.set_index("PatientDurableKey")["IndexDate"],
                             folder / f"{group}_group_diagnoses.parquet")
    if is_hat:
        out[["PatientDurableKey"]].to_parquet(folder / "hat_patient_keys.parquet", index=False)

    say(f"\nwrote {group}_group.parquet: {len(out):,} patients, "
        f"{out['EligibleForMatching'].sum():,} eligible for matching")
    say(f"  not eligible: {(out['ClinicVisits365Before'] < 2).sum():,} with under 2 clinic visits "
        f"in the year before index; {out['Sex'].isna().sum():,} with no usable sex; "
        f"{out['IndexBeforeD8944Existed'].sum():,} indexed before 2021-10-01")
    say(f"wrote {group}_group_diagnoses.parquet: {n_diag:,} rows")
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
