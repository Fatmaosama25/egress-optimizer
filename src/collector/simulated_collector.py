"""
Layer 1: Data Collection - Simulated Collector
===============================================
Generates realistic synthetic data for local testing.
Produces the same data format as the real AWS collector,
allowing the full pipeline to run without AWS credentials.
"""

import random
import math
from datetime import datetime, timedelta
from typing import List

from .base import BaseCollector, FileAccessRecord, CollectionResult


# Realistic file name patterns
FILE_PREFIXES = [
    "customer_data", "analytics_report", "transaction_log", "user_profile",
    "product_catalog", "inventory_snapshot", "sales_data", "marketing_assets",
    "backup_db", "audit_log", "media_assets", "config_backup",
    "ml_training_data", "api_logs", "session_data", "payment_records",
    "email_archive", "document_store", "image_repository", "video_archive",
    "compliance_records", "hr_data", "financial_report", "support_tickets",
    "sensor_data", "iot_telemetry", "web_crawl_data", "search_index",
]

FILE_EXTENSIONS = [".parquet", ".csv", ".json", ".tar.gz", ".sql", ".avro", ".log"]


class SimulatedCollector(BaseCollector):
    """
    Generates realistic simulated file data for testing the optimization pipeline.
    
    Creates files with varied:
    - Sizes (100MB to 50GB)
    - Access patterns (hot, warm, cold, archive)
    - Locations (local, cloud_s3, cloud_glacier)
    - Ages (1 to 120 days)
    
    The distribution roughly follows real-world patterns:
    - ~20% hot data (accessed frequently, small to medium)
    - ~15% warm data (moderate access)
    - ~40% cold data (rarely accessed)
    - ~25% archive data (almost never accessed, often large)
    """

    def __init__(self, config: dict):
        super().__init__(config)
        sim_config = config.get("simulation", {})
        self.num_files = sim_config.get("num_files", 80)
        self.min_size_gb = sim_config.get("min_file_size_gb", 0.1)
        self.max_size_gb = sim_config.get("max_file_size_gb", 50)
        self.time_range_days = sim_config.get("time_range_days", 120)
        self.seed = sim_config.get("seed", 42)
        self.pricing = config.get("pricing", {})

    def get_source_name(self) -> str:
        return "Simulated"

    def collect(self) -> CollectionResult:
        """Generate simulated file access data."""
        random.seed(self.seed)
        now = datetime.now()
        files = []

        for i in range(self.num_files):
            file_record = self._generate_file(i, now)
            files.append(file_record)

        return self._create_result(files, "simulated")

    def _generate_file(self, index: int, now: datetime) -> FileAccessRecord:
        """Generate a single simulated file with realistic properties."""
        # Determine file category (weighted distribution)
        category = random.choices(
            ["hot", "warm", "cold", "archive"],
            weights=[20, 15, 40, 25],
            k=1
        )[0]

        # File identity
        prefix = random.choice(FILE_PREFIXES)
        ext = random.choice(FILE_EXTENSIONS)
        file_name = f"{prefix}_{index:03d}{ext}"
        file_id = f"file-{index:04d}"

        # File size varies by category
        size_gb = self._generate_size(category)

        # Access patterns based on category
        access_today, access_weekly, access_monthly, days_since = \
            self._generate_access_pattern(category)

        # File age
        created_days_ago = random.randint(
            max(days_since, 1),
            self.time_range_days
        )
        created_date = now - timedelta(days=created_days_ago)
        last_access = now - timedelta(days=days_since)

        # Current location (simulates pre-existing placement — not yet optimized)
        current_location = self._initial_location(category)

        # Calculate egress costs
        egress_per_gb = self.pricing.get("egress_per_gb", 0.09)
        daily_egress_gb = access_today * size_gb
        monthly_egress_gb = access_monthly * size_gb
        egress_cost_daily = daily_egress_gb * egress_per_gb if current_location != "local" else 0
        egress_cost_monthly = monthly_egress_gb * egress_per_gb if current_location != "local" else 0

        # Possible previous migration
        migration_date = None
        if random.random() < 0.1:  # 10% of files have been migrated before
            migration_date = now - timedelta(days=random.randint(1, 60))

        return FileAccessRecord(
            file_id=file_id,
            file_name=file_name,
            file_size_gb=round(size_gb, 2),
            current_location=current_location,
            access_count_today=round(access_today, 1),
            access_count_weekly=round(access_weekly, 1),
            access_count_monthly=round(access_monthly, 1),
            last_access_date=last_access,
            days_since_last_access=days_since,
            created_date=created_date,
            egress_cost_daily=round(egress_cost_daily, 2),
            egress_cost_monthly=round(egress_cost_monthly, 2),
            total_egress_volume_gb=round(monthly_egress_gb, 2),
            last_migration_date=migration_date,
            tags={"category_hint": category, "department": random.choice(
                ["engineering", "marketing", "finance", "operations", "analytics"]
            )},
        )

    def _generate_size(self, category: str) -> float:
        """Generate file size based on category (archive tends to be larger)."""
        if category == "hot":
            return random.uniform(0.1, 10)       # 100MB - 10GB
        elif category == "warm":
            return random.uniform(0.5, 20)        # 500MB - 20GB
        elif category == "cold":
            return random.uniform(1, 30)          # 1GB - 30GB
        else:  # archive
            return random.uniform(5, 50)          # 5GB - 50GB

    def _generate_access_pattern(self, category: str):
        """Generate access frequency and recency for a given category."""
        if category == "hot":
            access_today = random.uniform(12, 100)
            access_weekly = access_today * 7 * random.uniform(0.8, 1.0)
            access_monthly = access_weekly * 4.3 * random.uniform(0.8, 1.0)
            days_since = random.randint(0, 3)
        elif category == "warm":
            access_today = random.uniform(1.5, 9)
            access_weekly = access_today * 7 * random.uniform(0.6, 0.9)
            access_monthly = access_weekly * 4.3 * random.uniform(0.6, 0.9)
            days_since = random.randint(1, 15)
        elif category == "cold":
            access_today = random.uniform(0, 0.12)  # < 1/week
            access_weekly = random.uniform(0.1, 0.9)
            access_monthly = access_weekly * 4.3 * random.uniform(0.5, 1.0)
            days_since = random.randint(31, 80)
        else:  # archive
            access_today = random.uniform(0, 0.03)  # < 1/month
            access_weekly = random.uniform(0, 0.2)
            access_monthly = random.uniform(0.1, 0.8)
            days_since = random.randint(91, 120)

        return access_today, access_weekly, access_monthly, days_since

    def _initial_location(self, category: str) -> str:
        """
        Simulate pre-optimization placement.
        In the 'before' state, most data is in the cloud (the problem we're solving).
        """
        # 80% of all data starts in cloud (simulating the unoptimized state)
        if random.random() < 0.80:
            return "cloud_s3"
        elif random.random() < 0.5:
            return "local"
        else:
            return "cloud_glacier"
