"""Tests for the Magma benchmark adapter."""

from __future__ import annotations

from pathlib import Path

from scripts.magma_bugrc_eval import materialize_magma_buggy_source, parse_magma_patch


def test_parse_magma_patch_extracts_files_functions_and_canaries(tmp_path: Path) -> None:
    patch = tmp_path / "PNG001.patch"
    patch.write_text(
        """diff --git a/pngrutil.c b/pngrutil.c
--- a/pngrutil.c
+++ b/pngrutil.c
@@ -10,4 +10,12 @@ png_check_chunk_length(png_const_structrp png_ptr, png_uint_32 length)
+#ifdef MAGMA_ENABLE_CANARIES
+      MAGMA_LOG("%MAGMA_BUG%", row_factor_l == ((size_t)1 << 32));
+#endif
""",
        encoding="utf-8",
    )

    files, functions, canaries = parse_magma_patch(patch)

    assert files == ["pngrutil.c"]
    assert functions == ["png_check_chunk_length"]
    assert canaries == ["row_factor_l == ((size_t)1 << 32)"]


def test_materialize_magma_buggy_source_keeps_vulnerable_branch() -> None:
    source = """int f(int x) {
#ifdef MAGMA_ENABLE_FIXES
  return x > 0 ? x : 0;
#else
  return 10 / x;
#endif
#ifndef MAGMA_ENABLE_FIXES
  x--;
#endif
}
"""

    materialized = materialize_magma_buggy_source(source)

    assert "return 10 / x;" in materialized
    assert "x--;" in materialized
    assert "return x > 0 ? x : 0;" not in materialized
    assert "MAGMA_ENABLE_FIXES" not in materialized
