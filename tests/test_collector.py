"""
Unit Tests - Data Collector Module
====================================
Tests for SimulatedCollector and base data models.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.collector.base import FileAccessRecord, CollectionResult
from src.collector.simulated_collector import SimulatedCollector


@pytest.fixture
def config():
    """Standard test configuration."""
    return {
        "simulation": {"num_files": 20, "seed": 42},
        "classification": {
            "hot": {"min_access_per_day": 1, "max_days_since_access": 30},
        },
        "pricing": {
            "egress_per_gb": 0.09,
            "storage_s3_per_gb": 0.023,
            "storage_glacier_per_gb": 0.004,
            "local_server_monthly": 500,
        },
        "migration": {
            "transfer_cost_per_gb": 0.09,
            "min_monthly_savings": 5,
            "max_payback_months": 6,
            "batch_size": 50,
        },
    }


@pytest.fixture
def collection(config):
    """Run simulated collection."""
    collector = SimulatedCollector(config)
    return collector.collect()


class TestSimulatedCollector:
    """Tests for the SimulatedCollector class."""

    def test_collector_returns_result(self, config):
        """Collector should return a CollectionResult."""
        collector = SimulatedCollector(config)
        result = collector.collect()
        assert isinstance(result, CollectionResult)

    def test_correct_file_count(self, collection):
        """Should generate exactly the configured number of files."""
        assert collection.total_files == 20

    def test_files_have_required_fields(self, collection):
        """Each file should have all required fields."""
        for f in collection.files:
            assert f.file_id is not None
            assert f.file_name is not None
            assert f.file_size_gb > 0
            assert f.current_location in ["cloud_s3", "local", "cloud_glacier"]

    def test_positive_file_sizes(self, collection):
        """All file sizes should be positive."""
        for f in collection.files:
            assert f.file_size_gb > 0

    def test_total_size_calculated(self, collection):
        """Total size should be sum of all file sizes."""
        expected_gb = sum(f.file_size_gb for f in collection.files)
        assert abs(collection.total_size_gb - expected_gb) < 0.1

    def test_egress_costs_non_negative(self, collection):
        """Egress costs should never be negative."""
        assert collection.total_egress_cost_daily >= 0
        assert collection.total_egress_cost_monthly >= 0

    def test_deterministic_with_seed(self, config):
        """Same seed should produce identical results."""
        c1 = SimulatedCollector(config).collect()
        c2 = SimulatedCollector(config).collect()
        assert c1.total_files == c2.total_files
        assert abs(c1.total_size_gb - c2.total_size_gb) < 0.01

    def test_source_name(self, config):
        """Should return a descriptive source name."""
        collector = SimulatedCollector(config)
        name = collector.get_source_name()
        assert "Simulated" in name or "simulated" in name
