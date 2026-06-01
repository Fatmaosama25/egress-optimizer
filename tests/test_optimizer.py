"""
Unit Tests - Migration Optimizer Module
=========================================
Tests for cost-benefit analysis and migration decisions.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.collector.simulated_collector import SimulatedCollector
from src.analyzer.cost_analyzer import CostAnalyzer
from src.classifier.hot_cold_classifier import HotColdClassifier
from src.optimizer.migration_optimizer import MigrationOptimizer


@pytest.fixture
def config():
    return {
        "simulation": {"num_files": 30, "seed": 42},
        "classification": {
            "hot": {"min_access_per_day": 10, "max_days_since_access": 7},
            "warm": {"min_access_per_day": 1, "max_days_since_access": 30},
            "cold": {"max_access_per_week": 1, "min_days_since_access": 30},
            "archive": {"max_access_per_month": 1, "min_days_since_access": 90},
        },
        "pricing": {
            "egress_per_gb": 0.09,
            "storage_s3_per_gb": 0.023,
            "storage_glacier_per_gb": 0.004,
            "local_server_monthly": 500,
        },
        "cost_thresholds": {
            "daily_egress_alert": 100,
            "monthly_egress_alert": 3000,
            "single_file_daily_gb": 10,
        },
        "migration": {
            "transfer_cost_per_gb": 0.09,
            "min_monthly_savings": 5,
            "max_payback_months": 6,
            "batch_size": 50,
        },
    }


@pytest.fixture
def optimization_report(config):
    collection = SimulatedCollector(config).collect()
    analyzer = CostAnalyzer(config)
    cost_report = analyzer.analyze(collection)
    classifier = HotColdClassifier(config)
    classification = classifier.classify(collection.files)
    optimizer = MigrationOptimizer(config)
    return optimizer.optimize(
        files=collection.files,
        classifications=classification.results,
        current_monthly_cost=cost_report.total_monthly_cost,
    )


class TestMigrationOptimizer:
    """Tests for the MigrationOptimizer class."""

    def test_report_generated(self, optimization_report):
        """Should produce an optimization report."""
        assert optimization_report is not None

    def test_cost_reduction_positive(self, optimization_report):
        """Should achieve positive cost reduction."""
        assert optimization_report.cost_reduction_percentage > 0

    def test_after_cost_lower(self, optimization_report):
        """After-optimization cost should be lower."""
        assert optimization_report.after_monthly_cost < optimization_report.before_monthly_cost

    def test_savings_match_difference(self, optimization_report):
        """Savings = before - after."""
        expected = (optimization_report.before_monthly_cost -
                    optimization_report.after_monthly_cost)
        assert abs(optimization_report.total_monthly_savings - expected) < 0.01

    def test_approved_have_positive_savings(self, optimization_report):
        """Every approved migration should have positive savings."""
        for m in optimization_report.approved_migrations:
            assert m.monthly_savings > 0

    def test_payback_within_threshold(self, optimization_report):
        """Approved migrations should pay back within configured limit."""
        for m in optimization_report.approved_migrations:
            assert m.payback_months <= 6.0

    def test_migration_cost_non_negative(self, optimization_report):
        """Total migration cost should be non-negative."""
        assert optimization_report.total_migration_cost >= 0

    def test_annual_savings_is_12x(self, optimization_report):
        """Annual savings should be 12x monthly."""
        expected = optimization_report.total_monthly_savings * 12
        assert abs(optimization_report.total_annual_savings - expected) < 1.0
