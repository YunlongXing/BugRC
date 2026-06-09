# BugRC

BugRC is a research prototype for **root-cause-guided vulnerability repair** in
C/C++ projects. Given a bug report with a trigger location and optional runtime,
patch, issue, or CVE evidence, BugRC reconstructs a root-cause-to-trigger
causality chain, ranks root-cause candidates, and emits evidence-grounded patch
suggestions and audit artifacts.

This public repository contains the software artifact only: source code, tests,
examples, and reproduction/evaluation drivers. Large benchmark corpora, local
caches, generated outputs, and non-software materials are intentionally not
included.

## Highlights

BugRC is designed around one principle:

> A security patch should cut the causal path from the vulnerability origin to
> the trigger, not merely suppress the crash-site symptom.

The implementation provides:

- JSON-validated intermediate representations for bug reports, trigger points,
  runtime evidence, root-cause candidates, backward slices, and causality chains.
- C/C++ source abstraction with lightweight parser backends and heuristic
  fallbacks for incomplete projects.
- Trigger-guided backward slicing over variables, sizes, indices, pointers,
  branch guards, returns, globals, and heap-like aliases.
- Root-cause candidate ranking with explicit features and optional CVE-derived
  pattern priors.
- Optional OpenAI-compatible LLM interpretation for ambiguous candidate labels
  and patch intent. LLM output is used only to interpret extracted evidence.
- Patch suggestion, patch-aware analysis, JSON/HTML/text reporting, and
  timeout-bounded patch validation helpers.

## Results Snapshot

The following results are from the authors' evaluation runs. Raw ARVO, Magma,
and CVE corpora are not included in this repository because they are large and
should be obtained from their original sources.

- **ARVO-Meta:** BugRC completed 3,661 analyses from 4,993 C/C++ bug reports.
  A strict semantic-and-manual audit identified 267 high-confidence
  benchmark-reference disagreements where BugRC better cuts the recovered
  root-cause-to-trigger path.
- **Magma:** On all 138 Magma vulnerabilities, BugRC matched the reference
  repair in 117 cases, produced a stronger source-level repair in 14 cases, and
  was incomplete in 7 cases under the evaluation taxonomy.
- **Patch materialization:** After refinement, 115 of 138 generated Magma diffs
  were applicable source patches; 113 passed `diff --check`.
- **Compile validation:** In a selected 12-case Magma core set, all baseline
  versions compiled and 11 BugRC-patched versions compiled.
- **Ablation:** Removing the causality chain reduced performance, while a
  trigger-site patch baseline dropped to 65.2% on Magma, supporting the value
  of root-cause-to-trigger reasoning.

These numbers are intended as artifact context, not as standalone proof of
patch correctness. BugRC reports semantic, materialization, and validation
evidence separately.

## Repository Layout

```text
src/bugrc/
  models/           Pydantic data models and JSON contracts
  ingestion/        Bug-spec loading and evidence normalization
  dynamic_analysis/ ASan-like sanitizer and stack trace parsing
  source/           C/C++ source abstraction and parser backends
  slicing/          Trigger-guided backward slicing
  ranking/          Candidate features, scoring, and priors
  chains/           Causality-chain search and formatting
  patch_analysis/   Patch parsing and weak-supervision refinement
  llm/              Optional OpenAI-compatible semantic interpretation
  validation/       Patch/build/reproducer validation harness
  pipeline.py       End-to-end orchestration
  cli.py            bugrc command-line interface

scripts/            Reproduction, CVE-mining, ARVO, and Magma drivers
examples/           JSON schema-shape inputs and output examples
tests/              Unit tests for core components and scripts
reproduce_openssl_sm2_case/
                    Small SM2-style regression example
```

## Dependencies

Required:

- Python `>=3.9`
- `pydantic>=2.7,<3`
- `git` for patch validation and benchmark helpers

Recommended for development:

- `pytest`

Optional:

- `ctags`, `clang`, or tree-sitter-related tooling for richer source parsing.
  BugRC falls back to regex/heuristic parsing when these are unavailable.
- An OpenAI-compatible API key for optional LLM-assisted interpretation:
  `BUGRC_OPENAI_API_KEY` or `OPENAI_API_KEY`.

## Installation

```bash
git clone https://github.com/YunlongXing/BugRC.git
cd BugRC
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -e .
python3 -m pip install pytest
```

Run the tests:

```bash
pytest -q
```

## Basic Usage

Run the full pipeline on the included OpenSSL SM2-style regression example:

```bash
bugrc analyze reproduce_openssl_sm2_case/openssl_sm2_case.json \
  --parser-backend regex \
  --output-dir out/openssl-sm2
```

Print a readable explanation:

```bash
bugrc explain --result-json out/openssl-sm2/analysis_result.json
```

Generate patch suggestions:

```bash
bugrc suggest-patch reproduce_openssl_sm2_case/openssl_sm2_case.json \
  --parser-backend regex \
  --output-dir out/patches
```

Validate an existing patch in a temporary copy:

```bash
bugrc validate-patch \
  --repo /path/to/repo \
  --patch fix.diff \
  --build-cmd "make -j2" \
  --output-dir out/validate
```

## Optional LLM Mode

BugRC does not require an LLM for source analysis. To enable semantic
interpretation for ambiguous candidates or patch intent:

```bash
export BUGRC_OPENAI_API_KEY="..."
bugrc analyze reproduce_openssl_sm2_case/openssl_sm2_case.json \
  --parser-backend regex \
  --llm \
  --llm-model gpt-4.1-mini \
  --output-dir out/with-llm
```

The LLM layer is evidence-bounded: it receives extracted trigger, candidate,
function, dependency, and optional patch context, and it cannot add new source
locations or dependency edges.

## CVE Pattern Prior

Historical CVE pattern libraries can be used as weak ranking priors:

```bash
bugrc analyze reproduce_openssl_sm2_case/openssl_sm2_case.json \
  --parser-backend regex \
  --cve-pattern-library data/cve_pattern_library.v4.clean.json \
  --output-dir out/with-cve-prior
```

To build CVE-derived semantic patterns from a collected CVE JSON file:

```bash
python3 scripts/build_cve_semantic_patterns.py \
  --collection-json /path/to/bootstrap_collection_result.json \
  --output-dir out/cve-semantic \
  --min-confidence 0.45
```

The repository also includes a compact CVE-derived artifact bundle under
`data/`: a 2,177-record compressed root-cause dataset and an 84-pattern library
that can be loaded directly by the CLI.

## OpenSSL SM2-Style Regression Example

The repository includes a minimized OpenSSL SM2-style two-phase decrypt sizing
example:

```bash
bugrc analyze reproduce_openssl_sm2_case/openssl_sm2_case.json \
  --parser-backend regex \
  --output-dir out/openssl-sm2
```

The expected high-level result is that BugRC ranks the upstream size-query
contract as the root-cause region rather than treating the XOR copy trigger as
the only relevant statement.

## Benchmark Drivers

The `scripts/` directory includes drivers for larger experiments:

- `arvo_meta_bugrc_eval.py` for ARVO-style bug report evaluation.
- `magma_bugrc_eval.py` for Magma vulnerability cases.
- `bootstrap_cve_corpus.py` and related scripts for CVE collection, filtering,
  source validation, and pattern mining.
- `validate_magma_patch_applicability.py` and
  `validate_magma_compile_core_cases.py` for patch materialization and compile
  validation.

These scripts expect external benchmark paths supplied by the user. Large
datasets and generated results are intentionally not committed.
