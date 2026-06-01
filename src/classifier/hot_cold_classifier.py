"""
Layer 3: Hot/Cold Classification Engine
========================================
Classifies files as Hot, Warm, Cold, or Archive based on
access frequency and recency thresholds from the thesis.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict
from enum import Enum

from src.collector.base import FileAccessRecord


class DataTier(Enum):
    """Data classification tiers — Binary: Hot vs Cold."""
    HOT = "HOT"
    COLD = "COLD"


# Recommended storage locations per tier
TIER_LOCATIONS = {
    DataTier.HOT: "local",
    DataTier.COLD: "cloud_s3",
}

TIER_DESCRIPTIONS = {
    DataTier.HOT: "Frequently accessed - store on local server (zero egress)",
    DataTier.COLD: "Rarely accessed - keep in cloud S3 (cheap storage)",
}


@dataclass
class ClassificationResult:
    """Result of classifying a single file."""
    file_id: str
    file_name: str
    file_size_gb: float
    current_location: str
    tier: DataTier
    recommended_location: str
    needs_migration: bool           # True if current != recommended
    migration_direction: str        # 'to_local', 'to_cloud', 'to_glacier', 'none'
    confidence: float               # 0.0 - 1.0
    reason: str                     # Human-readable explanation


@dataclass
class ClassificationReport:
    """Complete classification report for all files."""
    timestamp: datetime
    results: List[ClassificationResult]
    summary: Dict[str, int]         # Count per tier
    migration_candidates: List[ClassificationResult]  # Files that need moving
    total_files: int
    total_needing_migration: int
    size_by_tier: Dict[str, float]  # GB per tier


class HotColdClassifier:
    """
    Layer 3 of the 6-Layer Framework.
    
    Binary Classification Algorithm:
    
    IF access_frequency >= threshold AND last_access < recency_limit:
        -> HOT -> Store on Local Server (zero egress cost)
        
    ELSE:
        -> COLD -> Keep in Cloud S3 (cheap storage)
    """

    def __init__(self, config: dict):
        cls_config = config.get("classification", {})

        # Hot thresholds
        hot = cls_config.get("hot", {})
        self.hot_min_access = hot.get("min_access_per_day", 1)
        self.hot_max_days = hot.get("max_days_since_access", 30)

    def classify(self, files: List[FileAccessRecord]) -> ClassificationReport:
        """Classify all files and produce a report."""
        results = []
        summary = {t.value: 0 for t in DataTier}
        size_by_tier = {t.value: 0.0 for t in DataTier}
        migration_candidates = []

        for f in files:
            result = self._classify_file(f)
            results.append(result)
            summary[result.tier.value] += 1
            size_by_tier[result.tier.value] += f.file_size_gb
            if result.needs_migration:
                migration_candidates.append(result)

        return ClassificationReport(
            timestamp=datetime.now(),
            results=results,
            summary=summary,
            migration_candidates=migration_candidates,
            total_files=len(files),
            total_needing_migration=len(migration_candidates),
            size_by_tier={k: round(v, 2) for k, v in size_by_tier.items()},
        )

    def _classify_file(self, f: FileAccessRecord) -> ClassificationResult:
        """
        Binary classification: HOT or COLD.
        
        HOT: access >= threshold AND recent access
        COLD: everything else
        """
        # --- HOT: frequently accessed + recent ---
        if (f.access_count_today >= self.hot_min_access and
                f.days_since_last_access <= self.hot_max_days):
            tier = DataTier.HOT
            confidence = min(1.0, f.access_count_today / (self.hot_min_access * 10))
            reason = (f"Access {f.access_count_today:.1f}/day >= {self.hot_min_access}/day, "
                      f"last accessed {f.days_since_last_access} days ago (<= {self.hot_max_days})")
        # --- COLD: everything else ---
        else:
            tier = DataTier.COLD
            confidence = min(1.0, max(f.days_since_last_access, 1) / max(self.hot_max_days, 1))
            reason = (f"Access {f.access_count_today:.1f}/day or last access {f.days_since_last_access} days ago. "
                      f"Below HOT threshold -> COLD.")

        # Determine migration need
        recommended_location = TIER_LOCATIONS[tier]
        needs_migration = f.current_location != recommended_location
        migration_direction = self._get_migration_direction(
            f.current_location, recommended_location
        )

        return ClassificationResult(
            file_id=f.file_id,
            file_name=f.file_name,
            file_size_gb=f.file_size_gb,
            current_location=f.current_location,
            tier=tier,
            recommended_location=recommended_location,
            needs_migration=needs_migration,
            migration_direction=migration_direction,
            confidence=round(confidence, 2),
            reason=reason,
        )

    def _get_migration_direction(self, current: str, recommended: str) -> str:
        """Determine the migration direction."""
        if current == recommended:
            return "none"
        elif recommended == "local":
            return "to_local"
        elif recommended == "cloud_s3":
            return "to_cloud"
        return "unknown"
