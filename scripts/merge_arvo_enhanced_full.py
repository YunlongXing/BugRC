#!/usr/bin/env python3
"""Merge enhanced ARVO shard outputs and write summary artifacts."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="Enhanced ARVO run root containing shards/.")
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    records = load_records(root / "shards")
    records.sort(key=lambda item: int(str(item.get("local_id"))) if str(item.get("local_id", "")).isdigit() else str(item.get("local_id")))

    merged_path = root / "results.enhanced_merged.jsonl"
    merged_path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )

    summary = summarize(records)
    (root / "summary.enhanced_merged.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    better_records = [
        record
        for record in records
        if (((record.get("patch_comparison") or {}).get("llm") or {}).get("verdict") == "bugrc_patch_better")
    ]
    (root / "bugrc_patch_better.enhanced.json").write_text(
        json.dumps(better_records, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"merged={merged_path}")
    print(f"bugrc_patch_better={root / 'bugrc_patch_better.enhanced.json'} count={len(better_records)}")
    return 0


def load_records(shards_root: Path) -> list[dict[str, Any]]:
    records_by_id: dict[str, dict[str, Any]] = {}
    for result_path in sorted(shards_root.glob("shard_*/results.jsonl")):
        for line in result_path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            local_id = str(record.get("local_id") or "")
            if not local_id:
                continue
            previous = records_by_id.get(local_id)
            if previous is None or record_quality(record) >= record_quality(previous):
                records_by_id[local_id] = record
    return list(records_by_id.values())


def record_quality(record: dict[str, Any]) -> tuple[int, float]:
    status = str(record.get("status") or "")
    comparison = record.get("patch_comparison") or {}
    quality = 0
    if status == "completed":
        quality += 100
    if comparison.get("status") == "semantic_judged":
        quality += 20
    if comparison.get("status") == "exact_match":
        quality += 15
    if comparison.get("llm"):
        quality += 10
    return quality, float(record.get("elapsed_seconds") or 0.0)


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    status_counter: Counter[str] = Counter()
    comparison_counter: Counter[str] = Counter()
    verdict_counter: Counter[str] = Counter()
    pseudo_counter: Counter[str] = Counter()
    project_counter: Counter[str] = Counter()
    for record in records:
        status_counter[str(record.get("status"))] += 1
        project_counter[str(record.get("project") or "unknown")] += 1
        comparison = record.get("patch_comparison") or {}
        if comparison:
            comparison_counter[str(comparison.get("status"))] += 1
        verdict = (comparison.get("llm") or {}).get("verdict")
        if verdict:
            verdict_counter[str(verdict)] += 1
        generated_patch = (record.get("generated_patch") or {}).get("payload") or {}
        pseudo_counter[str(generated_patch.get("is_pseudo_patch"))] += 1
    return {
        "record_count": len(records),
        "status_distribution": dict(status_counter.most_common()),
        "patch_comparison_distribution": dict(comparison_counter.most_common()),
        "semantic_verdict_distribution": dict(verdict_counter.most_common()),
        "generated_patch_is_pseudo_distribution": dict(pseudo_counter.most_common()),
        "project_count": len(project_counter),
        "top_projects": dict(project_counter.most_common(20)),
    }


if __name__ == "__main__":
    raise SystemExit(main())
