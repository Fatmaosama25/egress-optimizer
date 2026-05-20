"""
Layer 6: Savings Tracker & Monitoring
======================================
Tracks cost savings over time, ROI progress,
and generates data for the dashboard.
"""

import json
import os
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional

from src.analyzer.cost_analyzer import CostReport
from src.optimizer.migration_optimizer import OptimizationReport
from src.classifier.hot_cold_classifier import ClassificationReport


@dataclass
class SavingsSnapshot:
    """A point-in-time savings record."""
    timestamp: str
    before_monthly: float
    after_monthly: float
    monthly_savings: float
    annual_savings: float
    cumulative_savings: float
    roi_percentage: float
    payback_remaining_months: float
    files_optimized: int
    data_optimized_gb: float


class SavingsTracker:
    """
    Layer 6 of the 6-Layer Framework.
    Tracks savings over time and produces dashboard-ready data.
    """

    def __init__(self, config: dict, data_dir: str = "data"):
        self.config = config
        self.data_dir = data_dir
        self.server_investment = config.get("local_server", {}).get("investment_cost", 25000)
        self.history: List[SavingsSnapshot] = []
        os.makedirs(data_dir, exist_ok=True)

    def record(
        self,
        cost_report: CostReport,
        optimization: OptimizationReport,
        classification: ClassificationReport,
    ) -> SavingsSnapshot:
        """Record a new savings snapshot."""
        cumulative = sum(s.monthly_savings for s in self.history)
        cumulative += optimization.total_monthly_savings

        roi = ((cumulative - self.server_investment) / self.server_investment * 100
               if self.server_investment > 0 else 0)

        remaining_to_payback = max(0, self.server_investment - cumulative)
        months_remaining = (remaining_to_payback / optimization.total_monthly_savings
                           if optimization.total_monthly_savings > 0 else float('inf'))

        snapshot = SavingsSnapshot(
            timestamp=datetime.now().isoformat(),
            before_monthly=optimization.before_monthly_cost,
            after_monthly=optimization.after_monthly_cost,
            monthly_savings=optimization.total_monthly_savings,
            annual_savings=optimization.total_annual_savings,
            cumulative_savings=round(cumulative, 2),
            roi_percentage=round(roi, 1),
            payback_remaining_months=round(months_remaining, 1),
            files_optimized=len(optimization.approved_migrations),
            data_optimized_gb=optimization.total_data_to_move_gb,
        )

        self.history.append(snapshot)
        return snapshot

    def export_dashboard_data(
        self,
        cost_report: CostReport,
        classification: ClassificationReport,
        optimization: OptimizationReport,
    ) -> str:
        """Export all data as JSON for the web dashboard."""
        dashboard_data = {
            "generated_at": datetime.now().isoformat(),
            "cost_summary": {
                "before_monthly": optimization.before_monthly_cost,
                "after_monthly": optimization.after_monthly_cost,
                "monthly_savings": optimization.total_monthly_savings,
                "annual_savings": optimization.total_annual_savings,
                "reduction_pct": optimization.cost_reduction_percentage,
                "egress_pct_of_total": cost_report.egress_as_percentage,
                "total_data_tb": round(cost_report.total_data_gb / 1000, 2),
            },
            "classification": {
                "summary": classification.summary,
                "size_by_tier": classification.size_by_tier,
                "total_files": classification.total_files,
                "needing_migration": classification.total_needing_migration,
            },
            "migration": {
                "approved_count": len(optimization.approved_migrations),
                "rejected_count": len(optimization.rejected_migrations),
                "total_cost": optimization.total_migration_cost,
                "data_to_move_gb": optimization.total_data_to_move_gb,
                "payback_months": optimization.estimated_payback_months,
            },
            "roi": {
                "server_investment": self.server_investment,
                "monthly_savings": optimization.total_monthly_savings,
                "payback_months": (self.server_investment / optimization.total_monthly_savings
                                  if optimization.total_monthly_savings > 0 else 0),
                "three_year_savings": optimization.total_monthly_savings * 36 - self.server_investment,
            },
            "top_cost_files": cost_report.top_cost_files,
            "alerts": [
                {
                    "type": a.alert_type,
                    "severity": a.severity,
                    "message": a.message,
                    "value": a.current_value,
                    "threshold": a.threshold_value,
                }
                for a in cost_report.alerts
            ],
            "cost_by_location": cost_report.cost_by_location,
            "savings_history": [asdict(s) for s in self.history],
            "migrations_detail": [
                {
                    "file": m.file_name,
                    "size_gb": m.file_size_gb,
                    "from": m.source_location,
                    "to": m.target_location,
                    "tier": m.tier.value,
                    "savings": m.monthly_savings,
                    "payback": m.payback_months,
                }
                for m in optimization.approved_migrations[:20]
            ],
        }

        filepath = os.path.join(self.data_dir, "dashboard_data.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(dashboard_data, f, indent=2)

        return filepath
