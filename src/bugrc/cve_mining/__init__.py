"""Public entry points for BugRC CVE collection."""

from bugrc.cve_mining.collection import CVECollectionService
from bugrc.cve_mining.dataset import CVEDatasetBuildCase, CVERootCauseDatasetBuilder
from bugrc.cve_mining.mining import CVERootCauseMiner
from bugrc.cve_mining.patches import CVEPatchExtractor
from bugrc.cve_mining.patterns import RootCausePatternMiner
from bugrc.cve_mining.semantic_alignment import CVESemanticAligner
from bugrc.cve_mining.sources import (
    CVEListV5Adapter,
    CVESourceAdapter,
    CollectionSource,
    GitHubSecurityAdvisoryAdapter,
    NVDJSONFeedAdapter,
    ProjectAdvisoryAdapter,
    get_source_adapter,
)

__all__ = [
    "CVECollectionService",
    "CVEDatasetBuildCase",
    "CVERootCauseMiner",
    "CVERootCauseDatasetBuilder",
    "CVEPatchExtractor",
    "CVESemanticAligner",
    "RootCausePatternMiner",
    "CVEListV5Adapter",
    "CVESourceAdapter",
    "CollectionSource",
    "GitHubSecurityAdvisoryAdapter",
    "NVDJSONFeedAdapter",
    "ProjectAdvisoryAdapter",
    "get_source_adapter",
]
