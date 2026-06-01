"""
Integration Test - Full Pipeline
==================================
Tests the entire 5-layer pipeline end-to-end in simulated mode.
"""

import pytest
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.collector.simulated_collector import SimulatedCollector
from src.analyzer.cost_analyzer import CostAnalyzer
from src.classifier.hot_cold_classifier import HotColdClassifier
from src.classifier.ml_classifier import MLClassifier
from src.optimizer.migration_optimizer import MigrationOptimizer
from src.iac_generator.terraform_generator import TerraformGenerator
from src.monitor.savings_tracker import SavingsTracker


@pytest.fixture
def config():
    return {
        "simulation": {"num_files": 40, "seed": 42},
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
        "roi": {"server_investment": 25000},
    }


class TestFullPipeline:
    """Integration test: all 5 layers in sequence."""

    def test_full_pipeline_simulated(self, config):
        """Run the complete pipeline and verify all outputs."""

        # Layer 1: Collect
        collector = SimulatedCollector(config)
        collection = collector.collect()
        assert collection.total_files == 40
        assert collection.total_size_gb > 0

        # Layer 2: Analyze
        analyzer = CostAnalyzer(config)
        cost_report = analyzer.analyze(collection)
        assert cost_report.total_monthly_cost > 0
        assert cost_report.egress_as_percentage > 50

        # Layer 3: Classify
        classifier = HotColdClassifier(config)
        classification = classifier.classify(collection.files)
        assert classification.total_files == 40
        assert sum(classification.summary.values()) == 40
        tiers = set(classification.summary.keys())
        assert "HOT" in tiers
        assert "COLD" in tiers

        # Layer 3b: Optimize
        optimizer = MigrationOptimizer(config)
        opt_report = optimizer.optimize(
            files=collection.files,
            classifications=classification.results,
            current_monthly_cost=cost_report.total_monthly_cost,
        )
        assert opt_report.cost_reduction_percentage > 0
        assert opt_report.after_monthly_cost < opt_report.before_monthly_cost

        # Layer 4: Generate Terraform
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        tf_dir = os.path.join(project_root, "terraform")
        generator = TerraformGenerator(config, tf_dir)
        generator.generate(opt_report)
        assert os.path.exists(os.path.join(tf_dir, "main.tf"))
        assert os.path.exists(os.path.join(tf_dir, "migration_plan.json"))

        # Layer 5: Track savings
        tracker = SavingsTracker(config, os.path.join(project_root, "data"))
        tracker.record(cost_report, opt_report, classification)
        dashboard_path = tracker.export_dashboard_data(
            cost_report, classification, opt_report
        )
        assert os.path.exists(dashboard_path)

        # Verify dashboard JSON is valid
        with open(dashboard_path) as f:
            dashboard = json.load(f)
        assert "cost_summary" in dashboard
        assert "classification" in dashboard
        assert "roi" in dashboard

    def test_thesis_claims(self, config):
        """Verify the key thesis claims hold true."""

        # Run pipeline
        collection = SimulatedCollector(config).collect()
        cost_report = CostAnalyzer(config).analyze(collection)
        classification = HotColdClassifier(config).classify(collection.files)
        opt_report = MigrationOptimizer(config).optimize(
            files=collection.files,
            classifications=classification.results,
            current_monthly_cost=cost_report.total_monthly_cost,
        )

        # Thesis Claim 1: 40-60% cost reduction
        assert opt_report.cost_reduction_percentage >= 30, \
            f"Cost reduction {opt_report.cost_reduction_percentage:.1f}% below 30%"

        # Thesis Claim 2: Payback < 6 months
        investment = config["roi"]["server_investment"]
        if opt_report.total_monthly_savings > 0:
            payback = investment / opt_report.total_monthly_savings
            assert payback < 12, f"Payback {payback:.1f} months exceeds 12"

        # Thesis Claim 3: Egress is majority of cost
        assert cost_report.egress_as_percentage > 50, \
            f"Egress only {cost_report.egress_as_percentage:.1f}% of total"
