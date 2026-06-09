"""Regression tests for the CVE dataset/pattern build script helpers."""

from __future__ import annotations

import importlib.util
import logging
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_cve_dataset_and_patterns.py"
SPEC = importlib.util.spec_from_file_location("build_cve_dataset_and_patterns", SCRIPT_PATH)
if SPEC is None or SPEC.loader is None:  # pragma: no cover - defensive import path
    raise RuntimeError(f"Unable to load build script module from {SCRIPT_PATH}")
BUILD_SCRIPT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILD_SCRIPT)


class CVEBuildScriptTests(unittest.TestCase):
    def test_collect_builder_stage_artifacts_only_returns_existing_stage_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            collection_path = temp_root / "collection.json"
            patch_path = temp_root / "patches.json"
            mining_path = temp_root / "mining.json"
            semantic_path = temp_root / "semantic.json"
            for path in (collection_path, mining_path):
                path.write_text("{}", encoding="utf-8")

            artifacts = BUILD_SCRIPT.collect_builder_stage_artifacts(
                collection_result_path=collection_path,
                patch_extractions_path=patch_path,
                mining_results_path=mining_path,
                semantic_alignments_path=semantic_path,
            )

            self.assertEqual(
                {path.as_posix() for path in artifacts},
                {collection_path.as_posix(), mining_path.as_posix()},
            )

    def test_cleanup_stage_artifacts_removes_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            stage_path = temp_root / "stage.json"
            stage_path.write_text("{}", encoding="utf-8")

            BUILD_SCRIPT.cleanup_stage_artifacts([stage_path], logger=logging.getLogger("test"))

            self.assertFalse(stage_path.exists())


if __name__ == "__main__":
    unittest.main()
