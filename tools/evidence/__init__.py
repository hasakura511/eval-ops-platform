"""Evidence collection tools for media hint scoring."""

from .imdb_evidence import (
    IMDbEvidenceCollector,
    TitleEvidence,
    PersonEvidence,
    SearchEvidence,
    collect_media_evidence,
)

__all__ = [
    "IMDbEvidenceCollector",
    "TitleEvidence",
    "PersonEvidence",
    "SearchEvidence",
    "collect_media_evidence",
]
