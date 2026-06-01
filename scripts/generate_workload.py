"""
Workload Generator — Phase 2
==============================
Creates realistic test data in LocalStack S3 and MinIO.
Uploads files with metadata tags matching the simulation patterns.

Usage:
    python scripts/generate_workload.py
"""

import boto3
import json
import random
import os
import sys
import yaml
from datetime import datetime, timedelta
from botocore.config import Config

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_config():
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "config", "config.yaml"
    )
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def create_s3_client(endpoint_url, access_key, secret_key, region="us-east-1"):
    """Create an S3 client for either LocalStack or MinIO."""
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region,
        config=Config(signature_version="s3v4"),
    )


# File name patterns (same as simulated_collector.py)
FILE_PREFIXES = [
    "customer_data", "analytics_report", "transaction_log", "user_profile",
    "product_catalog", "inventory_snapshot", "sales_data", "marketing_assets",
    "backup_db", "audit_log", "media_assets", "config_backup",
    "ml_training_data", "api_logs", "session_data", "payment_records",
    "email_archive", "document_store", "image_repository", "video_archive",
    "compliance_records", "hr_data", "financial_report", "support_tickets",
    "sensor_data", "iot_telemetry", "web_crawl_data", "search_index",
]

DEPARTMENTS = ["engineering", "marketing", "finance", "operations", "analytics"]


def generate_file_content(size_mb):
    """Generate random binary content of a given size (in MB).
    For small sizes, generates actual data. For large sizes, repeats a pattern.
    """
    # Cap actual generation at 1MB, use metadata to record intended size
    actual_size = min(size_mb, 1)
    chunk = os.urandom(1024)  # 1KB random chunk
    repeats = int(actual_size * 1024)  # number of KB
    return chunk * max(repeats, 1)


def generate_workload(config):
    """Upload test files to LocalStack S3 (simulating cloud storage)."""
    ls_config = config["localstack"]
    sim_config = config.get("simulation", {})

    # Create LocalStack S3 client
    s3 = create_s3_client(
        ls_config["endpoint_url"],
        ls_config["access_key"],
        ls_config["secret_key"],
        ls_config.get("region", "us-east-1"),
    )

    bucket = ls_config["cloud_bucket"]
    num_files = sim_config.get("num_files", 80)
    seed = sim_config.get("seed", 42)
    random.seed(seed)
    now = datetime.now()

    # Create bucket
    try:
        s3.create_bucket(Bucket=bucket)
        print(f"  [OK] Created bucket: {bucket}")
    except s3.exceptions.BucketAlreadyOwnedByYou:
        print(f"  [OK] Bucket already exists: {bucket}")
    except Exception:
        print(f"  [OK] Using existing bucket: {bucket}")

    print(f"\n  Uploading {num_files} test files...\n")

    files_metadata = []

    for i in range(num_files):
        # Determine category (binary: hot or cold)
        category = random.choices(
            ["hot", "cold"],
            weights=[40, 60],
            k=1
        )[0]

        # File identity
        prefix = random.choice(FILE_PREFIXES)
        ext = random.choice([".parquet", ".csv", ".json", ".tar.gz", ".sql", ".log"])
        file_name = f"{prefix}_{i:03d}{ext}"
        file_id = f"file-{i:04d}"

        # File size (in GB for metadata, MB for actual upload)
        size_gb = _generate_size(category)
        size_mb = max(0.01, size_gb * 0.01)  # Scale down for test (10KB-500KB actual)

        # Access pattern
        access_today, access_weekly, access_monthly, days_since = \
            _generate_access_pattern(category)

        # Dates
        created_days_ago = random.randint(max(days_since, 1), 120)
        created_date = now - timedelta(days=created_days_ago)
        last_access = now - timedelta(days=days_since)

        # Location — 80% start in cloud (the problem we solve)
        if random.random() < 0.80:
            location = "cloud_s3"
        elif random.random() < 0.5:
            location = "local"
        else:
            location = "cloud_glacier"

        department = random.choice(DEPARTMENTS)

        # Metadata stored as S3 tags
        metadata = {
            "file_id": file_id,
            "category_hint": category,
            "department": department,
            "size_gb": str(round(size_gb, 2)),
            "access_today": str(round(access_today, 1)),
            "access_weekly": str(round(access_weekly, 1)),
            "access_monthly": str(round(access_monthly, 1)),
            "days_since_access": str(days_since),
            "created_date": created_date.isoformat(),
            "last_access_date": last_access.isoformat(),
            "current_location": location,
        }

        # Generate and upload file content
        content = generate_file_content(size_mb)

        s3.put_object(
            Bucket=bucket,
            Key=file_name,
            Body=content,
            Metadata=metadata,
        )

        files_metadata.append({
            "file_id": file_id,
            "file_name": file_name,
            "size_gb": round(size_gb, 2),
            "category": category,
            "department": department,
            "location": location,
            "access_today": round(access_today, 1),
            "days_since_access": days_since,
        })

        # Progress indicator
        bar_len = 30
        progress = (i + 1) / num_files
        filled = int(bar_len * progress)
        bar = "#" * filled + "-" * (bar_len - filled)
        print(f"\r  [{bar}] {i+1}/{num_files} - {file_name}", end="", flush=True)

    print(f"\n\n  [OK] Uploaded {num_files} files to LocalStack S3")

    # Save metadata index
    index_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "workload_index.json"
    )
    os.makedirs(os.path.dirname(index_path), exist_ok=True)
    with open(index_path, "w") as f:
        json.dump({"generated_at": now.isoformat(), "files": files_metadata}, f, indent=2)
    print(f"  [OK] Saved metadata index: data/workload_index.json")

    return files_metadata


def setup_minio(config):
    """Create the local storage bucket in MinIO."""
    minio_config = config["minio"]

    s3 = create_s3_client(
        minio_config["endpoint_url"],
        minio_config["access_key"],
        minio_config["secret_key"],
    )

    bucket = minio_config["local_bucket"]
    try:
        s3.create_bucket(Bucket=bucket)
        print(f"  [OK] Created MinIO bucket: {bucket}")
    except Exception:
        print(f"  [OK] MinIO bucket already exists: {bucket}")


def _generate_size(category):
    if category == "hot":
        return random.uniform(0.1, 15)
    else:  # cold
        return random.uniform(1, 50)


def _generate_access_pattern(category):
    if category == "hot":
        access_today = random.uniform(5, 100)
        access_weekly = access_today * 7 * random.uniform(0.7, 1.0)
        access_monthly = access_weekly * 4.3 * random.uniform(0.7, 1.0)
        days_since = random.randint(0, 10)
    else:  # cold
        access_today = random.uniform(0, 0.5)
        access_weekly = random.uniform(0, 2)
        access_monthly = random.uniform(0.1, 5)
        days_since = random.randint(15, 120)
    return access_today, access_weekly, access_monthly, days_since


if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("  Egress Optimizer - Workload Generator")
    print("=" * 50)

    config = load_config()

    print("\n--- Setting up MinIO (Local Server) ---")
    setup_minio(config)

    print("\n--- Generating Cloud Workload (LocalStack S3) ---")
    files = generate_workload(config)

    # Summary
    categories = {}
    for f in files:
        cat = f["category"]
        categories[cat] = categories.get(cat, 0) + 1

    print(f"\n{'='*50}")
    print(f"  SUMMARY")
    print(f"{'='*50}")
    print(f"  Total files:  {len(files)}")
    for cat, count in sorted(categories.items()):
        pct = count / len(files) * 100
        print(f"  {cat:<10}  {count:>3} files ({pct:.0f}%)")
    total_gb = sum(f["size_gb"] for f in files)
    print(f"  Total data:   {total_gb:.1f} GB (metadata), actual upload ~{len(files)}MB")
    print(f"\n  Ready for pipeline!\n")
