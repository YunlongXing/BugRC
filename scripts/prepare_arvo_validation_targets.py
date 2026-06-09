#!/usr/bin/env python3
"""Select high-confidence ARVO-Meta cases for patch/reproducer validation."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


FUZZ_TARGET_RE = re.compile(r"^Fuzz Target:\s*(\S+)", re.MULTILINE)
TESTCASE_RE = re.compile(r"https://oss-fuzz\.com/download\?testcase_id=\d+")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suspicious-json", required=True, type=Path)
    parser.add_argument("--meta-dir", required=True, type=Path)
    parser.add_argument("--oss-fuzz-dir", required=True, type=Path)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--min-confidence", type=float, default=0.9)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    cases = json.loads(args.suspicious_json.read_text(encoding="utf-8"))
    selected = []
    for case in cases:
        comparison = case.get("comparison") or {}
        if comparison.get("verdict") != "bugrc_patch_better":
            continue
        confidence = comparison.get("confidence")
        if not isinstance(confidence, (int, float)) or confidence < args.min_confidence:
            continue
        meta = read_json(args.meta_dir / f"{case.get('local_id')}.json")
        report_text = first_report_comment(meta)
        fuzzer_name = extract_fuzzer_name(report_text)
        testcase_url = extract_testcase_url(report_text)
        project = str(case.get("project") or "")
        oss_fuzz_project_dir = args.oss_fuzz_dir / "projects" / project
        chains = case.get("bugrc_chains") or []
        first_chain = chains[0] if chains else {}
        generated_patch = case.get("generated_patch") or {}
        official_patch_path = Path(str(case.get("official_patch_path") or ""))
        selected.append(
            {
                "local_id": str(case.get("local_id")),
                "project": project,
                "repo_url": case.get("repo_url"),
                "fix_commit": case.get("fix_commit"),
                "sanitizer": case.get("sanitizer"),
                "oss_fuzz_sanitizer": sanitizer_for_oss_fuzz(str(case.get("sanitizer") or "")),
                "crash_type": case.get("crash_type"),
                "severity": case.get("severity"),
                "confidence": float(confidence),
                "trigger": case.get("trigger"),
                "bugrc_chain_count": len(chains),
                "bugrc_first_chain_fallback": (first_chain.get("metadata") or {}).get("fallback_chain") if first_chain else None,
                "fuzzer_name": fuzzer_name,
                "testcase_url": testcase_url,
                "has_oss_fuzz_project": oss_fuzz_project_dir.exists(),
                "official_patch_path": official_patch_path.as_posix(),
                "generated_patch_diff": generated_patch.get("unified_diff") or "",
                "comparison": comparison,
                "selection_score": selection_score(
                    has_oss_fuzz_project=oss_fuzz_project_dir.exists(),
                    has_fuzzer=bool(fuzzer_name),
                    has_testcase=bool(testcase_url),
                    has_nonfallback_chain=bool(chains) and (first_chain.get("metadata") or {}).get("fallback_chain") is False,
                    confidence=float(confidence),
                ),
            }
        )

    selected.sort(key=lambda item: (-item["selection_score"], -item["confidence"], item["project"], item["local_id"]))
    selected = selected[: args.limit]
    payload = {
        "source": args.suspicious_json.as_posix(),
        "limit": args.limit,
        "min_confidence": args.min_confidence,
        "count": len(selected),
        "targets": selected,
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"targets={len(selected)} output={args.output_json}")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def first_report_comment(meta: dict[str, Any]) -> str:
    for comment in ((meta.get("report") or {}).get("comments") or []):
        content = str(comment.get("content") or "").strip()
        if content:
            return content
    return ""


def extract_fuzzer_name(report_text: str) -> str | None:
    match = FUZZ_TARGET_RE.search(report_text)
    return match.group(1) if match else None


def extract_testcase_url(report_text: str) -> str | None:
    match = TESTCASE_RE.search(report_text)
    return match.group(0) if match else None


def sanitizer_for_oss_fuzz(name: str) -> str:
    lowered = name.lower()
    if lowered == "asan":
        return "address"
    if lowered == "msan":
        return "memory"
    if lowered == "ubsan":
        return "undefined"
    return "address"


def selection_score(
    *,
    has_oss_fuzz_project: bool,
    has_fuzzer: bool,
    has_testcase: bool,
    has_nonfallback_chain: bool,
    confidence: float,
) -> float:
    score = confidence
    if has_oss_fuzz_project:
        score += 2.0
    if has_fuzzer:
        score += 1.0
    if has_testcase:
        score += 1.0
    if has_nonfallback_chain:
        score += 0.5
    return score


if __name__ == "__main__":
    main()
