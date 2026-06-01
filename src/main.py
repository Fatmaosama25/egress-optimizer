"""
DevOps Automation for Cloud Egress Cost Optimization
=====================================================
Main Orchestrator - Runs the full 6-layer optimization pipeline.

Pipeline:
  Layer 1: Collect data (simulated or AWS)
  Layer 2: Analyze costs & detect threshold breaches
  Layer 3: Classify files (Hot/Warm/Cold/Archive)
  Layer 3b: Optimize migration decisions
  Layer 4: Generate Terraform configurations
  Layer 6: Track savings & export dashboard data
"""

import os
import sys
import yaml
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.collector.simulated_collector import SimulatedCollector
from src.collector.aws_collector import AWSCollector
from src.analyzer.cost_analyzer import CostAnalyzer
from src.classifier.hot_cold_classifier import HotColdClassifier
from src.optimizer.migration_optimizer import MigrationOptimizer
from src.iac_generator.terraform_generator import TerraformGenerator
from src.monitor.savings_tracker import SavingsTracker


def load_config(config_path: str = None) -> dict:
    """Load configuration from YAML file."""
    if config_path is None:
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config", "config.yaml"
        )
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def print_header(text: str):
    """Print a formatted section header."""
    width = 60
    print(f"\n{'=' * width}")
    print(f"  {text}")
    print(f"{'=' * width}")


def print_metric(label: str, value: str, indent: int = 2):
    """Print a formatted metric."""
    print(f"{' ' * indent}{label:<35} {value}")


def run_pipeline():
    """Execute the full optimization pipeline."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Load config
    config = load_config()

    # Determine pipeline mode
    mode = config.get("mode", "simulated")

    print_header("DevOps Automation for Cloud Egress Cost Optimization")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Mode: {mode.upper()}")

    # ===== LAYER 1: DATA COLLECTION =====
    print_header("Layer 1: Data Collection")
    if mode == "localstack":
        collector = AWSCollector(config)
    else:
        collector = SimulatedCollector(config)
    collection = collector.collect()
    print_metric("Source:", collector.get_source_name())
    print_metric("Files collected:", str(collection.total_files))
    print_metric("Total data:", f"{collection.total_size_tb:.2f} TB ({collection.total_size_gb:.0f} GB)")
    print_metric("Daily egress cost:", f"${collection.total_egress_cost_daily:.2f}")
    print_metric("Monthly egress cost:", f"${collection.total_egress_cost_monthly:.2f}")

    # ===== LAYER 2: COST ANALYSIS =====
    print_header("Layer 2: Cost Analysis")
    analyzer = CostAnalyzer(config)
    cost_report = analyzer.analyze(collection)
    print_metric("Total monthly cost:", f"${cost_report.total_monthly_cost:.2f}")
    print_metric("  - Egress fees:", f"${cost_report.total_monthly_egress_cost:.2f}")
    print_metric("  - Storage fees:", f"${cost_report.total_storage_cost_monthly:.2f}")
    print_metric("Annual cost:", f"${cost_report.total_annual_cost:.2f}")
    print_metric("Egress as % of total:", f"{cost_report.egress_as_percentage:.1f}%")

    if cost_report.alerts:
        print(f"\n  ALERTS ({len(cost_report.alerts)}):")
        for alert in cost_report.alerts[:5]:
            icon = "!!" if alert.severity == "CRITICAL" else "!" if alert.severity == "WARNING" else "i"
            print(f"    [{icon}] {alert.message}")

    print("\n  Top 5 Most Expensive Files:")
    for i, f in enumerate(cost_report.top_cost_files[:5], 1):
        print(f"    {i}. {f['file_name']:<35} ${f['total_monthly_cost']:.2f}/mo "
              f"({f['size_gb']:.1f}GB, {f['location']})")

    # ===== LAYER 3: CLASSIFICATION =====
    print_header("Layer 3: Hot/Cold Classification")
    classifier = HotColdClassifier(config)
    classification = classifier.classify(collection.files)

    print("  Classification Summary:")
    for tier, count in classification.summary.items():
        size = classification.size_by_tier[tier]
        pct = (count / classification.total_files * 100)
        bar = "#" * int(pct / 2)
        print(f"    {tier:<10} {count:>3} files ({size:>8.1f} GB) [{bar}] {pct:.0f}%")

    print_metric("\nFiles needing migration:", str(classification.total_needing_migration))

    # ===== LAYER 3b: OPTIMIZATION =====
    print_header("Layer 3b: Migration Optimization")
    optimizer = MigrationOptimizer(config)
    optimization = optimizer.optimize(
        files=collection.files,
        classifications=classification.results,
        current_monthly_cost=cost_report.total_monthly_cost,
    )

    print_metric("Approved migrations:", str(len(optimization.approved_migrations)))
    print_metric("Rejected migrations:", str(len(optimization.rejected_migrations)))
    print_metric("Data to move:", f"{optimization.total_data_to_move_gb:.1f} GB")
    print_metric("One-time migration cost:", f"${optimization.total_migration_cost:.2f}")
    print()
    print_metric("BEFORE (monthly):", f"${optimization.before_monthly_cost:.2f}")
    print_metric("AFTER  (monthly):", f"${optimization.after_monthly_cost:.2f}")
    print_metric("MONTHLY SAVINGS:", f"${optimization.total_monthly_savings:.2f}")
    print_metric("ANNUAL SAVINGS:", f"${optimization.total_annual_savings:.2f}")
    print_metric("COST REDUCTION:", f"{optimization.cost_reduction_percentage:.1f}%")
    print_metric("PAYBACK PERIOD:", f"{optimization.estimated_payback_months:.1f} months")

    # ===== LAYER 4: TERRAFORM GENERATION =====
    print_header("Layer 4: Terraform Generation")
    tf_dir = os.path.join(project_root, "terraform")
    tf_gen = TerraformGenerator(config, output_dir=tf_dir)
    tf_files = tf_gen.generate(optimization)
    print(f"  Generated {len(tf_files)} Terraform files:")
    for fname in tf_files:
        fpath = os.path.join(tf_dir, fname)
        size = os.path.getsize(fpath)
        print(f"    - {fname} ({size} bytes)")

    # ===== LAYER 6: SAVINGS TRACKING =====
    print_header("Layer 6: Savings Tracking & Dashboard Export")
    data_dir = os.path.join(project_root, "data")
    tracker = SavingsTracker(config, data_dir=data_dir)
    snapshot = tracker.record(cost_report, optimization, classification)
    dashboard_path = tracker.export_dashboard_data(cost_report, classification, optimization)
    print_metric("Dashboard data exported to:", os.path.basename(dashboard_path))

    # ROI Summary
    server_cost = config.get("local_server", {}).get("investment_cost", 25000)
    monthly_sav = optimization.total_monthly_savings
    payback = server_cost / monthly_sav if monthly_sav > 0 else float('inf')
    three_year = (monthly_sav * 36) - server_cost

    print_header("ROI SUMMARY")
    print_metric("Server Investment:", f"${server_cost:,.0f}")
    print_metric("Monthly Savings:", f"${monthly_sav:,.2f}")
    print_metric("Payback Period:", f"{payback:.1f} months")
    print_metric("3-Year Net Savings:", f"${three_year:,.2f}")

    print(f"\n{'=' * 60}")
    print(f"  Pipeline completed successfully!")
    print(f"  Open dashboard/index.html to view interactive results.")
    print(f"  Terraform configs ready in terraform/")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    run_pipeline()
