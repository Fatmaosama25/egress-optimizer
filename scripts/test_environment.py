"""
Environment Verification Script
================================
Tests that LocalStack (S3) and MinIO are working correctly.
Run this after 'docker-compose up -d' to verify your setup.
"""

import boto3
import json
from botocore.config import Config

# Simple ASCII output (Windows compatible)
CHECK = "[OK]"
CROSS = "[FAIL]"


def test_localstack_s3():
    """Test LocalStack S3 — simulates AWS Cloud."""
    print(f"\n{'='*50}")
    print(f"  Testing LocalStack (AWS S3 Simulator)")
    print(f"  Endpoint: http://localhost:4566")
    print(f"{'='*50}")

    try:
        # Connect to LocalStack S3
        s3 = boto3.client(
            "s3",
            endpoint_url="http://localhost:4566",
            aws_access_key_id="test",
            aws_secret_access_key="test",
            region_name="us-east-1",
        )

        # 1. Create a bucket
        bucket_name = "egress-test-bucket"
        s3.create_bucket(Bucket=bucket_name)
        print(f"  {CHECK} Created bucket: {bucket_name}")

        # 2. Upload a test file
        test_data = json.dumps({"message": "Hello from LocalStack!", "status": "working"})
        s3.put_object(Bucket=bucket_name, Key="test-file.json", Body=test_data)
        print(f"  {CHECK} Uploaded test file: test-file.json")

        # 3. Download and verify
        response = s3.get_object(Bucket=bucket_name, Key="test-file.json")
        content = response["Body"].read().decode("utf-8")
        data = json.loads(content)
        assert data["status"] == "working"
        print(f"  {CHECK} Downloaded and verified: {data['message']}")

        # 4. List objects
        objects = s3.list_objects_v2(Bucket=bucket_name)
        count = objects.get("KeyCount", 0)
        print(f"  {CHECK} Listed objects: {count} file(s) in bucket")

        # 5. Cleanup
        s3.delete_object(Bucket=bucket_name, Key="test-file.json")
        s3.delete_bucket(Bucket=bucket_name)
        print(f"  {CHECK} Cleaned up test bucket")

        print(f"\n  LocalStack S3 is working perfectly!")
        return True

    except Exception as e:
        print(f"  {CROSS} LocalStack S3 FAILED: {e}")
        return False


def test_minio():
    """Test MinIO — simulates on-premise local server."""
    print(f"\n{'='*50}")
    print(f"  Testing MinIO (Local Server Simulator)")
    print(f"  Endpoint: http://localhost:9000")
    print(f"{'='*50}")

    try:
        # Connect to MinIO (S3-compatible)
        s3 = boto3.client(
            "s3",
            endpoint_url="http://localhost:9000",
            aws_access_key_id="minioadmin",
            aws_secret_access_key="minioadmin123",
            region_name="us-east-1",
            config=Config(signature_version="s3v4"),
        )

        # 1. Create a bucket
        bucket_name = "local-test-bucket"
        s3.create_bucket(Bucket=bucket_name)
        print(f"  {CHECK} Created bucket: {bucket_name}")

        # 2. Upload a test file
        test_data = json.dumps({"message": "Hello from MinIO!", "location": "local_server"})
        s3.put_object(Bucket=bucket_name, Key="local-test.json", Body=test_data)
        print(f"  {CHECK} Uploaded test file: local-test.json")

        # 3. Download and verify
        response = s3.get_object(Bucket=bucket_name, Key="local-test.json")
        content = response["Body"].read().decode("utf-8")
        data = json.loads(content)
        assert data["location"] == "local_server"
        print(f"  {CHECK} Downloaded and verified: {data['message']}")

        # 4. Cleanup
        s3.delete_object(Bucket=bucket_name, Key="local-test.json")
        s3.delete_bucket(Bucket=bucket_name)
        print(f"  {CHECK} Cleaned up test bucket")

        print(f"\n  MinIO is working perfectly!")
        return True

    except Exception as e:
        print(f"  {CROSS} MinIO FAILED: {e}")
        return False


if __name__ == "__main__":
    print(f"\n{'#'*50}")
    print(f"  Egress Optimizer — Environment Test")
    print(f"{'#'*50}")

    ls_ok = test_localstack_s3()
    minio_ok = test_minio()

    print(f"\n{'='*50}")
    print(f"  RESULTS")
    print(f"{'='*50}")
    print(f"  LocalStack S3:  {'PASS ' + CHECK if ls_ok else 'FAIL ' + CROSS}")
    print(f"  MinIO:          {'PASS ' + CHECK if minio_ok else 'FAIL ' + CROSS}")

    if ls_ok and minio_ok:
        print(f"\n  All systems ready! You can start building.")
    else:
        print(f"\n  Some tests failed. Check Docker containers.")
        print(f"  Run: docker ps")

    print()
