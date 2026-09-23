#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
phewas.py -- single-file phenome-wide association study (PheWAS) tool.

Requirements: Python 3.7+ and numpy. Nothing else (no pandas, scipy,
statsmodels or matplotlib). Modeled on the workflow of the R PheWAS package
(https://github.com/PheWAS/PheWAS):

  1. Map ICD codes to phecodes, rolling child phecodes up to their parents
     (250.21 -> 250.2 -> 250).
  2. Define, for every phecode:
       cases      people with >= --min-code-count occurrences (default 2;
                  distinct dates if a date column exists)
       excluded   people with 1..(min-1) occurrences, people with a related
                  phecode from the exclusion range, and the wrong sex for
                  sex-specific phecodes
       controls   everyone else in the --people file
  3. For each phecode with >= --min-cases cases, fit
         phecode ~ predictor + covariates
     by logistic regression (Wald test, as R's glm). If separation is
     detected, refit with Firth penalized logistic regression
     (penalized likelihood-ratio test, as R's logistf).
  4. Bonferroni and Benjamini-Hochberg FDR correction.
  5. Write a results CSV, a Manhattan plot (SVG; open in any browser) and a
     run log that records the SHA-256 of this script and every input file.

QUICK START (Windows cmd uses ^ for line continuation, PowerShell uses `)

  python phewas.py --selftest

  python phewas.py ^
      --people cohort.csv --id-col person_id ^
      --predictors rs1333049 --covars age sex PC1 PC2 PC3 --sex-col sex ^
      --events icd_codes.csv ^
      --map phecode_map_icd9.csv ICD9CM --map phecode_map_icd10.csv ICD10CM ^
      --definitions phecode_definitions1.2.csv ^
      --out results\\cad_snp

INPUT FILES  (CSV / TSV / pipe-delimited, optionally .gz. Column names are
             auto-detected case-insensitively, or set with the --*-col flags.)

  --people       One row per person: id, predictor column(s), covariates and
                 optionally sex. This file defines the study population;
                 anyone in it without qualifying codes is a control.
                 Non-numeric covariates (e.g. sex = M/F, race) are dummy
                 coded automatically; the most common level is the reference.
  --events       One row per diagnosis: id, code, and optionally vocabulary
                 (ICD9CM / ICD10CM, or 9 / 10), date, count.
  --map          ICD -> phecode map with code and phecode columns (optionally
                 vocabulary, description, exclusion range). Repeatable. Put a
                 vocabulary after the file name to tag all of its rows:
                     --map Phecode_map_v1_2_icd10cm_beta.csv ICD10CM
  --definitions  Optional, repeatable: phecode info (description, category,
                 sex, exclusion range), e.g. phecode_definitions1.2.csv.
                 R-style sex_restriction tables (male_only/female_only) work too.
  --exclusions   Optional pairwise exclusion table in R PheWAS phecode_exclude
                 format (columns: code, exclusion_criteria).

Use --events-are-phecodes if your events file already holds phecodes.
Run  python phewas.py --help  for all options.
"""

import argparse
import bisect
import csv
import gzip
import hashlib
import io
import math
import os
import platform
import re
import sys
import tempfile
import time
from collections import Counter, defaultdict
from xml.sax.saxutils import escape as xml_escape

__version__ = "1.0.0"

try:
    import numpy as np
except ImportError:
    sys.stderr.write(
        "ERROR: numpy is required but could not be imported.\n"
        "Check with:  python -c \"import numpy; print(numpy.__version__)\"\n")
    sys.exit(1)

csv.field_size_limit(2 ** 31 - 1)

Z975 = 1.959963984540054
MISSING = {"", "NA", "N/A", "NAN", "NULL", "NONE", ".", "?", "MISSING"}

ID_CANDS = ["id", "person_id", "patient_id", "subject_id", "participant_id",
            "sample_id", "eid", "iid", "grid", "mrn", "pid"]
CODE_CANDS = ["code", "icd", "icd_code", "icd9", "icd10", "icd9cm", "icd10cm",
              "dx_code", "diagnosis_code", "concept_code",
              "condition_source_value", "source_value"]
VOCAB_CANDS = ["vocabulary_id", "vocabulary", "vocab", "code_type",
               "icd_version", "code_system", "flag"]
DATE_CANDS = ["date", "index", "event_date", "visit_date", "service_date",
              "dx_date", "start_date", "condition_start_date", "admit_date"]
COUNT_CANDS = ["count", "n", "code_count", "freq", "frequency", "num"]
PHE_CANDS = ["phecode", "phecode_id", "jd_code"]
DESC_CANDS = ["phenotype", "description", "phecode_string", "phecode_str",
              "phenotype_name", "phecode_description", "phecode_name"]
CAT_CANDS = ["category", "group", "phecode_category", "category_name"]
SEX_CANDS = ["sex", "sex_restriction"]
RANGE_CANDS = ["phecode_exclude_range", "exclude_range", "excl_phecodes",
               "exclusion_range", "phecode_exclusion_range"]


# --------------------------------------------------------------------------
# logging / errors
# --------------------------------------------------------------------------
_LOG_LINES = []


def log(msg=""):
    line = time.strftime("[%H:%M:%S] ") + str(msg)
    _LOG_LINES.append(line)
    try:
        print(line, file=sys.stderr, flush=True)
    except UnicodeEncodeError:
        print(line.encode("ascii", "replace").decode("ascii"),
              file=sys.stderr, flush=True)


class PheWASError(Exception):
    pass


def die(msg):
    raise PheWASError(msg)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


# --------------------------------------------------------------------------
# table reading
# --------------------------------------------------------------------------
def _open_text(path):
    if path.lower().endswith(".gz"):
        return io.TextIOWrapper(gzip.open(path, "rb"), encoding="utf-8-sig",
                                errors="replace", newline="")
    return open(path, "r", encoding="utf-8-sig", errors="replace", newline="")


def _norm_name(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


class Table(object):
    """Minimal delimited-file reader with forgiving column lookup."""

    def __init__(self, path):
        if not os.path.isfile(path):
            die("file not found: %s" % path)
        self.path = path
        with _open_text(path) as f:
            first = f.readline()
        counts = {d: first.count(d) for d in [",", "\t", "|", ";"]}
        best = max(counts, key=counts.get)
        self.delim = best if counts[best] > 0 else ","

    def __enter__(self):
        self.f = _open_text(self.path)
        self.reader = csv.reader(self.f, delimiter=self.delim)
        try:
            self.header = [h.strip() for h in next(self.reader)]
        except StopIteration:
            die("%s is empty" % self.path)
        self._lookup = {}
        for i in range(len(self.header) - 1, -1, -1):
            self._lookup[_norm_name(self.header[i])] = i
        return self

    def __exit__(self, *exc):
        self.f.close()

    def find(self, explicit, candidates, required, what):
        if explicit:
            k = _norm_name(explicit)
            if k in self._lookup:
                return self._lookup[k]
            die("%s: column '%s' (%s) not found. Columns are: %s"
                % (self.path, explicit, what, self.header))
        for c in candidates:
            k = _norm_name(c)
            if k in self._lookup:
                return self._lookup[k]
        if required:
            die("%s: could not find a %s column (tried %s). Columns are: %s. "
                "Set it explicitly with the matching --*-col option."
                % (self.path, what, candidates, self.header))
        return None

    def rows(self):
        n = len(self.header)
        for row in self.reader:
            if not row:
                continue
            if len(row) < n:
                row = row + [""] * (n - len(row))
            yield row


# --------------------------------------------------------------------------
# code / phecode normalization
# --------------------------------------------------------------------------
_NUMERIC_PHE = re.compile(r"^\d+(\.\d*)?$")


def canon_phecode(s):
    """'8.5' / '008.50' / '008.5' -> '008.5'; non-numeric codes unchanged."""
    s = s.strip()
    if not s:
        return ""
    if _NUMERIC_PHE.match(s):
        if "." in s:
            a, b = s.split(".", 1)
            b = b.rstrip("0")
        else:
            a, b = s, ""
        a = (a.lstrip("0") or "0").zfill(3)
        return a + ("." + b if b else "")
    return s


def phe_num(p):
    try:
        return float(p) if _NUMERIC_PHE.match(p) else None
    except ValueError:
        return None


def phe_sort_key(p):
    v = phe_num(p)
    return (0, v, p) if v is not None else (1, 0.0, p)


def phecode_parents(p):
    out = []
    while "." in p:
        p = p[:-1]
        if p.endswith("."):
            p = p[:-1]
        out.append(p)
    return out


def norm_code(c, strip_dots):
    c = c.strip().upper()
    if strip_dots:
        c = c.replace(".", "")
    return c


def norm_vocab(v):
    if v is None:
        return None
    s = str(v).strip().upper()
    if not s:
        return None
    try:
        f = float(s)
        if f == 9:
            return "ICD9CM"
        if f == 10:
            return "ICD10CM"
    except ValueError:
        pass
    k = re.sub(r"[^A-Z0-9]", "", s)
    if k in ("ICD9", "ICD9CM"):
        return "ICD9CM"
    if k in ("ICD10", "ICD10CM"):
        return "ICD10CM"
    return k or None


def parse_ranges(s):
    """'008-009.99, 041' -> [(8.0, 9.99), (41.0, 41.0)]"""
    out = []
    for part in re.split(r"[,;]", s or ""):
        part = part.strip()
        if not part:
            continue
        m = re.match(r"^([0-9.]+)\s*-\s*([0-9.]+)$", part)
        try:
            if m:
                out.append((float(m.group(1)), float(m.group(2))))
            elif re.match(r"^[0-9.]+$", part):
                out.append((float(part), float(part)))
        except ValueError:
            pass
    return out


def _truthy(s):
    return s.strip().upper() in ("TRUE", "T", "1", "YES", "Y")


# --------------------------------------------------------------------------
# loaders
# --------------------------------------------------------------------------
def load_definitions(paths):
    info = {}
    for path in paths:
        n = 0
        with Table(path) as t:
            pi = t.find(None, PHE_CANDS + ["code"], True, "phecode")
            di = t.find(None, DESC_CANDS, False, "description")
            ci = t.find(None, CAT_CANDS, False, "category")
            si = t.find(None, SEX_CANDS, False, "sex")
            ri = t.find(None, RANGE_CANDS, False, "exclusion range")
            mi = t.find(None, ["male_only"], False, "male_only")
            fi = t.find(None, ["female_only"], False, "female_only")
            for row in t.rows():
                p = canon_phecode(row[pi])
                if not p:
                    continue
                n += 1
                d = info.setdefault(p, {"desc": "", "cat": "", "sex": None,
                                        "ranges": None})
                if di is not None and row[di].strip():
                    d["desc"] = row[di].strip()
                if ci is not None and row[ci].strip():
                    d["cat"] = row[ci].strip()
                if si is not None:
                    s = row[si].strip().upper()
                    if s.startswith("M"):
                        d["sex"] = "M"
                    elif s.startswith("F"):
                        d["sex"] = "F"
                if mi is not None and _truthy(row[mi]):
                    d["sex"] = "M"
                if fi is not None and _truthy(row[fi]):
                    d["sex"] = "F"
                if ri is not None:
                    rs = parse_ranges(row[ri])
                    if rs:
                        d["ranges"] = rs
        log("definitions %s: %d rows" % (path, n))
    return info


def load_maps(specs, args):
    vmap = defaultdict(set)   # (vocab, code) -> phecodes   (vocab known)
    nmap = defaultdict(set)   # code -> phecodes            (vocab unknown)
    amap = defaultdict(set)   # code -> phecodes            (all rows)
    descs, ranges, vocabs = {}, {}, set()
    for spec in specs:
        path = spec[0]
        override = norm_vocab(spec[1]) if len(spec) > 1 else None
        n = 0
        with Table(path) as t:
            ci = t.find(args.map_code_col, CODE_CANDS, True, "ICD code")
            pi = t.find(args.map_phecode_col, PHE_CANDS, True, "phecode")
            vi = None if override else t.find(args.map_vocab_col, VOCAB_CANDS,
                                              False, "vocabulary")
            di = t.find(None, DESC_CANDS, False, "description")
            ri = t.find(None, RANGE_CANDS, False, "exclusion range")
            for row in t.rows():
                code = norm_code(row[ci], args.strip_dots)
                phe = canon_phecode(row[pi])
                if not code or not phe:
                    continue
                n += 1
                v = override or (norm_vocab(row[vi]) if vi is not None else None)
                if v:
                    vocabs.add(v)
                    vmap[(v, code)].add(phe)
                else:
                    nmap[code].add(phe)
                amap[code].add(phe)
                if di is not None and row[di].strip():
                    descs.setdefault(phe, row[di].strip())
                if ri is not None and phe not in ranges:
                    rs = parse_ranges(row[ri])
                    if rs:
                        ranges[phe] = rs
        log("map %s%s: %d code->phecode rows"
            % (path, " [%s]" % override if override else "", n))
    universe = set()
    for s in amap.values():
        universe |= s
    return vmap, nmap, amap, descs, ranges, vocabs, universe


def load_pairs(path):
    pairs = defaultdict(set)
    with Table(path) as t:
        ti = t.find(None, ["code", "phecode"], True, "target phecode")
        ei = t.find(None, ["exclusion_criteria", "exclude", "exclude_phecode",
                           "excluded_phecode", "exclusion"], True,
                    "excluded phecode")
        for row in t.rows():
            a, b = canon_phecode(row[ti]), canon_phecode(row[ei])
            if a and b:
                pairs[a].add(b)
    log("pairwise exclusions %s: %d phecodes" % (path, len(pairs)))
    return pairs


def load_people(args):
    with Table(args.people) as t:
        ii = t.find(args.id_col, ID_CANDS, True, "person id")
        needed = list(dict.fromkeys(
            args.predictors + args.covars + ([args.sex_col] if args.sex_col else [])))
        cols = {name: t.find(name, [], True, "requested") for name in needed}
        ids, seen, dup = [], set(), 0
        raw = {name: [] for name in needed}
        for row in t.rows():
            pid = row[ii].strip()
            if not pid:
                continue
            if pid in seen:
                dup += 1
                continue
            seen.add(pid)
            ids.append(pid)
            for name, ci in cols.items():
                raw[name].append(row[ci].strip())
    if dup:
        log("WARNING: %d duplicate ids in %s (kept first occurrence)"
            % (dup, args.people))
    log("people %s: %d individuals" % (args.people, len(ids)))
    if not ids:
        die("no individuals in --people file")
    return ids, raw


def encode_column(name, vals):
    """Return (matrix n x m, column names, missing mask, description)."""
    n = len(vals)
    miss = np.array([v.upper() in MISSING for v in vals], dtype=bool)
    nums = np.full(n, np.nan)
    numeric = True
    for i, v in enumerate(vals):
        if miss[i]:
            continue
        try:
            nums[i] = float(v)
        except ValueError:
            numeric = False
            break
    if numeric:
        miss = miss | ~np.isfinite(nums)
        return nums.reshape(-1, 1), [name], miss, "numeric"
    cnt = Counter(v for v, m in zip(vals, miss) if not m)
    levels = sorted(cnt, key=lambda l: (-cnt[l], l))
    ref, others = levels[0], levels[1:]
    mat = np.zeros((n, len(others)))
    pos = {l: j for j, l in enumerate(others)}
    for i, v in enumerate(vals):
        if not miss[i] and v in pos:
            mat[i, pos[v]] = 1.0
    names = ["%s[%s]" % (name, l) for l in others]
    return mat, names, miss, "categorical, reference='%s', levels=%s" % (ref, levels)


# --------------------------------------------------------------------------
# events -> phecode counts
# --------------------------------------------------------------------------
def count_events(args, id_index, maps, universe):
    phe_mode = args.events_are_phecodes
    vmap, nmap, amap = maps if maps else ({}, {}, {})
    mc = args.min_code_count
    rollup = not args.no_rollup
    if rollup and phe_mode and not universe:
        log("rollup skipped: --events-are-phecodes without --definitions")
        rollup = False
    counts = defaultdict(dict)
    parent_cache = {}
    unmapped = Counter()
    n_rows = n_pop = n_mapped = n_bad = 0
    sample_ids = []
    with Table(args.events) as t:
        ii = t.find(args.events_id_col,
                    ([args.id_col] if args.id_col else []) + ID_CANDS,
                    True, "person id")
        if phe_mode:
            ci = t.find(args.code_col, PHE_CANDS + CODE_CANDS, True, "phecode")
            vi = None
        else:
            ci = t.find(args.code_col, CODE_CANDS, True, "ICD code")
            vi = t.find(args.vocab_col, VOCAB_CANDS, False, "vocabulary")
        di = t.find(args.date_col, DATE_CANDS, False, "date")
        cc = t.find(args.count_col, COUNT_CANDS, False, "count")
        if args.count_col and not args.date_col:
            di = None
        if di is not None:
            cc = None
            how = "distinct values of '%s' per person and phecode" % t.header[di]
        elif cc is not None:
            how = "sum of '%s'" % t.header[cc]
        else:
            how = "one per row"
        log("events %s: id='%s' code='%s' vocab=%s; counting = %s"
            % (args.events, t.header[ii], t.header[ci],
               ("'%s'" % t.header[vi]) if vi is not None else "none", how))
        if not phe_mode and vi is None and len(set(v for v, _ in vmap)) > 1:
            log("WARNING: events have no vocabulary column but the maps cover "
                "several vocabularies; codes shared between ICD-9 and ICD-10 "
                "will map to both. Use --vocab-col if possible.")
        for row in t.rows():
            n_rows += 1
            pid = row[ii].strip()
            idx = id_index.get(pid)
            if idx is None:
                if len(sample_ids) < 5:
                    sample_ids.append(pid)
                continue
            n_pop += 1
            if phe_mode:
                p = canon_phecode(row[ci])
                phes = {p} if p else None
            else:
                code = norm_code(row[ci], args.strip_dots)
                if vi is not None:
                    v = norm_vocab(row[vi])
                    a, b = vmap.get((v, code)), nmap.get(code)
                    phes = (a | b) if (a and b) else (a or b)
                else:
                    phes = amap.get(code)
                if not phes:
                    if len(unmapped) < 100000:
                        unmapped[code] += 1
                    continue
            if not phes:
                continue
            n_mapped += 1
            if rollup:
                full = set(phes)
                for p in phes:
                    par = parent_cache.get(p)
                    if par is None:
                        par = tuple(q for q in phecode_parents(p) if q in universe)
                        parent_cache[p] = par
                    full.update(par)
                phes = full
            if di is not None:
                dval = row[di].strip()
                for p in phes:
                    d = counts[p]
                    st = d.get(idx)
                    if st is None:
                        d[idx] = {dval} if mc > 1 else 1
                    elif isinstance(st, set) and dval not in st:
                        st.add(dval)
                        if len(st) >= mc:
                            d[idx] = len(st)   # threshold reached; stop tracking
            else:
                c = 1.0
                if cc is not None:
                    try:
                        c = float(row[cc])
                    except ValueError:
                        n_bad += 1
                        continue
                    if not c > 0:
                        continue
                for p in phes:
                    d = counts[p]
                    d[idx] = d.get(idx, 0) + c
    log("events: %d rows, %d for people in the study population, %d mapped "
        "to a phecode (%.1f%% of population rows)"
        % (n_rows, n_pop, n_mapped, 100.0 * n_mapped / max(n_pop, 1)))
    if n_bad:
        log("WARNING: %d rows with a non-numeric count were skipped" % n_bad)
    if n_pop == 0:
        die("no event ids matched the --people ids. Example event ids: %s; "
            "example people ids: %s" % (sample_ids, list(id_index)[:5]))
    if unmapped and not phe_mode:
        log("most frequent unmapped codes: %s"
            % ", ".join("%s (%d)" % kv for kv in unmapped.most_common(10)))
    if n_mapped == 0:
        ev_dots = sum("." in c for c in list(unmapped)[:1000])
        mp_dots = sum("." in c for c in list(amap)[:1000])
        hint = ""
        if (ev_dots == 0) != (mp_dots == 0):
            hint = " The events and map disagree about decimal points; try --strip-dots."
        die("no events mapped to phecodes." + hint)
    for p in counts:
        d = counts[p]
        for k, v in d.items():
            if isinstance(v, set):
                d[k] = len(v)
    return counts


# --------------------------------------------------------------------------
# statistics
# --------------------------------------------------------------------------
def _expit(eta):
    return np.exp(-np.logaddexp(0.0, -eta))


def _loglik(eta, y):
    return float(np.dot(y, eta) - np.sum(np.logaddexp(0.0, eta)))


def fit_logistic(X, y, max_iter=60):
    """Maximum-likelihood logistic regression by Newton-Raphson/IRLS."""
    n, k = X.shape
    beta = np.zeros(k)
    ybar = float(y.mean())
    beta[0] = math.log(ybar / (1.0 - ybar))
    eta = X @ beta
    ll = _loglik(eta, y)
    converged = False
    for _ in range(max_iter):
        p = _expit(eta)
        w = p * (1.0 - p)
        info = (X * w[:, None]).T @ X
        try:
            delta = np.linalg.solve(info, X.T @ (y - p))
        except np.linalg.LinAlgError:
            return {"ok": False, "note": "singular information matrix"}
        if not np.all(np.isfinite(delta)):
            return {"ok": False, "note": "non-finite update"}
        step, improved = 1.0, False
        for _ in range(30):
            nb = beta + step * delta
            neta = X @ nb
            nll = _loglik(neta, y)
            if nll >= ll:
                improved = True
                break
            step *= 0.5
        if not improved:
            converged = True
            break
        change = np.max(np.abs(nb - beta))
        rel = abs(nll - ll) / (abs(nll) + 0.1)
        beta, eta, ll = nb, neta, nll
        if rel < 1e-10 or change < 1e-9:
            converged = True
            break
    p = _expit(eta)
    w = p * (1.0 - p)
    info = (X * w[:, None]).T @ X
    try:
        cov = np.linalg.inv(info)
    except np.linalg.LinAlgError:
        return {"ok": False, "note": "singular information matrix"}
    se = np.sqrt(np.clip(np.diag(cov), 0.0, None))
    std_eff = np.abs(beta[1:]) * X[:, 1:].std(axis=0)
    separation = ((not converged) or bool(std_eff.size and std_eff.max() > 10)
                  or float(np.max(np.abs(eta))) > 30 or not np.all(np.isfinite(se)))
    return {"ok": True, "beta": beta, "se": se, "converged": converged,
            "separation": separation, "ll": ll}


def _firth_state(X, y, beta):
    eta = X @ beta
    p = _expit(eta)
    w = p * (1.0 - p)
    info = (X * w[:, None]).T @ X
    sign, logdet = np.linalg.slogdet(info)
    if sign <= 0 or not np.isfinite(logdet):
        return -np.inf, p, w, info
    return _loglik(eta, y) + 0.5 * logdet, p, w, info


def fit_firth(X, y, fixed=None, beta0=None, max_iter=200, max_step=5.0):
    """Firth penalized logistic regression (Jeffreys prior), as in logistf.
    Parameters listed in `fixed` are held at 0 (used for the penalized LRT)."""
    n, k = X.shape
    free = np.ones(k, dtype=bool)
    if fixed:
        free[list(fixed)] = False
    beta = np.zeros(k) if beta0 is None else np.array(beta0, dtype=float)
    beta[~free] = 0.0
    pl, p, w, info = _firth_state(X, y, beta)
    if not np.isfinite(pl):
        return {"ok": False, "note": "singular information matrix"}
    converged = False
    for _ in range(max_iter):
        try:
            iinv = np.linalg.inv(info)
        except np.linalg.LinAlgError:
            return {"ok": False, "note": "singular information matrix"}
        h = w * np.sum((X @ iinv) * X, axis=1)
        U = X.T @ (y - p + h * (0.5 - p))
        Uf = U[free]
        try:
            df = np.linalg.solve(info[np.ix_(free, free)], Uf)
        except np.linalg.LinAlgError:
            return {"ok": False, "note": "singular information matrix"}
        mx = float(np.max(np.abs(df)))
        if mx > max_step:
            df = df * (max_step / mx)
        delta = np.zeros(k)
        delta[free] = df
        step, improved = 1.0, False
        for _ in range(30):
            nb = beta + step * delta
            npl, pn, wn, infon = _firth_state(X, y, nb)
            if npl >= pl:
                improved = True
                break
            step *= 0.5
        if not improved:
            converged = True
            break
        change = float(np.max(np.abs(nb - beta)))
        beta, pl, p, w, info = nb, npl, pn, wn, infon
        if change < 1e-9 or float(np.max(np.abs(Uf))) < 1e-9:
            converged = True
            break
    try:
        cov = np.linalg.inv(info)
    except np.linalg.LinAlgError:
        return {"ok": False, "note": "singular information matrix"}
    return {"ok": True, "beta": beta, "pl": pl, "cov": cov,
            "converged": converged}


def wald_p(z):
    return math.erfc(abs(z) / math.sqrt(2.0))


def run_model(X, y, firth_mode):
    """Fit y ~ X; the predictor of interest is column 1."""
    if firth_mode != "always":
        r = fit_logistic(X, y)
        if r["ok"] and (not r["separation"] or firth_mode == "never"):
            b, s = float(r["beta"][1]), float(r["se"][1])
            if not (s > 0 and np.isfinite(s)):
                return {"note": "invalid standard error"}
            return {"beta": b, "se": s, "p": wald_p(b / s), "lo": b - Z975 * s,
                    "hi": b + Z975 * s, "model": "logistic",
                    "converged": r["converged"],
                    "note": "possible separation" if r["separation"] else ""}
        if firth_mode == "never":
            return {"note": "logistic fit failed: " + r.get("note", "")}
        why = "separation detected" if r["ok"] else r["note"]
    else:
        why = ""
    f = fit_firth(X, y)
    if not f["ok"]:
        return {"note": "Firth fit failed: " + f["note"]}
    f0 = fit_firth(X, y, fixed=[1], beta0=f["beta"])
    if not f0["ok"]:
        return {"note": "Firth null fit failed: " + f0["note"]}
    b = float(f["beta"][1])
    s = float(math.sqrt(max(f["cov"][1, 1], 0.0)))
    stat = max(0.0, 2.0 * (f["pl"] - f0["pl"]))
    note = ("Firth: " + why) if why else "Firth"
    note += "; CI is Wald, p is penalized LRT"
    return {"beta": b, "se": s, "p": math.erfc(math.sqrt(stat / 2.0)),
            "lo": b - Z975 * s, "hi": b + Z975 * s, "model": "firth",
            "converged": f["converged"] and f0["converged"], "note": note}


def independent_columns(Xi):
    """Greedy selection of linearly independent columns (0 and 1 first)."""
    G = Xi.T @ Xi
    d = np.sqrt(np.clip(np.diag(G), 0.0, None))
    keep = []
    for j in range(Xi.shape[1]):
        if d[j] == 0:
            continue
        cand = keep + [j]
        sub = G[np.ix_(cand, cand)] / np.outer(d[cand], d[cand])
        ev = np.linalg.eigvalsh(sub)
        if ev.min() > 1e-10 * max(ev.max(), 1.0):
            keep.append(j)
    return keep


def bh_qvalues(ps):
    m = len(ps)
    if m == 0:
        return []
    order = sorted(range(m), key=lambda i: ps[i])
    q = [0.0] * m
    prev = 1.0
    for rank in range(m, 0, -1):
        i = order[rank - 1]
        prev = min(prev, ps[i] * m / rank)
        q[i] = min(prev, 1.0)
    return q


# --------------------------------------------------------------------------
# Manhattan plot (SVG, no dependencies)
# --------------------------------------------------------------------------
PALETTE = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b",
           "#e377c2", "#7f7f7f", "#bcbd22", "#17becf", "#393b79", "#637939",
           "#8c6d31", "#843c39", "#7b4173", "#3182bd", "#e6550d", "#31a354"]


def write_manhattan(path, rows, title, alpha, n_labels):
    pts = [r for r in rows if r.get("p") is not None]
    if not pts:
        log("no tested phecodes; Manhattan plot skipped")
        return
    for r in pts:
        r["_cat"] = r["category"] or "Uncategorized"
    cat_min = {}
    for r in pts:
        k = phe_sort_key(r["phecode"])
        if r["_cat"] not in cat_min or k < cat_min[r["_cat"]]:
            cat_min[r["_cat"]] = k
    cats = sorted(cat_min, key=lambda c: (cat_min[c], c))
    color = {c: PALETTE[i % len(PALETTE)] for i, c in enumerate(cats)}
    rank = {c: i for i, c in enumerate(cats)}
    pts.sort(key=lambda r: (rank[r["_cat"]], phe_sort_key(r["phecode"])))

    m = len(pts)
    bonf = alpha / m
    fdr_ps = [r["p"] for r in pts if r["q"] <= alpha]
    W, H = 1400, 660
    L, R, T, B = 80, 30, 60, 190
    pw, ph = W - L - R, H - T - B
    ys = [-math.log10(max(r["p"], 1e-300)) for r in pts]
    ymax = max(max(ys), -math.log10(bonf), 3.0) * 1.1
    step = next(s for s in [1, 2, 5, 10, 20, 25, 50, 100, 200] if ymax / s <= 8)

    def px(i):
        return L + (i + 0.5) * pw / m

    def py(v):
        return T + ph - v / ymax * ph

    out = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
           'viewBox="0 0 %d %d" font-family="Arial, Helvetica, sans-serif">'
           % (W, H, W, H),
           '<rect width="100%" height="100%" fill="#ffffff"/>',
           '<text x="%d" y="30" font-size="18" font-weight="bold">%s</text>'
           % (L, xml_escape(title))]
    v = 0
    while v <= ymax:
        y = py(v)
        out.append('<line x1="%d" x2="%d" y1="%.1f" y2="%.1f" stroke="#e5e5e5"/>'
                   % (L, L + pw, y, y))
        out.append('<text x="%d" y="%.1f" font-size="12" text-anchor="end">%g</text>'
                   % (L - 8, y + 4, v))
        v += step
    out.append('<line x1="%d" x2="%d" y1="%d" y2="%d" stroke="#333"/>'
               % (L, L, T, T + ph))
    out.append('<line x1="%d" x2="%d" y1="%d" y2="%d" stroke="#333"/>'
               % (L, L + pw, T + ph, T + ph))
    out.append('<text transform="translate(24,%d) rotate(-90)" font-size="14" '
               'text-anchor="middle">-log10(p)</text>' % (T + ph / 2))
    yb = py(-math.log10(bonf))
    out.append('<line x1="%d" x2="%d" y1="%.1f" y2="%.1f" stroke="#d62728" '
               'stroke-dasharray="6,4"/>' % (L, L + pw, yb, yb))
    out.append('<text x="%d" y="%.1f" font-size="11" fill="#d62728" '
               'text-anchor="end">Bonferroni p=%.2g</text>' % (L + pw - 4, yb - 4, bonf))
    if fdr_ps:
        yf = py(-math.log10(max(max(fdr_ps), 1e-300)))
        out.append('<line x1="%d" x2="%d" y1="%.1f" y2="%.1f" stroke="#1f77b4" '
                   'stroke-dasharray="2,3"/>' % (L, L + pw, yf, yf))
        out.append('<text x="%d" y="%.1f" font-size="11" fill="#1f77b4" '
                   'text-anchor="end">FDR %g</text>' % (L + pw - 4, yf + 13, alpha))
    for i, r in enumerate(pts):
        x, y = px(i), py(ys[i])
        c = color[r["_cat"]]
        tip = xml_escape("%s %s | OR=%.3g p=%.3g cases=%d"
                         % (r["phecode"], r["description"], math.exp(r["beta"]),
                            r["p"], r["n_cases"]))
        if r["beta"] >= 0:
            pts_s = "%.1f,%.1f %.1f,%.1f %.1f,%.1f" % (x, y - 4.5, x - 4, y + 3, x + 4, y + 3)
        else:
            pts_s = "%.1f,%.1f %.1f,%.1f %.1f,%.1f" % (x, y + 4.5, x - 4, y - 3, x + 4, y - 3)
        out.append('<polygon points="%s" fill="%s" fill-opacity="0.85">'
                   '<title>%s</title></polygon>' % (pts_s, c, tip))
    top = sorted((i for i, r in enumerate(pts) if r["q"] <= alpha),
                 key=lambda i: pts[i]["p"])[:n_labels]
    placed = []   # (x0, x1, y) of labels already drawn, to avoid overlaps
    for i in top:
        r = pts[i]
        lab = r["description"] or r["phecode"]
        lab = lab if len(lab) <= 40 else lab[:38] + ".."
        anchor = "end" if px(i) > L + pw * 0.8 else "start"
        dx = -7 if anchor == "end" else 7
        wid = 6.2 * len(lab)
        x0 = px(i) + dx - (wid if anchor == "end" else 0)
        x1 = x0 + wid
        ly = py(ys[i]) - 5
        for _ in range(40):
            if not any(x0 < b1 and b0 < x1 and abs(ly - by) < 12 for b0, b1, by in placed):
                break
            ly += 13
        placed.append((x0, x1, ly))
        if abs(ly - (py(ys[i]) - 5)) > 1:
            out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#999" '
                       'stroke-width="0.6"/>' % (px(i), py(ys[i]), px(i) + dx, ly - 3))
        out.append('<text x="%.1f" y="%.1f" font-size="11" text-anchor="%s">%s</text>'
                   % (px(i) + dx, ly, anchor, xml_escape(lab)))
    for c in cats:
        idx = [i for i, r in enumerate(pts) if r["_cat"] == c]
        xc = (px(idx[0]) + px(idx[-1])) / 2
        lab = c if len(c) <= 28 else c[:26] + ".."
        out.append('<text transform="translate(%.1f,%d) rotate(-50)" font-size="11" '
                   'text-anchor="end" fill="%s">%s</text>'
                   % (xc, T + ph + 14, color[c], xml_escape(lab)))
    out.append('<text x="%d" y="%d" font-size="11" fill="#555" text-anchor="end">'
               'triangle up = OR &gt; 1, down = OR &lt; 1; hover a point for details</text>'
               % (L + pw, H - 10))
    out.append("</svg>")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    for r in pts:
        r.pop("_cat", None)


# --------------------------------------------------------------------------
# main pipeline
# --------------------------------------------------------------------------
def build_parser():
    ap = argparse.ArgumentParser(
        description="Single-file PheWAS (numpy only). See the header of this "
                    "file for input formats and an example.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    g = ap.add_argument_group("study population")
    g.add_argument("--people", help="one row per person: id, predictors, covariates")
    g.add_argument("--id-col", help="person id column (auto-detected if omitted)")
    g.add_argument("--predictors", nargs="+", default=[],
                   help="exposure/genotype column(s); each is analysed separately")
    g.add_argument("--covars", nargs="*", default=[], help="covariate columns")
    g.add_argument("--sex-col", help="sex column, used for sex-specific phecodes")
    g.add_argument("--male-values", default="M,MALE,MAN",
                   help="comma-separated values of --sex-col meaning male")
    g.add_argument("--female-values", default="F,FEMALE,WOMAN",
                   help="comma-separated values of --sex-col meaning female")
    g = ap.add_argument_group("diagnosis events")
    g.add_argument("--events", help="one row per diagnosis event")
    g.add_argument("--events-id-col")
    g.add_argument("--code-col")
    g.add_argument("--vocab-col")
    g.add_argument("--date-col", help="count distinct values of this column")
    g.add_argument("--count-col", help="sum this column instead of dates")
    g.add_argument("--events-are-phecodes", action="store_true",
                   help="events file already contains phecodes; no map needed")
    g.add_argument("--strip-dots", action="store_true",
                   help="remove '.' from ICD codes in both events and maps")
    g = ap.add_argument_group("phecode maps and definitions")
    g.add_argument("--map", nargs="+", action="append", default=[],
                   metavar=("FILE", "VOCAB"),
                   help="ICD->phecode map file, optionally followed by its vocabulary")
    g.add_argument("--map-code-col")
    g.add_argument("--map-phecode-col")
    g.add_argument("--map-vocab-col")
    g.add_argument("--definitions", action="append", default=[],
                   help="phecode definitions file(s)")
    g.add_argument("--exclusions", help="pairwise exclusion file (code, exclusion_criteria)")
    g = ap.add_argument_group("phenotype and model settings")
    g.add_argument("--min-code-count", type=int, default=2,
                   help="occurrences needed to be a case")
    g.add_argument("--min-cases", type=int, default=20,
                   help="minimum cases to test a phecode")
    g.add_argument("--no-rollup", action="store_true",
                   help="do not roll child phecodes up to parents")
    g.add_argument("--no-exclusions", action="store_true",
                   help="ignore exclusion ranges (controls = all non-cases)")
    g.add_argument("--no-sex-restriction", action="store_true")
    g.add_argument("--firth", choices=["auto", "always", "never"], default="auto",
                   help="Firth regression: on separation, always, or never")
    g = ap.add_argument_group("output")
    g.add_argument("--out", help="output prefix, e.g. results\\mystudy")
    g.add_argument("--alpha", type=float, default=0.05)
    g.add_argument("--labels", type=int, default=10,
                   help="number of top hits labelled on the plot")
    g.add_argument("--no-hash", action="store_true",
                   help="skip SHA-256 hashing of input files in the log")
    ap.add_argument("--selftest", action="store_true",
                    help="run built-in tests on synthetic data and exit")
    ap.add_argument("--version", action="version", version=__version__)
    return ap


def _fmt(x, spec="%.6g"):
    if x is None:
        return "NA"
    if isinstance(x, float) and not np.isfinite(x):
        return "NA"
    return spec % x


def run(args):
    t0 = time.time()
    if not args.people or not args.events or not args.out or not args.predictors:
        die("--people, --events, --predictors and --out are required "
            "(or use --selftest)")
    if not args.map and not args.events_are_phecodes:
        die("--map is required unless --events-are-phecodes is given")
    if args.min_code_count < 1:
        die("--min-code-count must be >= 1")
    out_dir = os.path.dirname(os.path.abspath(args.out))
    os.makedirs(out_dir, exist_ok=True)

    log("phewas.py %s | Python %s | numpy %s | %s"
        % (__version__, platform.python_version(), np.__version__, platform.platform()))
    try:
        log("script sha256: %s" % sha256_file(os.path.abspath(__file__)))
    except (OSError, NameError):
        pass
    log("command: " + " ".join(sys.argv))

    inputs = [args.people, args.events] + [m[0] for m in args.map] + \
        list(args.definitions) + ([args.exclusions] if args.exclusions else [])
    for pth in inputs:
        if not os.path.isfile(pth):
            die("file not found: %s" % pth)
        if not args.no_hash:
            log("input sha256 %s  %s" % (sha256_file(pth), pth))

    # --- phecode reference data
    defs = load_definitions(args.definitions) if args.definitions else {}
    if args.map:
        vmap, nmap, amap, mdesc, mranges, vocabs, universe = load_maps(args.map, args)
        maps = (vmap, nmap, amap)
    else:
        maps, mdesc, mranges, universe = None, {}, {}, set()
    universe = set(universe) | set(defs)
    pairs = load_pairs(args.exclusions) if args.exclusions else {}

    # --- population
    ids, raw = load_people(args)
    N = len(ids)
    id_index = {pid: i for i, pid in enumerate(ids)}

    # --- phenotypes
    counts = count_events(args, id_index, maps, universe)
    mc = args.min_code_count
    cases, low, present = {}, {}, {}
    for p, d in counts.items():
        idx = np.fromiter(d.keys(), dtype=np.int64, count=len(d))
        cnt = np.fromiter(d.values(), dtype=np.float64, count=len(d))
        present[p] = idx
        cases[p] = np.sort(idx[cnt >= mc])
        low[p] = idx[cnt < mc]
    with_any = np.zeros(N, dtype=bool)
    for idx in present.values():
        with_any[idx] = True
    log("%d phecodes observed; %d of %d people (%.1f%%) have at least one mapped code"
        % (len(counts), int(with_any.sum()), N, 100.0 * with_any.mean()))

    def info(p, key):
        d = defs.get(p)
        if key == "desc":
            return (d and d["desc"]) or mdesc.get(p, "")
        if key == "ranges":
            return (d and d["ranges"]) or mranges.get(p)
        return d[key] if d else (None if key == "sex" else "")

    # --- exclusions
    num_obs = sorted((phe_num(p), p) for p in counts if phe_num(p) is not None)
    vals = [v for v, _ in num_obs]
    names = [p for _, p in num_obs]
    n_with_rules = 0
    excl_idx = {}
    for P in counts:
        related = set()
        if not args.no_exclusions:
            rs = info(P, "ranges")
            if rs:
                n_with_rules += 1
                for lo, hi in rs:
                    i = bisect.bisect_left(vals, lo - 1e-9)
                    j = bisect.bisect_right(vals, hi + 1e-9)
                    related.update(names[i:j])
            if P in pairs:
                if not rs:
                    n_with_rules += 1
                related |= {q for q in pairs[P] if q in counts}
            related.discard(P)
        parts = [present[q] for q in related] + [low[P]]
        ex = np.unique(np.concatenate(parts)) if parts else np.zeros(0, np.int64)
        excl_idx[P] = np.setdiff1d(ex, cases[P], assume_unique=True)
    if args.no_exclusions:
        log("exclusion ranges disabled (--no-exclusions)")
    elif n_with_rules == 0:
        log("WARNING: no exclusion criteria found in the maps/definitions; "
            "controls may include people with closely related phecodes")
    else:
        log("exclusion criteria available for %d of %d observed phecodes"
            % (n_with_rules, len(counts)))

    # --- sex
    is_male = is_female = None
    if args.sex_col and not args.no_sex_restriction:
        mv = {s.strip().upper() for s in args.male_values.split(",")}
        fv = {s.strip().upper() for s in args.female_values.split(",")}
        sx = [v.upper() for v in raw[args.sex_col]]
        is_male = np.array([v in mv for v in sx])
        is_female = np.array([v in fv for v in sx])
        log("sex from '%s': %d male, %d female, %d other/missing"
            % (args.sex_col, int(is_male.sum()), int(is_female.sum()),
               N - int(is_male.sum()) - int(is_female.sum())))
        if is_male.sum() == 0 and is_female.sum() == 0:
            log("WARNING: no values matched --male-values/--female-values; "
                "sex restriction disabled")
            is_male = is_female = None
    n_sex = sum(1 for p in counts if info(p, "sex"))
    if n_sex and is_male is None:
        log("NOTE: %d observed phecodes are sex-specific but no usable --sex-col "
            "was given, so they are analysed in everyone" % n_sex)

    # --- covariates
    cov_cols, cov_names = [], []
    cov_miss = np.zeros(N, dtype=bool)
    for c in args.covars:
        mat, nm, miss, desc = encode_column(c, raw[c])
        log("covariate %s: %s, %d missing" % (c, desc, int(miss.sum())))
        cov_cols.append(mat)
        cov_names += nm
        cov_miss |= miss
    C = np.hstack(cov_cols) if cov_cols else np.zeros((N, 0))

    phe_order = sorted(counts, key=phe_sort_key)
    all_rows = []
    for pred in args.predictors:
        mat, nm, pmiss, desc = encode_column(pred, raw[pred])
        if mat.shape[1] != 1:
            die("predictor '%s' is categorical with more than 2 levels (%s); "
                "recode it as numeric first" % (pred, desc))
        log("predictor %s: %s%s, %d missing"
            % (pred, desc, " (coded 1 = %s)" % nm[0] if nm[0] != pred else "",
               int(pmiss.sum())))
        ok = ~pmiss & ~cov_miss
        log("complete cases for %s: %d of %d" % (pred, int(ok.sum()), N))
        X = np.column_stack([np.ones(N), mat[:, 0], C])
        X[~ok] = 0.0
        term_names = ["(Intercept)", pred] + cov_names
        rows = []
        n_tested = 0
        tick = time.time()
        for k, P in enumerate(phe_order):
            inc = ok.copy()
            if excl_idx[P].size:
                inc[excl_idx[P]] = False
            sx = info(P, "sex")
            if sx and is_male is not None:
                inc &= is_male if sx == "M" else is_female
            y = np.zeros(N)
            y[cases[P]] = 1.0
            yi = y[inc]
            n_tot = int(inc.sum())
            n_case = int(yi.sum())
            row = {"predictor": pred, "phecode": P,
                   "description": info(P, "desc"), "category": info(P, "cat"),
                   "sex_restriction": sx or "", "n_total": n_tot,
                   "n_cases": n_case, "n_controls": n_tot - n_case,
                   "n_excluded": int(ok.sum()) - n_tot, "beta": None, "se": None,
                   "p": None, "lo": None, "hi": None, "model": "",
                   "converged": "", "note": "", "dropped_terms": ""}
            if n_case < args.min_cases:
                row["note"] = "fewer than %d cases" % args.min_cases
            elif n_tot - n_case < 1:
                row["note"] = "no controls"
            else:
                Xi = X[inc]
                keep = independent_columns(Xi)
                if 0 not in keep or 1 not in keep:
                    row["note"] = "predictor constant or collinear in this subset"
                else:
                    if len(keep) < Xi.shape[1]:
                        row["dropped_terms"] = ";".join(
                            term_names[j] for j in range(Xi.shape[1]) if j not in keep)
                        Xi = Xi[:, keep]
                    res = run_model(Xi, yi, args.firth)
                    row.update(res)
                    if res.get("p") is not None:
                        n_tested += 1
            rows.append(row)
            if time.time() - tick > 15:
                log("  %s: %d / %d phecodes" % (pred, k + 1, len(phe_order)))
                tick = time.time()
        tested = [r for r in rows if r["p"] is not None]
        qs = bh_qvalues([r["p"] for r in tested])
        for r, q in zip(tested, qs):
            r["q"] = q
            r["bonferroni"] = r["p"] <= args.alpha / max(len(tested), 1)
        for r in rows:
            r.setdefault("q", None)
            r.setdefault("bonferroni", None)
        n_b = sum(1 for r in tested if r["bonferroni"])
        n_f = sum(1 for r in tested if r["q"] <= args.alpha)
        n_firth = sum(1 for r in tested if r["model"] == "firth")
        log("%s: %d phecodes tested (%d with Firth); %d Bonferroni-significant, "
            "%d FDR<%g" % (pred, len(tested), n_firth, n_b, n_f, args.alpha))
        for r in sorted(tested, key=lambda r: r["p"])[:10]:
            log("   %-8s OR=%-8.3g p=%-10.3g cases=%-7d %s"
                % (r["phecode"], math.exp(r["beta"]), r["p"], r["n_cases"],
                   r["description"][:60]))
        safe = re.sub(r"[^A-Za-z0-9_.-]", "_", pred)
        svg = "%s_%s_manhattan.svg" % (args.out, safe)
        write_manhattan(svg, tested, "PheWAS: %s  (%d phecodes)" % (pred, len(tested)),
                        args.alpha, args.labels)
        log("wrote %s" % svg)
        all_rows += rows

    res_path = args.out + "_results.csv"
    cols = ["predictor", "phecode", "description", "category", "sex_restriction",
            "n_total", "n_cases", "n_controls", "n_excluded", "beta", "se",
            "OR", "OR_lower95", "OR_upper95", "p", "q_fdr", "bonferroni",
            "model", "converged", "dropped_terms", "note"]
    all_rows.sort(key=lambda r: (args.predictors.index(r["predictor"]),
                                 r["p"] if r["p"] is not None else 2.0,
                                 phe_sort_key(r["phecode"])))
    with open(res_path, "w", encoding="utf-8", newline="") as f:
        wtr = csv.writer(f)
        wtr.writerow(cols)
        for r in all_rows:
            has = r["beta"] is not None
            wtr.writerow([
                r["predictor"], r["phecode"], r["description"], r["category"],
                r["sex_restriction"], r["n_total"], r["n_cases"], r["n_controls"],
                r["n_excluded"], _fmt(r["beta"]), _fmt(r["se"]),
                _fmt(math.exp(r["beta"]) if has else None),
                _fmt(math.exp(r["lo"]) if has else None),
                _fmt(math.exp(r["hi"]) if has else None),
                _fmt(r["p"], "%.4g"), _fmt(r["q"], "%.4g"),
                "" if r["bonferroni"] is None else ("TRUE" if r["bonferroni"] else "FALSE"),
                r["model"], "" if r["converged"] == "" else str(bool(r["converged"])).upper(),
                r["dropped_terms"], r["note"]])
    log("wrote %s" % res_path)
    log("finished in %.1f s" % (time.time() - t0))
    log_path = args.out + "_log.txt"
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("\n".join(_LOG_LINES) + "\n")
    return all_rows


# --------------------------------------------------------------------------
# self-test
# --------------------------------------------------------------------------
def selftest():
    rs = np.random.RandomState(3)
    fails = []

    def check(name, cond, detail=""):
        log("%s  %s %s" % ("PASS" if cond else "FAIL", name, detail))
        if not cond:
            fails.append(name)

    # 1. logistic regression recovers a known effect
    n = 20000
    x = rs.normal(size=n)
    z = rs.normal(size=n)
    X = np.column_stack([np.ones(n), x, z])
    y = (rs.uniform(size=n) < _expit(-2 + 0.5 * x - 0.3 * z)).astype(float)
    r = fit_logistic(X, y)
    check("logistic estimate", r["ok"] and abs(r["beta"][1] - 0.5) < 0.08,
          "beta=%.3f (true 0.5)" % r["beta"][1])
    # 2. Firth on a small, well-behaved sample is close to ML but shrunk
    f = fit_firth(X[:3000], y[:3000])
    r2 = fit_logistic(X[:3000], y[:3000])
    check("firth close to ML when no separation",
          f["ok"] and abs(f["beta"][1] - r2["beta"][1]) < 0.05,
          "firth=%.3f ml=%.3f" % (f["beta"][1], r2["beta"][1]))
    # 3. complete separation: ML flags it, Firth stays finite
    xs = np.r_[np.zeros(50), np.ones(50)]
    ys = xs.copy()   # outcome perfectly predicted by x
    Xs = np.column_stack([np.ones(100), xs])
    rml = fit_logistic(Xs, ys)
    check("separation detected", (not rml["ok"]) or rml["separation"])
    out = run_model(Xs, ys, "auto")
    check("Firth under separation", out.get("model") == "firth"
          and np.isfinite(out["beta"]) and 0 < out["p"] < 1e-5,
          "beta=%s p=%s" % (out.get("beta"), out.get("p")))
    # 4. end-to-end pipeline on synthetic files
    tmp = tempfile.mkdtemp(prefix="phewas_selftest_")
    phes = ["008", "038", "250", "250.2", "250.21", "272", "272.1", "401",
            "401.1", "411", "411.4", "427", "427.2", "495", "555", "555.1",
            "714", "714.1", "185", "626"]
    cats = {"008": "infectious diseases", "038": "infectious diseases",
            "250": "endocrine/metabolic", "250.2": "endocrine/metabolic",
            "250.21": "endocrine/metabolic", "272": "endocrine/metabolic",
            "272.1": "endocrine/metabolic", "185": "neoplasms",
            "626": "genitourinary", "495": "respiratory", "555": "digestive",
            "555.1": "digestive", "714": "musculoskeletal", "714.1": "musculoskeletal"}
    ranges = {"250": "249-250.99", "250.2": "249-250.99", "250.21": "249-250.99",
              "411": "410-414.99", "411.4": "410-414.99", "401": "401-405.99",
              "401.1": "401-405.99", "272": "272-272.99", "272.1": "272-272.99"}
    leaves = [p for p in phes if not any(q != p and q.startswith(p + ".") for q in phes)]
    icd = {p: "T%02d.%d" % (i, i % 7) for i, p in enumerate(leaves)}
    with open(os.path.join(tmp, "map.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["icd10cm", "phecode"])
        for p, c in icd.items():
            w.writerow([c, p])
    with open(os.path.join(tmp, "defs.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["phecode", "phenotype", "phecode_exclude_range", "sex", "category"])
        for p in phes:
            sex = "Male" if p == "185" else ("Female" if p == "626" else "Both")
            w.writerow([p, "Phenotype " + p, ranges.get(p, ""), sex,
                        cats.get(p, "circulatory system")])
    N = 6000
    snp = rs.binomial(2, 0.3, size=N)
    age = rs.normal(55, 10, size=N)
    sex = np.where(rs.uniform(size=N) < 0.5, "M", "F")
    with open(os.path.join(tmp, "people.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["person_id", "snp", "age", "sex"])
        for i in range(N):
            w.writerow(["P%05d" % i, snp[i], "%.1f" % age[i], sex[i]])
    with open(os.path.join(tmp, "events.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["person_id", "vocabulary_id", "code", "date"])
        for p in leaves:
            if p == "185":
                elig = sex == "M"
            elif p == "626":
                elig = sex == "F"
            else:
                elig = np.ones(N, bool)
            eta = -3.0 + 0.02 * (age - 55) + (0.8 * snp if p == "411.4" else 0.0)
            has = (rs.uniform(size=N) < _expit(eta)) & elig
            once = (rs.uniform(size=N) < 0.02) & ~has & elig
            for i in np.where(has)[0]:
                for d in range(2 + rs.randint(3)):
                    w.writerow(["P%05d" % i, "ICD10CM", icd[p], "2020-01-%02d" % (d + 1)])
            for i in np.where(once)[0]:
                w.writerow(["P%05d" % i, "ICD10CM", icd[p], "2021-05-05"])
    argv = ["--people", os.path.join(tmp, "people.csv"), "--predictors", "snp",
            "--covars", "age", "sex", "--sex-col", "sex",
            "--events", os.path.join(tmp, "events.csv"),
            "--map", os.path.join(tmp, "map.csv"), "ICD10CM",
            "--definitions", os.path.join(tmp, "defs.csv"),
            "--out", os.path.join(tmp, "st"), "--no-hash"]
    rows = run(build_parser().parse_args(argv))
    by = {r["phecode"]: r for r in rows}
    top = min((r for r in rows if r["p"] is not None), key=lambda r: r["p"])
    check("planted association is the top hit", top["phecode"] in ("411", "411.4"),
          "top=%s p=%.2g" % (top["phecode"], top["p"]))
    check("planted OR recovered", abs(by["411.4"]["beta"] - 0.8) < 0.25,
          "beta=%.3f (true 0.8)" % by["411.4"]["beta"])
    check("rollup: 411 has at least the 411.4 cases",
          by["411"]["n_cases"] >= by["411.4"]["n_cases"])
    check("sex restriction (185 male only)",
          by["185"]["n_total"] <= int((sex == "M").sum())
          and "sex" in by["185"]["dropped_terms"])
    check("exclusions applied (single-code people excluded)",
          by["495"]["n_excluded"] > 0)
    nulls = [r["p"] for r in rows if r["p"] is not None and r["phecode"]
             not in ("411", "411.4")]
    check("null phecodes not significant", min(nulls) > 0.05 / len(rows) / 10,
          "min null p=%.3g" % min(nulls))
    check("outputs written", os.path.isfile(os.path.join(tmp, "st_results.csv"))
          and os.path.isfile(os.path.join(tmp, "st_snp_manhattan.svg")))
    log("self-test files in %s" % tmp)
    log("SELF-TEST %s" % ("PASSED" if not fails else "FAILED: %s" % fails))
    return 0 if not fails else 1


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        if args.selftest:
            return selftest()
        run(args)
        return 0
    except PheWASError as e:
        log("ERROR: %s" % e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
