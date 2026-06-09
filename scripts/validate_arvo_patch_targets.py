#!/usr/bin/env python3
"""Best-effort patch application, build, and OSS-Fuzz reproducer validation for ARVO cases."""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import json
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--targets-json", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--repos-dir", required=True, type=Path)
    parser.add_argument("--repo-lock-dir", required=True, type=Path)
    parser.add_argument("--oss-fuzz-dir", required=True, type=Path)
    parser.add_argument("--max-targets", type=int, default=50)
    parser.add_argument("--start-index", type=int, default=0)
    parser.add_argument("--git-timeout", type=int, default=120)
    parser.add_argument("--download-timeout", type=int, default=120)
    parser.add_argument("--build-image-timeout", type=int, default=1800)
    parser.add_argument("--build-timeout", type=int, default=2400)
    parser.add_argument("--reproduce-timeout", type=int, default=600)
    parser.add_argument("--skip-docker", action="store_true")
    parser.add_argument("--force", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    payload = json.loads(args.targets_json.read_text(encoding="utf-8"))
    targets = payload.get("targets", payload)
    if not isinstance(targets, list):
        raise ValueError("targets JSON must contain a targets list")
    selected = targets[args.start_index : args.start_index + args.max_targets]

    args.output_dir.mkdir(parents=True, exist_ok=True)
    results_path = args.output_dir / "validation_results.jsonl"
    done = set() if args.force else load_done_ids(results_path)

    for index, target in enumerate(selected, start=args.start_index):
        local_id = str(target["local_id"])
        if local_id in done:
            print(f"[{index}] {local_id}: already done", flush=True)
            continue
        print(f"[{index}] {local_id}: validating", flush=True)
        started = time.time()
        try:
            result = validate_one(target, args)
            result["status"] = "completed"
        except Exception as exc:
            result = {
                "local_id": local_id,
                "project": target.get("project"),
                "status": "failed",
                "error": f"{type(exc).__name__}: {exc}",
            }
        result["elapsed_seconds"] = round(time.time() - started, 3)
        append_jsonl(results_path, result)
        write_summary(results_path, args.output_dir / "validation_summary.json")
        print(f"[{index}] {local_id}: {result.get('status')}", flush=True)

    write_summary(results_path, args.output_dir / "validation_summary.json")
    return 0


def validate_one(target: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    local_id = str(target["local_id"])
    project = str(target.get("project") or "")
    repo_url = str(target.get("repo_url") or "")
    fix_commit = str(target.get("fix_commit") or "")
    case_dir = args.output_dir / "cases" / local_id
    case_dir.mkdir(parents=True, exist_ok=True)

    repo = ensure_repo(repo_url, args.repos_dir, args.repo_lock_dir, args.git_timeout)
    variants = {
        "base": prepare_worktree(repo, args.repo_lock_dir, case_dir, "base", fix_commit, args.git_timeout),
        "official": prepare_worktree(repo, args.repo_lock_dir, case_dir, "official", fix_commit, args.git_timeout),
        "bugrc": prepare_worktree(repo, args.repo_lock_dir, case_dir, "bugrc", fix_commit, args.git_timeout),
    }

    official_patch = Path(str(target.get("official_patch_path") or ""))
    bugrc_patch = case_dir / "bugrc_generated.patch"
    bugrc_patch.write_text(str(target.get("generated_patch_diff") or ""), encoding="utf-8")

    patch_results = {
        "official": apply_patch(variants["official"], official_patch, args.git_timeout, allow_fuzzy=False),
        "bugrc": apply_patch(variants["bugrc"], bugrc_patch, args.git_timeout, allow_fuzzy=True),
    }
    testcase_path = download_testcase(target, case_dir, args.download_timeout)
    docker_results: dict[str, Any] = {}

    can_docker = (
        not args.skip_docker
        and target.get("has_oss_fuzz_project") is True
        and bool(target.get("fuzzer_name"))
        and testcase_path is not None
    )
    if can_docker:
        docker_results["build_image"] = build_image(project, args)
        docker_results["base"] = build_and_reproduce(
            project=project,
            variant="base",
            source_path=variants["base"],
            testcase_path=testcase_path,
            fuzzer_name=str(target["fuzzer_name"]),
            sanitizer=str(target.get("oss_fuzz_sanitizer") or "address"),
            args=args,
        )
        base_build = docker_results["base"].get("build") or {}
        if base_build.get("returncode") != 0:
            # If the vulnerable revision cannot build in the current OSS-Fuzz
            # environment, reproducer comparison is not meaningful.
            for variant_name in ("official", "bugrc"):
                docker_results[variant_name] = {"skipped": True, "reason": "base build failed"}
        else:
            for variant_name in ("official", "bugrc"):
                source_path = variants[variant_name]
                if not patch_results[variant_name].get("applied"):
                    docker_results[variant_name] = {"skipped": True, "reason": "patch did not apply"}
                    continue
                docker_results[variant_name] = build_and_reproduce(
                    project=project,
                    variant=variant_name,
                    source_path=source_path,
                    testcase_path=testcase_path,
                    fuzzer_name=str(target["fuzzer_name"]),
                    sanitizer=str(target.get("oss_fuzz_sanitizer") or "address"),
                    args=args,
                )
    else:
        docker_results["skipped"] = True
        docker_results["reason"] = docker_skip_reason(target, args, testcase_path)

    conclusion = classify_result(patch_results, docker_results)
    return {
        "local_id": local_id,
        "project": project,
        "repo_url": repo_url,
        "fix_commit": fix_commit,
        "confidence": target.get("confidence"),
        "crash_type": target.get("crash_type"),
        "sanitizer": target.get("sanitizer"),
        "fuzzer_name": target.get("fuzzer_name"),
        "testcase_url": target.get("testcase_url"),
        "testcase_path": testcase_path.as_posix() if testcase_path else None,
        "trigger": target.get("trigger"),
        "patch_apply": patch_results,
        "docker_validation": docker_results,
        "conclusion": conclusion,
    }


def ensure_repo(repo_url: str, repos_dir: Path, lock_dir: Path, timeout: int) -> Path:
    parsed = urlparse(repo_url)
    key_parts = [parsed.netloc or "unknown"] + [part for part in parsed.path.strip("/").split("/") if part]
    if key_parts[-1].endswith(".git"):
        key_parts[-1] = key_parts[-1][:-4]
    repo_path = repos_dir.joinpath(*key_parts)
    with file_lock(lock_dir, lock_name(repo_path)):
        if (repo_path / ".git").exists():
            run(["git", "fetch", "--filter=blob:none", "origin"], cwd=repo_path, timeout=timeout, check=False)
            return repo_path
        repo_path.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", "--filter=blob:none", repo_url, repo_path.as_posix()], cwd=repos_dir, timeout=timeout)
    return repo_path


def prepare_worktree(repo: Path, lock_dir: Path, case_dir: Path, variant: str, fix_commit: str, timeout: int) -> Path:
    path = case_dir / variant / repo.name
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    with file_lock(lock_dir, lock_name(repo)):
        if path.exists():
            return path
        run(["git", "worktree", "prune"], cwd=repo, timeout=timeout, check=False)
        run(["git", "fetch", "origin", fix_commit, "--depth", "2"], cwd=repo, timeout=timeout, check=False)
        pre_fix_ref = f"{fix_commit}^"
        run(["git", "worktree", "add", "--detach", path.as_posix(), pre_fix_ref], cwd=repo, timeout=timeout)
    return path


def apply_patch(worktree: Path, patch_path: Path, timeout: int, *, allow_fuzzy: bool) -> dict[str, Any]:
    if not patch_path.exists() or patch_path.stat().st_size == 0:
        return {"applied": False, "reason": "missing_or_empty_patch", "patch_path": patch_path.as_posix()}
    check = run(["git", "apply", "--check", patch_path.as_posix()], cwd=worktree, timeout=timeout, check=False)
    if check.returncode != 0:
        if allow_fuzzy:
            fuzzy = fuzzy_apply_patch(worktree, patch_path)
            if fuzzy.get("applied"):
                diff_check = run(["git", "diff", "--check"], cwd=worktree, timeout=timeout, check=False)
                fuzzy.update(
                    {
                        "patch_path": patch_path.as_posix(),
                        "raw_git_apply_stderr": check.stderr[-4000:],
                        "diff_check_returncode": diff_check.returncode,
                        "diff_check_stderr": diff_check.stderr[-4000:],
                    }
                )
                return fuzzy
        return {
            "applied": False,
            "reason": "git_apply_check_failed",
            "patch_path": patch_path.as_posix(),
            "stdout": check.stdout[-4000:],
            "stderr": check.stderr[-4000:],
        }
    applied = run(["git", "apply", patch_path.as_posix()], cwd=worktree, timeout=timeout, check=False)
    diff_check = run(["git", "diff", "--check"], cwd=worktree, timeout=timeout, check=False)
    return {
        "applied": applied.returncode == 0,
        "reason": "applied" if applied.returncode == 0 else "git_apply_failed",
        "patch_path": patch_path.as_posix(),
        "stdout": applied.stdout[-4000:],
        "stderr": applied.stderr[-4000:],
        "diff_check_returncode": diff_check.returncode,
        "diff_check_stderr": diff_check.stderr[-4000:],
    }


def fuzzy_apply_patch(worktree: Path, patch_path: Path) -> dict[str, Any]:
    """Apply simple generated diffs by replacing exact old blocks in source files."""
    text = patch_path.read_text(encoding="utf-8", errors="replace")
    file_patches = parse_generated_file_patches(text)
    applied = 0
    failures: list[dict[str, Any]] = []
    for file_patch in file_patches:
        rel_path = file_patch["file"]
        path = worktree / rel_path
        if not path.exists():
            failures.append({"file": rel_path, "reason": "file_not_found"})
            continue
        original = path.read_text(encoding="utf-8", errors="replace")
        updated = original
        file_applied = 0
        for hunk in file_patch["hunks"]:
            old_text = "\n".join(hunk["old_lines"])
            new_text = "\n".join(hunk["new_lines"])
            if old_text and not old_text.endswith("\n"):
                old_text += "\n"
            if new_text and not new_text.endswith("\n"):
                new_text += "\n"
            if old_text and old_text in updated:
                updated = updated.replace(old_text, new_text, 1)
                file_applied += 1
                continue
            compact_old = "\n".join(line for line in hunk["old_lines"] if line.strip())
            compact_new = "\n".join(line for line in hunk["new_lines"] if line.strip())
            if compact_old and compact_old in updated:
                updated = updated.replace(compact_old, compact_new, 1)
                file_applied += 1
                continue
            failures.append({"file": rel_path, "reason": "old_block_not_found", "old_preview": old_text[:500]})
        if file_applied:
            path.write_text(updated, encoding="utf-8")
            applied += file_applied
    return {
        "applied": applied > 0 and not failures,
        "reason": "fuzzy_applied" if applied > 0 and not failures else "fuzzy_apply_incomplete",
        "applied_method": "fuzzy_block_replace",
        "applied_hunks": applied,
        "failures": failures[:20],
    }


def parse_generated_file_patches(text: str) -> list[dict[str, Any]]:
    lines = text.splitlines()
    patches: list[dict[str, Any]] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.startswith("--- a/"):
            index += 1
            continue
        old_file = line.removeprefix("--- a/").strip()
        index += 1
        if index >= len(lines) or not lines[index].startswith("+++ b/"):
            continue
        new_file = lines[index].removeprefix("+++ b/").strip()
        rel_file = new_file or old_file
        index += 1
        hunks: list[dict[str, list[str]]] = []
        current: dict[str, list[str]] | None = None
        while index < len(lines) and not lines[index].startswith("--- a/"):
            hunk_line = lines[index]
            if hunk_line.startswith("@@"):
                if current and (current["old_lines"] or current["new_lines"]):
                    hunks.append(current)
                current = {"old_lines": [], "new_lines": []}
            elif current is not None:
                if hunk_line.startswith("-") and not hunk_line.startswith("---"):
                    current["old_lines"].append(hunk_line[1:])
                elif hunk_line.startswith("+") and not hunk_line.startswith("+++"):
                    current["new_lines"].append(hunk_line[1:])
                elif hunk_line.startswith(" "):
                    current["old_lines"].append(hunk_line[1:])
                    current["new_lines"].append(hunk_line[1:])
            index += 1
        if current and (current["old_lines"] or current["new_lines"]):
            hunks.append(current)
        patches.append({"file": rel_file, "hunks": hunks})
    return patches


def download_testcase(target: dict[str, Any], case_dir: Path, timeout: int) -> Path | None:
    url = target.get("testcase_url")
    if not url:
        return None
    out = case_dir / "reproducer.testcase"
    if out.exists() and out.stat().st_size > 0:
        return out
    try:
        with urllib.request.urlopen(str(url), timeout=timeout) as response:
            out.write_bytes(response.read())
        return out if out.exists() and out.stat().st_size > 0 else None
    except OSError:
        return None


def build_image(project: str, args: argparse.Namespace) -> dict[str, Any]:
    with file_lock(args.repo_lock_dir, f"oss-fuzz-image-{project}"):
        proc = run(
            ["python3", "infra/helper.py", "build_image", "--no-pull", project],
            cwd=args.oss_fuzz_dir,
            timeout=args.build_image_timeout,
            check=False,
        )
    return proc_payload(proc)


def build_and_reproduce(
    *,
    project: str,
    variant: str,
    source_path: Path,
    testcase_path: Path,
    fuzzer_name: str,
    sanitizer: str,
    args: argparse.Namespace,
) -> dict[str, Any]:
    # OSS-Fuzz helper writes to shared build/out/<project> and build/work/<project>.
    # Keep variants/shards for the same project serialized to avoid cross-case races.
    with file_lock(args.repo_lock_dir, f"oss-fuzz-build-{project}"):
        build_proc = run(
            [
                "python3",
                "infra/helper.py",
                "build_fuzzers",
                "--engine",
                "libfuzzer",
                "--sanitizer",
                sanitizer,
                project,
                source_path.as_posix(),
            ],
            cwd=args.oss_fuzz_dir,
            timeout=args.build_timeout,
            check=False,
        )
        reproduce_payload: dict[str, Any] | None = None
        if build_proc.returncode == 0:
            reproduce_proc = run(
                [
                    "python3",
                    "infra/helper.py",
                    "reproduce",
                    "-e",
                    "RUN_FUZZER_MODE=interactive",
                    project,
                    fuzzer_name,
                    testcase_path.as_posix(),
                ],
                cwd=args.oss_fuzz_dir,
                timeout=args.reproduce_timeout,
                check=False,
            )
            reproduce_payload = proc_payload(reproduce_proc)
    return {
        "variant": variant,
        "source_path": source_path.as_posix(),
        "build": proc_payload(build_proc),
        "reproduce": reproduce_payload,
    }


def docker_skip_reason(target: dict[str, Any], args: argparse.Namespace, testcase_path: Path | None) -> str:
    if args.skip_docker:
        return "skip_docker_requested"
    if target.get("has_oss_fuzz_project") is not True:
        return "missing_oss_fuzz_project"
    if not target.get("fuzzer_name"):
        return "missing_fuzzer_name"
    if testcase_path is None:
        return "missing_or_unavailable_testcase"
    return "unknown"


def classify_result(patches: dict[str, Any], docker: dict[str, Any]) -> dict[str, Any]:
    official_applies = patches.get("official", {}).get("applied") is True
    bugrc_applies = patches.get("bugrc", {}).get("applied") is True
    base_build = docker.get("base", {}).get("build")
    official_build = docker.get("official", {}).get("build")
    bugrc_build = docker.get("bugrc", {}).get("build")
    official_repro = docker.get("official", {}).get("reproduce")
    bugrc_repro = docker.get("bugrc", {}).get("reproduce")
    base_repro = docker.get("base", {}).get("reproduce")
    official_crashes = crashed(official_repro)
    bugrc_crashes = crashed(bugrc_repro)
    base_crashes = crashed(base_repro)
    verdict = "patch_apply_only"
    if docker.get("skipped"):
        verdict = "docker_skipped"
    elif base_build is not None and base_build.get("returncode") != 0:
        verdict = "base_build_failed"
    elif base_repro is None and base_build is not None:
        verdict = "base_reproducer_missing"
    elif base_repro is not None:
        if not base_crashes:
            verdict = "reproducer_did_not_trigger_base"
        elif official_build is not None and official_build.get("returncode") != 0:
            verdict = "official_build_failed"
        elif bugrc_build is not None and bugrc_build.get("returncode") != 0:
            verdict = "bugrc_build_failed"
        elif official_repro is None:
            verdict = "official_reproducer_missing"
        elif bugrc_repro is None:
            verdict = "bugrc_reproducer_missing"
        elif base_crashes and official_crashes and not bugrc_crashes:
            verdict = "validated_official_incomplete_bugrc_fixes"
        elif base_crashes and not official_crashes and not bugrc_crashes:
            verdict = "both_fix_reproducer"
        elif base_crashes and not official_crashes and bugrc_crashes:
            verdict = "official_fixes_bugrc_does_not"
        else:
            verdict = "reproducer_inconclusive"
    return {
        "verdict": verdict,
        "official_patch_applies": official_applies,
        "bugrc_patch_applies": bugrc_applies,
        "base_crashes": base_crashes,
        "official_crashes": official_crashes,
        "bugrc_crashes": bugrc_crashes,
        "base_build_returncode": build_returncode(base_build),
        "official_build_returncode": build_returncode(official_build),
        "bugrc_build_returncode": build_returncode(bugrc_build),
    }


def crashed(payload: dict[str, Any] | None) -> bool | None:
    if payload is None:
        return None
    output = f"{payload.get('stdout', '')}\n{payload.get('stderr', '')}"
    if "ERROR: " in output or "runtime error:" in output or "AddressSanitizer" in output:
        return True
    if payload.get("returncode") not in (0, None):
        return True
    return False


def build_returncode(payload: dict[str, Any] | None) -> int | None:
    if payload is None:
        return None
    value = payload.get("returncode")
    return value if isinstance(value, int) else None


def run(command: list[str], *, cwd: Path, timeout: int, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=check,
    )


def proc_payload(proc: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout[-8000:],
        "stderr": proc.stderr[-8000:],
    }


@contextlib.contextmanager
def file_lock(lock_dir: Path, name: str) -> Iterable[None]:
    lock_dir.mkdir(parents=True, exist_ok=True)
    path = lock_dir / f"{name}.lock"
    with path.open("w", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def lock_name(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.as_posix().encode("utf-8")).hexdigest()


def load_done_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    done = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if payload.get("local_id"):
            done.add(str(payload["local_id"]))
    return done


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def write_summary(results_path: Path, summary_path: Path) -> None:
    records = load_records(results_path)
    from collections import Counter

    summary = {
        "record_count": len(records),
        "status_distribution": dict(Counter(record.get("status") for record in records)),
        "conclusion_distribution": dict(Counter((record.get("conclusion") or {}).get("verdict") for record in records)),
        "official_patch_applies": dict(Counter(str((record.get("conclusion") or {}).get("official_patch_applies")) for record in records)),
        "bugrc_patch_applies": dict(Counter(str((record.get("conclusion") or {}).get("bugrc_patch_applies")) for record in records)),
    }
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")


def load_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


if __name__ == "__main__":
    raise SystemExit(main())
