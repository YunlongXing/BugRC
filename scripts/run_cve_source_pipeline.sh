#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [[ ! -x "${PROJECT_ROOT}/.venv/bin/python" ]]; then
  echo "Missing virtualenv at ${PROJECT_ROOT}/.venv" >&2
  exit 1
fi

BASE_OUTPUT="${1:-${HOME}/bugrc-data/cve_source_pipeline}"
PARSER_BACKEND="${PARSER_BACKEND:-regex}"
GIT_TIMEOUT_SECONDS="${GIT_TIMEOUT_SECONDS:-30}"
SEMANTIC_MIN_CONFIDENCE="${SEMANTIC_MIN_CONFIDENCE:-0.68}"
SEMANTIC_PATTERN_MIN_CONFIDENCE="${SEMANTIC_PATTERN_MIN_CONFIDENCE:-0.45}"
SOURCE_MAX_CVES="${SOURCE_MAX_CVES:-1000}"
SOURCE_MAX_PER_PATTERN="${SOURCE_MAX_PER_PATTERN:-200}"
SOURCE_VALIDATION_MAX_REPOS="${SOURCE_VALIDATION_MAX_REPOS:-500}"
SOURCE_MAX_FILES="${SOURCE_MAX_FILES:-3000}"
SOURCE_MAX_BYTES="${SOURCE_MAX_BYTES:-67108864}"
SOURCE_PROGRESS_LOG_EVERY="${SOURCE_PROGRESS_LOG_EVERY:-25}"

BOOTSTRAP_DIR="${BASE_OUTPUT}/cve_bootstrap_full"
SEMANTIC_DIR="${BASE_OUTPUT}/cve_semantic"
TARGETS_DIR="${BASE_OUTPUT}/cve_source_validation_targets"
VALIDATION_DIR="${BASE_OUTPUT}/cve_source_validation"
REPOS_ROOT="${BASE_OUTPUT}/source-validation-repos"
LOG_DIR="${BASE_OUTPUT}/logs"

mkdir -p "${BOOTSTRAP_DIR}" "${SEMANTIC_DIR}" "${TARGETS_DIR}" "${VALIDATION_DIR}" "${REPOS_ROOT}" "${LOG_DIR}"

cd "${PROJECT_ROOT}"
source "${PROJECT_ROOT}/.venv/bin/activate"

echo "[1/4] Building cvelistV5 collection at ${BOOTSTRAP_DIR}"
if [[ -f "${BOOTSTRAP_DIR}/bootstrap_collection_result.json" ]]; then
  echo "Reusing existing collection JSON: ${BOOTSTRAP_DIR}/bootstrap_collection_result.json"
else
  python3 scripts/bootstrap_cve_corpus.py \
    --output-dir "${BOOTSTRAP_DIR}" \
    --keep-collection-json \
    --no-disk-saver \
    --skip-build \
    --max-repos 0 \
    --parser-backend "${PARSER_BACKEND}" \
    --git-timeout-seconds "${GIT_TIMEOUT_SECONDS}"
fi

echo "[2/4] Building semantic baseline at ${SEMANTIC_DIR}"
python3 scripts/build_cve_semantic_patterns.py \
  --collection-json "${BOOTSTRAP_DIR}/bootstrap_collection_result.json" \
  --output-dir "${SEMANTIC_DIR}" \
  --min-confidence "${SEMANTIC_PATTERN_MIN_CONFIDENCE}"

echo "[3/4] Selecting high-value CVEs for source validation at ${TARGETS_DIR}"
python3 scripts/select_cve_source_validation_targets.py \
  --semantic-dataset "${SEMANTIC_DIR}/cve_semantic_root_cause_dataset.json" \
  --collection-json "${BOOTSTRAP_DIR}/bootstrap_collection_result.json" \
  --output-dir "${TARGETS_DIR}" \
  --project-root "${PROJECT_ROOT}" \
  --log-path "${LOG_DIR}/source_validation.log" \
  --validation-output-dir "${VALIDATION_DIR}" \
  --repos-root "${REPOS_ROOT}" \
  --min-confidence "${SEMANTIC_MIN_CONFIDENCE}" \
  --max-cves "${SOURCE_MAX_CVES}" \
  --max-per-pattern "${SOURCE_MAX_PER_PATTERN}" \
  --validation-max-repos "${SOURCE_VALIDATION_MAX_REPOS}" \
  --git-timeout-seconds "${GIT_TIMEOUT_SECONDS}" \
  --max-source-files "${SOURCE_MAX_FILES}" \
  --max-source-bytes "${SOURCE_MAX_BYTES}" \
  --progress-log-every "${SOURCE_PROGRESS_LOG_EVERY}"

echo "[4/4] Running source validation into ${VALIDATION_DIR}"
python3 scripts/resume_cve_bootstrap_filtered.py \
  --collection-json "${TARGETS_DIR}/source_validation_collection.json" \
  --output-dir "${VALIDATION_DIR}" \
  --repos-root "${REPOS_ROOT}" \
  --parser-backend "${PARSER_BACKEND}" \
  --max-repos "${SOURCE_VALIDATION_MAX_REPOS}" \
  --git-timeout-seconds "${GIT_TIMEOUT_SECONDS}" \
  --max-source-files "${SOURCE_MAX_FILES}" \
  --max-source-bytes "${SOURCE_MAX_BYTES}" \
  --progress-log-every "${SOURCE_PROGRESS_LOG_EVERY}"

echo "Pipeline complete."
echo "Semantic dataset: ${SEMANTIC_DIR}/cve_semantic_root_cause_dataset.json"
echo "Semantic patterns: ${SEMANTIC_DIR}/cve_pattern_prior_library.json"
echo "Source dataset: ${VALIDATION_DIR}/pipeline-output/cve_root_cause_dataset.json"
echo "Source patterns: ${VALIDATION_DIR}/pipeline-output/cve_pattern_library.json"
