"""
Unit Tests - Classifier Module
================================
Tests for both rule-based and ML-based classification.
"""

import pytest
import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.collector.base import FileAccessRecord
from src.classifier.hot_cold_classifier import HotColdClassifier, DataTier
from src.classifier.ml_classifier import MLClassifier


@pytest.fixture
def config():
    return {
        "classification": {
            "hot": {"min_access_per_day": 1, "max_days_since_access": 30},
        },
    }


def make_file(access_today, days_since, size_gb=5.0, location="cloud_s3"):
    """Helper to create a test FileAccessRecord."""
    now = datetime.now()
    return FileAccessRecord(
        file_id="test-001",
        file_name="test_file.csv",
        file_size_gb=size_gb,
        current_location=location,
        access_count_today=access_today,
        access_count_weekly=access_today * 5,
        access_count_monthly=access_today * 20,
        last_access_date=now - timedelta(days=days_since),
        days_since_last_access=days_since,
        created_date=now - timedelta(days=100),
        egress_cost_daily=access_today * size_gb * 0.09,
        egress_cost_monthly=access_today * 20 * size_gb * 0.09,
        total_egress_volume_gb=access_today * 20 * size_gb,
        last_migration_date=None,
        tags={},
    )


class TestRuleBasedClassifier:
    """Tests for the rule-based HotColdClassifier."""

    def test_hot_classification(self, config):
        """High access + recent = HOT."""
        classifier = HotColdClassifier(config)
        files = [make_file(access_today=50, days_since=1)]
        report = classifier.classify(files)
        assert report.results[0].tier == DataTier.HOT

    def test_cold_classification(self, config):
        """Low access + old = COLD."""
        classifier = HotColdClassifier(config)
        files = [make_file(access_today=0.01, days_since=45)]
        report = classifier.classify(files)
        assert report.results[0].tier == DataTier.COLD

    def test_hot_recommends_local(self, config):
        """HOT files should be stored locally."""
        classifier = HotColdClassifier(config)
        files = [make_file(access_today=50, days_since=1)]
        report = classifier.classify(files)
        assert report.results[0].recommended_location == "local"

    def test_migration_detected(self, config):
        """HOT file in cloud should need migration to local."""
        classifier = HotColdClassifier(config)
        files = [make_file(access_today=50, days_since=1, location="cloud_s3")]
        report = classifier.classify(files)
        assert report.results[0].needs_migration is True
        assert report.results[0].migration_direction == "to_local"

    def test_no_migration_if_correct(self, config):
        """File already in correct location should not migrate."""
        classifier = HotColdClassifier(config)
        files = [make_file(access_today=50, days_since=1, location="local")]
        report = classifier.classify(files)
        assert report.results[0].needs_migration is False

    def test_summary_counts(self, config):
        """Summary should have counts for all tiers."""
        classifier = HotColdClassifier(config)
        files = [
            make_file(access_today=50, days_since=1),
            make_file(access_today=0.001, days_since=100),
        ]
        report = classifier.classify(files)
        assert report.total_files == 2
        assert sum(report.summary.values()) == 2


class TestMLClassifier:
    """Tests for the ML-based classifier."""

    def test_ml_loads_or_falls_back(self, config):
        """ML classifier should either load model or use fallback."""
        classifier = MLClassifier(config)
        assert classifier.get_method_name() is not None

    def test_ml_classifies_files(self, config):
        """Should classify files regardless of mode."""
        classifier = MLClassifier(config)
        files = [
            make_file(access_today=50, days_since=1),
            make_file(access_today=0.001, days_since=100),
        ]
        report = classifier.classify(files)
        assert report.total_files == 2
        assert len(report.results) == 2

    def test_ml_confidence_range(self, config):
        """Confidence should be between 0 and 1."""
        classifier = MLClassifier(config)
        files = [make_file(access_today=50, days_since=1)]
        report = classifier.classify(files)
        assert 0.0 <= report.results[0].confidence <= 1.0
