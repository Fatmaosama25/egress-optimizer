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
    """Data classification tiers."""
    HOT = "HOT"
    WARM = "WARM"
    COLD = "COLD"
    ARCHIVE = "ARCHIVE"


# Recommended storage locations per tier
TIER_LOCATIONS = {
    DataTier.HOT: "local",
    DataTier.WARM: "local",
    DataTier.COLD: "cloud_s3",
    DataTier.ARCHIVE: "cloud_glacier",
}

TIER_DESCRIPTIONS = {
    DataTier.HOT: "🔥 Frequently accessed — store on local server (zero egress)",
    DataTier.WARM: "🌡️ Moderately accessed — store on local server",
    DataTier.COLD: "🧊 Rarely accessed — store in AWS S3 (cheap storage)",
    DataTier.ARCHIVE: "❄️ Almost never accessed — archive in S3 Glacier",
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
    
    Classification Algorithm (from thesis thresholds.html):
    
    IF access_frequency > 10/day AND last_access < 7 days:
        → HOT → Keep on Local Server
        
    ELSE IF access_frequency >= 1/day AND last_access < 30 days:
        → WARM → Keep on Local Server
        
    ELSE IF access_frequency < 1/week AND last_access > 30 days:
        → COLD → Move to Cloud (S3)
        
    ELSE IF access_frequency < 1/month AND last_access > 90 days:
        → ARCHIVE → Move to Cloud Archive (S3 Glacier)
    """

    def __init__(self, config: dict):
        cls_config = config.get("classification", {})

        # Hot thresholds
        hot = cls_config.get("hot", {})
        self.hot_min_access = hot.get("min_access_per_day", 10)
        self.hot_max_days = hot.get("max_days_since_access", 7)

        # Warm thresholds
        warm = cls_config.get("warm", {})
        self.warm_min_access = warm.get("min_access_per_day", 1)
        self.warm_max_days = warm.get("max_days_since_access", 30)

        # Cold thresholds
        cold = cls_config.get("cold", {})
        self.cold_max_weekly = cold.get("max_access_per_week", 1)
        self.cold_min_days = cold.get("min_days_since_access", 30)

        # Archive thresholds
        archive = cls_config.get("archive", {})
        self.archive_max_monthly = archive.get("max_access_per_month", 1)
        self.archive_min_days = archive.get("min_days_since_access", 90)

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
        Apply the classification algorithm to a single file.
        
        Decision flow:
        1. Check HOT criteria first (highest priority)
        2. Then WARM
        3. Then ARCHIVE (before COLD, since archive is stricter)
        4. Default to COLD
        """
        tier = None
        confidence = 0.0
        reason = ""

        # --- HOT: access > 10/day AND last_access < 7 days ---
        if (f.access_count_today > self.hot_min_access and
                f.days_since_last_access <= self.hot_max_days):
            tier = DataTier.HOT
            confidence = min(1.0, f.access_count_today / (self.hot_min_access * 2))
            reason = (f"Access frequency {f.access_count_today:.1f}/day > {self.hot_min_access}/day, "
                      f"last accessed {f.days_since_last_access} days ago (< {self.hot_max_days})")

        # --- WARM: access >= 1/day AND last_access < 30 days ---
        elif (f.access_count_today >= self.warm_min_access and
              f.days_since_last_access <= self.warm_max_days):
            tier = DataTier.WARM
            confidence = min(1.0, f.access_count_today / self.hot_min_access)
            reason = (f"Access frequency {f.access_count_today:.1f}/day (1-10 range), "
                      f"last accessed {f.days_since_last_access} days ago (< {self.warm_max_days})")

        # --- ARCHIVE: access < 1/month AND last_access > 90 days ---
        elif (f.access_count_monthly < self.archive_max_monthly and
              f.days_since_last_access > self.archive_min_days):
            tier = DataTier.ARCHIVE
            confidence = min(1.0, self.archive_min_days / max(f.days_since_last_access, 1))
            reason = (f"Access frequency {f.access_count_monthly:.1f}/month < {self.archive_max_monthly}/month, "
                      f"last accessed {f.days_since_last_access} days ago (> {self.archive_min_days})")

        # --- COLD: access < 1/week AND last_access > 30 days ---
        elif (f.access_count_weekly < self.cold_max_weekly and
              f.days_since_last_access > self.cold_min_days):
            tier = DataTier.COLD
            confidence = min(1.0, self.cold_min_days / max(f.days_since_last_access, 1))
            reason = (f"Access frequency {f.access_count_weekly:.1f}/week < {self.cold_max_weekly}/week, "
                      f"last accessed {f.days_since_last_access} days ago (> {self.cold_min_days})")

        # --- DEFAULT: WARM (doesn't clearly fit other categories) ---
        else:
            tier = DataTier.WARM
            confidence = 0.5
            reason = (f"Does not clearly match hot/cold/archive criteria. "
                      f"Access: {f.access_count_today:.1f}/day, "
                      f"last access: {f.days_since_last_access} days ago. Defaulting to WARM.")

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
        elif recommended == "cloud_glacier":
            return "to_glacier"
        return "unknown"
