"""
Layer 1: Data Collection - AWS/LocalStack Collector
=====================================================
Reads real file data from LocalStack S3 (or real AWS S3).
Produces the same CollectionResult format as SimulatedCollector,
so the rest of the pipeline works identically.
"""

import boto3
from datetime import datetime
from typing import List
from botocore.config import Config

from .base import BaseCollector, FileAccessRecord, CollectionResult


class AWSCollector(BaseCollector):
    """
    Collects file access data from real S3 storage (LocalStack or AWS).
    
    Reads file metadata stored as S3 object metadata tags,
    which were set by the workload generator script.
    """

    def __init__(self, config: dict):
        super().__init__(config)
        ls_config = config.get("localstack", {})
        self.pricing = config.get("pricing", {})

        self.endpoint_url = ls_config.get("endpoint_url", "http://localhost:4566")
        self.access_key = ls_config.get("access_key", "test")
        self.secret_key = ls_config.get("secret_key", "test")
        self.region = ls_config.get("region", "us-east-1")
        self.bucket = ls_config.get("cloud_bucket", "egress-cloud-data")

        self.s3 = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region,
            config=Config(signature_version="s3v4"),
        )

    def get_source_name(self) -> str:
        return f"LocalStack S3 ({self.endpoint_url})"

    def collect(self) -> CollectionResult:
        """Collect file data from S3 bucket."""
        files = []
        now = datetime.now()

        # List all objects in the bucket
        paginator = self.s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                size_bytes = obj["Size"]

                # Get metadata tags
                try:
                    head = self.s3.head_object(Bucket=self.bucket, Key=key)
                    metadata = head.get("Metadata", {})
                except Exception:
                    metadata = {}

                file_record = self._parse_file(key, size_bytes, metadata, now)
                if file_record:
                    files.append(file_record)

        return self._create_result(files, "localstack")

    def _parse_file(
        self, key: str, size_bytes: int, metadata: dict, now: datetime
    ) -> FileAccessRecord:
        """Parse S3 object + metadata into a FileAccessRecord."""
        # Read metadata (set by generate_workload.py)
        file_id = metadata.get("file_id", f"s3-{hash(key) % 10000:04d}")
        size_gb_meta = metadata.get("size_gb")
        
        # Use metadata size_gb if available (represents intended size),
        # otherwise calculate from actual S3 object size
        if size_gb_meta:
            size_gb = float(size_gb_meta)
        else:
            size_gb = round(size_bytes / (1024 ** 3), 4)

        # Access pattern from metadata
        access_today = float(metadata.get("access_today", "0"))
        access_weekly = float(metadata.get("access_weekly", "0"))
        access_monthly = float(metadata.get("access_monthly", "0"))
        days_since = int(metadata.get("days_since_access", "0"))

        # Dates
        try:
            created_date = datetime.fromisoformat(metadata.get("created_date", now.isoformat()))
        except (ValueError, TypeError):
            created_date = now

        try:
            last_access = datetime.fromisoformat(metadata.get("last_access_date", now.isoformat()))
        except (ValueError, TypeError):
            last_access = now

        # Current location
        current_location = metadata.get("current_location", "cloud_s3")

        # Calculate egress costs
        egress_per_gb = self.pricing.get("egress_per_gb", 0.09)
        if current_location != "local":
            daily_egress_gb = access_today * size_gb
            monthly_egress_gb = access_monthly * size_gb
            egress_cost_daily = daily_egress_gb * egress_per_gb
            egress_cost_monthly = monthly_egress_gb * egress_per_gb
        else:
            daily_egress_gb = 0
            monthly_egress_gb = 0
            egress_cost_daily = 0
            egress_cost_monthly = 0

        return FileAccessRecord(
            file_id=file_id,
            file_name=key,
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
            last_migration_date=None,
            tags={
                "category_hint": metadata.get("category_hint", "unknown"),
                "department": metadata.get("department", "unknown"),
            },
        )
