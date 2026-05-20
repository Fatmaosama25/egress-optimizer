"""
Layer 1: Data Collection - Abstract Base Collector
===================================================
Defines the interface that all data collectors must implement.
This allows swapping between simulated and real AWS collectors.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional


@dataclass
class FileAccessRecord:
    """Represents a single file's access metadata and cost data."""
    file_id: str                          # Unique identifier
    file_name: str                        # Human-readable name
    file_size_gb: float                   # Size in gigabytes
    current_location: str                 # 'local', 'cloud_s3', 'cloud_glacier'
    access_count_today: float             # Average daily accesses
    access_count_weekly: float            # Average weekly accesses
    access_count_monthly: float           # Average monthly accesses
    last_access_date: datetime            # Last time file was accessed
    days_since_last_access: int           # Days since last access
    created_date: datetime                # When the file was created
    egress_cost_daily: float = 0.0        # Daily egress cost ($)
    egress_cost_monthly: float = 0.0      # Monthly egress cost ($)
    total_egress_volume_gb: float = 0.0   # Total GB transferred out
    last_migration_date: Optional[datetime] = None  # Last time file was moved
    tags: Dict[str, str] = field(default_factory=dict)  # Metadata tags


@dataclass
class CollectionResult:
    """Result of a data collection run."""
    timestamp: datetime
    files: List[FileAccessRecord]
    total_files: int
    total_size_gb: float
    total_egress_cost_daily: float
    total_egress_cost_monthly: float
    collection_source: str                # 'simulated' or 'aws'

    @property
    def total_size_tb(self) -> float:
        return self.total_size_gb / 1000


class BaseCollector(ABC):
    """
    Abstract base class for data collectors.
    
    Layer 1 of the 6-Layer Framework:
    - Collects file access patterns and cost data
    - Produces standardized FileAccessRecord objects
    - Can be implemented for different data sources
    """

    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def collect(self) -> CollectionResult:
        """
        Collect file access data and return a CollectionResult.
        Must be implemented by all concrete collectors.
        """
        pass

    @abstractmethod
    def get_source_name(self) -> str:
        """Return the name of this data source (e.g., 'AWS S3', 'Simulated')."""
        pass

    def _create_result(self, files: List[FileAccessRecord], source: str) -> CollectionResult:
        """Helper to create a CollectionResult from a list of files."""
        total_size = sum(f.file_size_gb for f in files)
        total_daily_cost = sum(f.egress_cost_daily for f in files)
        total_monthly_cost = sum(f.egress_cost_monthly for f in files)

        return CollectionResult(
            timestamp=datetime.now(),
            files=files,
            total_files=len(files),
            total_size_gb=total_size,
            total_egress_cost_daily=total_daily_cost,
            total_egress_cost_monthly=total_monthly_cost,
            collection_source=source,
        )
