"""Patch-aware analysis exports."""

from bugrc.patch_analysis.analyzer import PatchAwareAnalyzer
from bugrc.patch_analysis.classifier import PatchIntentClassifier
from bugrc.patch_analysis.models import (
    MappedPatchLocation,
    ParsedPatch,
    PatchAwareAnalysisResult,
    PatchHunk,
    PatchLine,
    PatchedFile,
)
from bugrc.patch_analysis.parser import UnifiedDiffParser

__all__ = [
    "MappedPatchLocation",
    "ParsedPatch",
    "PatchAwareAnalysisResult",
    "PatchAwareAnalyzer",
    "PatchHunk",
    "PatchIntentClassifier",
    "PatchLine",
    "PatchedFile",
    "UnifiedDiffParser",
]
