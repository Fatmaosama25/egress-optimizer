"""
Unit Tests - Cost Analyzer Module
====================================
Tests for cost calculation and alert detection.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.collector.simulated_collector import SimulatedCollector
from src.analyzer.cost_analyzer import CostAnalyzer


@pytest.fixture
def config():
    return {
        "simulation": {"num_files": 30, "seed": 42},
        "classification": {
            "hot": {"min_access_per_day": 1, "max_days_since_access": 30},
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
def cost_report(config):
    collection = SimulatedCollector(config).collect()
    analyzer = CostAnalyzer(config)
    return analyzer.analyze(collection)


class TestCostAnalyzer:
    """Tests for the CostAnalyzer class."""

    def test_report_has_total_cost(self, cost_report):
        """Report should calculate total monthly cost."""
        assert cost_report.total_monthly_cost > 0

    def test_egress_dominates_cost(self, cost_report):
        """Egress should be the major cost component (thesis claim)."""
        assert cost_report.egress_as_percentage > 50

    def test_annual_cost_is_12x_monthly(self, cost_report):
        """Annual cost should be 12x monthly."""
        expected = cost_report.total_monthly_cost * 12
        assert abs(cost_report.total_annual_cost - expected) < 1.0

    def test_top_cost_files_sorted(self, cost_report):
        """Top files should be sorted by cost (descending)."""
        costs = [f["total_monthly_cost"] for f in cost_report.top_cost_files]
        for i in range(len(costs) - 1):
            assert costs[i] >= costs[i + 1]

    def test_alerts_generated(self, cost_report):
        """Should generate at least one alert."""
        assert len(cost_report.alerts) > 0

    def test_storage_cost_non_negative(self, cost_report):
        """Storage costs should be non-negative."""
        assert cost_report.total_storage_cost_monthly >= 0

    def test_cost_by_location_exists(self, cost_report):
        """Should break down cost by storage location."""
        assert isinstance(cost_report.cost_by_location, dict)
        assert len(cost_report.cost_by_location) > 0
