# Experiment Results Bundle

This directory contains compact, sanitized result artifacts for auditing BugRC's
main empirical claims. It intentionally excludes raw benchmark corpora, cloned
source trees, build directories, local caches, remote path maps, and non-software
materials.

## Contents

- `magma/`
  - Full 138-case Magma run summary and compressed per-case JSONL results.
  - Summary: 117 cases matched the reference repair, 14 cases produced a
    stronger source-level repair under the artifact taxonomy, and 7 cases were
    incomplete.

- `ablation/`
  - Ablation table for Full BugRC, variants without causality chain,
    CVE/pattern prior, project prior, LLM-only root cause, and trigger-site
    baseline.
  - On Magma, Full BugRC reached 94.9% success under the evaluation taxonomy,
    while the trigger-site baseline reached 65.2%.

- `validation/`
  - Patch materialization, diff-check, compile, and targeted dynamic-validation
    summaries.
  - Refined Magma patch materialization applied 115 of 138 generated patches,
    with 113 passing `diff --check`.
  - In the selected 12-case Magma compile set, all base versions compiled and
    11 BugRC-patched versions compiled.

- `external_baselines/`
  - Small Magma-subset compatibility/effectiveness artifacts for external AVR
    baselines, including VulRepair prediction export and CPR/ExtractFix
    applicability assessment.

- `arvo_high_confidence/`
  - Compressed high-confidence ARVO semantic audit subset.
  - Contains 267 records accepted at confidence >= 0.99 after semantic judging
    and manual consistency review.

- `priors/`
  - ARVO-derived project prior, ranker calibration, and prior summary files.
  - These are optional priors for reproducing enhanced ranking configurations.

- `artifact_manifest.json`
  - File-level SHA-256 hashes and byte sizes for the result bundle.

## Reading Compressed Files

```bash
python3 - <<'PY'
import gzip
import json

with gzip.open("results/magma/full_138_results.jsonl.gz", "rt") as handle:
    first_case = json.loads(handle.readline())

print(first_case.keys())
PY
```

## Notes

The result files preserve the evaluation taxonomy and per-case evidence used by
the artifact, but they are not a replacement for rebuilding benchmarks from
their original sources. Large corpora such as ARVO, Magma, CVE mirrors, and
project source checkouts should be obtained separately and supplied to the
scripts in `scripts/`.
