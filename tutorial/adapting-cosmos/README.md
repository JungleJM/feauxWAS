# Adapting Cosmos Pulls

From the two Telescope pulls to `hat_group.parquet` and `control_group.parquet`, the files matching and the PheWAS run on. Everything here runs on the VM; the study's choices it applies are in `reference/plan/decisions.md` (the D-numbers below).

| File | What it is |
|------------------------|-----------------------------------------------|
| `build_group_parquet.py` | Turns one pull's four parquets into the group's two files. Needs pandas and pyarrow only. |
| `ctrl_PheWAS_intake.yaml` | The control pull, as a Telescope intake. |

## On The VM, In Order

1.  **Build the hat group.** Copy `build_group_parquet.py` into the `hat_` pull's parquet folder (Telescope's `cosmos_parquets`, beside `hat_Patients.parquet`, `hat_Encounters.parquet`, `hat_Diagnoses.parquet` and `hat_Labs.parquet`) and run `python build_group_parquet.py`. It writes `hat_group.parquet`, `hat_group_diagnoses.parquet`, `hat_group_report.txt` and `hat_patient_keys.parquet`.
2.  **Read the report.** `hat_group_report.txt` lists every `DiagnosisStatus` and which were dropped, the sex, race and ethnicity values, the encounter statuses, and who isn't eligible for matching and why. Check nothing surprising was dropped.
3.  **Pull the controls.** Put `hat_patient_keys.parquet` beside `ctrl_PheWAS_intake.yaml`, open it in Telescope, check `project_db`, and run it.
4.  **Build the control group.** Same as step 1, in the `ctrl_` pull's parquet folder: `control_group.parquet`, `control_group_diagnoses.parquet`, `control_group_report.txt`. If the report says some controls had a D89.44, they were dropped.
5.  **Match and run the PheWAS**, as in `../control-matching-tutorial.md` (steps 3–5), pointing at the real group files.

To run the script on parquets in another folder: `python build_group_parquet.py --dir <folder>`.

## What The Script Does

1.  **Reads only the columns it uses** from each table; the pulls carry every column, most of which the analysis never needs. A missing table or column stops it with a message naming it.
2.  **Cleans the diagnoses.** Drops any `DiagnosisStatus` containing "rule", "error", "delete" or "cancel" (ruled-out, entered in error...), then keeps one row per patient, code and date: billing repeats the same diagnosis across linked encounters, and pheauxWAS counts dates, not rows.
3.  **Sets the index date.** A case's index is their first D89.44 that survived step 2 (D4, D24); the pull's `IndexDate` took a D89.44 of any status, so a case can move to a later D89.44, or drop out if none is left. `AgeAtIndex` (Cosmos's, from DurationDim) moves with it. A control's index is the clinic visit the pull sampled (D30); a control with any D89.44 is dropped.
4.  **Demographics.** `Sex` is `ReliableSex`, or `Sex` where that is Ambiguous; anything else is left missing (D25). `Race` (from `FirstRace`) and `Ethnicity` turn blank and `*`-prefixed values (`*Unspecified`) into `Unknown` (D10).
5.  **Observation and visits**, from completed encounters only. Observation runs from the first to the last encounter, ending earlier at death or the data's end. `ClinicVisits365Before` and `After` count days with a completed Office Visit or Follow-Up in the year either side of index (D31); `EdVisits365Before` and `Admissions365Before` count ED visits and admissions.
6.  **HaT codes.** `HaTDateCount` is the number of D89.44 dates (the 2+ sensitivity analysis, D24); `EarlierMastCellCode` and its date are the first other D89.4x code before index (the attending's question 1).
7.  **Tryptase.** Baseline serum tryptase only (components 2287 and 59082, in ng/mL, not a failed draw): `TryptaseCount`, `TryptaseMax`, `TryptaseFirst` and its date. The IgE antibody (8166) and the other units are left out.
8.  **Eligibility** for matching (D8): two clinic-visit days in the year before index, a usable sex, and, for cases, an index from 2021-10-01 on, when D89.44 was in use and the control pool begins (`IndexBeforeD8944Existed`).
9.  **Writes** the two files, plus, for the hat group, `hat_patient_keys.parquet` (the keys alone) for the control pull to exclude.

## The Two Files

`<group>_group.parquet`, one row per patient:

| Column | Meaning |
|------------------------|-----------------------------------------------|
| `PatientDurableKey` | the patient |
| `Group`, `HaT_Flag` | `hat` (1) or `control` (0) |
| `IndexDate`, `IndexYear`, `IndexQuarter` | the index date; its year; its quarter, as `2023Q2` |
| `AgeAtIndex` | age in years at index |
| `IndexBeforeD8944Existed` | 1 if the index is before 2021-10-01 |
| `Sex`, `Race`, `MultiRacial`, `Ethnicity` | demographics, as in step 4 |
| `BirthDate`, `DeathDate` | from PatientDim |
| `ObservationStartDate`, `ObservationEndDate` | first and last completed encounter (the end capped at death and the data's end) |
| `YearsBeforeIndex`, `YearsAfterIndex` | record length before and after index |
| `ClinicVisits365Before`, `ClinicVisits365After` | clinic-visit days in the year before and after index |
| `EdVisits365Before`, `Admissions365Before` | ED visits and admissions in the year before index |
| `HaTDateCount` | distinct D89.44 dates |
| `EarlierMastCellCode`, `EarlierMastCellCodeDate` | first other D89.4x before index, if any |
| `TryptaseCount`, `TryptaseMax`, `TryptaseFirst`, `TryptaseFirstDate` | baseline serum tryptase, ng/mL |
| `EligibleForMatching` | 1 if eligible, as in step 8 |

`<group>_group_diagnoses.parquet`, one row per patient, code and date: `PatientDurableKey`, `DiagnosisCode`, `Vocabulary`, `DiagnosisDate`, `DaysFromIndex` (negative before index). All ICD-10-CM codes are kept, D89.44 included; `prepare_phewas_inputs.py` drops the exposure code and picks the window.

## The Control Pull

`ctrl_PheWAS_intake.yaml` has the same tables and columns as the `hat_` pull (`reference/hat_cosmos_blueprint.yaml`), with `ctrl_Patients` as the PK. Why it's built this way is D30; how it works:

- **`ctrl_Patients`** is one random completed Office Visit or Follow-Up per patient, from `control_index_start` (2021-10-01) to the data's end: the pseudo-index. Patients in `hat_patient_keys.parquet` are excluded.
- **The pool's size.** `ABS(CHECKSUM(PatientDurableKey)) % 1000 < pool_permille` first keeps about `pool_permille` patients per 1,000 (10, so 1%), so the rest of the query runs on millions of rows rather than billions. Then `smallset`, `stop_at_for_pk_table: 300000` and `random_pk_sample` keep the first 300,000 in Telescope's reproducible hash order: about 50 per case, for 10 per case after matching. If fewer than 300,000 come back, raise `pool_permille`.
- **`ctrl_Encounters`, `ctrl_Diagnoses`, `ctrl_Labs`** are the `hat_` pull's fact tables, joined to `ctrl_Patients`, with every column and the same window (from 2015-01-01).
- It validates in Telescope with one expected warning: `RandomOrder` (the hash that picks the visit) is computed, so its type is declared rather than checked.