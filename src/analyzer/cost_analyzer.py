"""
Layer 2: Cost Analysis Engine
==============================
Calculates egress costs, detects threshold breaches,
and generates cost alerts for the optimization engine.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional

from src.collector.base import CollectionResult, FileAccessRecord


@dataclass
class CostAlert:
    """Represents a cost threshold breach alert."""
    alert_type: str           # 'daily_egress', 'monthly_egress', 'spike', 'large_transfer'
    severity: str             # 'INFO', 'WARNING', 'CRITICAL'
    message: str
    current_value: float
    threshold_value: float
    timestamp: datetime = field(default_factory=datetime.now)
    affected_files: List[str] = field(default_factory=list)


@dataclass
class CostReport:
    """Complete cost analysis report."""
    timestamp: datetime
    total_daily_egress_cost: float
    total_monthly_egress_cost: float
    total_annual_egress_cost: float
    total_storage_cost_monthly: float
    total_monthly_cost: float         # egress + storage
    total_annual_cost: float
    egress_as_percentage: float       # What % of total cost is egress
    top_cost_files: List[Dict]        # Top 10 most expensive files
    cost_by_location: Dict[str, float]
    alerts: List[CostAlert]
    files_analyzed: int
    total_data_gb: float


class CostAnalyzer:
    """
    Layer 2 of the 6-Layer Framework.
    
    Analyzes file access data to:
    1. Calculate per-file and total egress costs
    2. Calculate storage costs by location
    3. Detect cost threshold breaches
    4. Generate alerts for cost spikes
    5. Identify the most expensive files (optimization targets)
    """

    def __init__(self, config: dict):
        self.pricing = config.get("pricing", {})
        self.triggers = config.get("cost_triggers", {})
        self.server_config = config.get("local_server", {})

        # Pricing
        self.egress_per_gb = self.pricing.get("egress_per_gb", 0.09)
        self.s3_per_gb = self.pricing.get("s3_storage_per_gb", 0.023)
        self.glacier_per_gb = self.pricing.get("glacier_storage_per_gb", 0.004)

        # Server costs (amortized)
        investment = self.server_config.get("investment_cost", 25000)
        amort_months = self.server_config.get("amortization_months", 36)
        operating = self.server_config.get("monthly_operating", 150)
        self.monthly_server_cost = (investment / amort_months) + operating

        # Triggers
        self.daily_threshold = self.triggers.get("daily_egress_alert", 100)
        self.monthly_threshold = self.triggers.get("monthly_egress_alert", 3000)
        self.spike_pct = self.triggers.get("spike_percentage", 200)
        self.large_transfer_gb = self.triggers.get("single_transfer_log", 10)

    def analyze(self, collection: CollectionResult) -> CostReport:
        """Run full cost analysis on collected data."""
        alerts = []
        files = collection.files

        # --- Calculate costs ---
        total_daily_egress = 0.0
        total_monthly_egress = 0.0
        total_storage = 0.0
        cost_by_location = {"local": 0.0, "cloud_s3": 0.0, "cloud_glacier": 0.0}

        file_costs = []

        for f in files:
            # Egress cost (only for cloud-stored files that are accessed)
            if f.current_location != "local":
                daily_egress = f.access_count_today * f.file_size_gb * self.egress_per_gb
                monthly_egress = f.access_count_monthly * f.file_size_gb * self.egress_per_gb
            else:
                daily_egress = 0.0
                monthly_egress = 0.0

            # Storage cost
            if f.current_location == "cloud_s3":
                storage_cost = f.file_size_gb * self.s3_per_gb
            elif f.current_location == "cloud_glacier":
                storage_cost = f.file_size_gb * self.glacier_per_gb
            else:  # local
                storage_cost = 0  # Covered by server amortization

            total_daily_egress += daily_egress
            total_monthly_egress += monthly_egress
            total_storage += storage_cost
            cost_by_location[f.current_location] = cost_by_location.get(
                f.current_location, 0
            ) + monthly_egress + storage_cost

            file_costs.append({
                "file_id": f.file_id,
                "file_name": f.file_name,
                "size_gb": f.file_size_gb,
                "location": f.current_location,
                "monthly_egress_cost": round(monthly_egress, 2),
                "monthly_storage_cost": round(storage_cost, 2),
                "total_monthly_cost": round(monthly_egress + storage_cost, 2),
            })

        # Add server amortized cost to local
        local_files = [f for f in files if f.current_location == "local"]
        if local_files:
            cost_by_location["local"] += self.monthly_server_cost

        # --- Top cost files ---
        file_costs.sort(key=lambda x: x["total_monthly_cost"], reverse=True)
        top_cost_files = file_costs[:10]

        # --- Totals ---
        total_monthly = total_monthly_egress + total_storage
        if local_files:
            total_monthly += self.monthly_server_cost
        total_annual = total_monthly * 12
        egress_pct = (total_monthly_egress / total_monthly * 100) if total_monthly > 0 else 0

        # --- Check alerts ---
        if total_daily_egress > self.daily_threshold:
            alerts.append(CostAlert(
                alert_type="daily_egress",
                severity="WARNING",
                message=f"Daily egress cost ${total_daily_egress:.2f} exceeds threshold ${self.daily_threshold}",
                current_value=total_daily_egress,
                threshold_value=self.daily_threshold,
            ))

        if total_monthly_egress > self.monthly_threshold:
            alerts.append(CostAlert(
                alert_type="monthly_egress",
                severity="CRITICAL",
                message=f"Monthly egress cost ${total_monthly_egress:.2f} exceeds threshold ${self.monthly_threshold}",
                current_value=total_monthly_egress,
                threshold_value=self.monthly_threshold,
            ))

        # Check for large individual file transfers
        for f in files:
            if f.total_egress_volume_gb > self.large_transfer_gb:
                alerts.append(CostAlert(
                    alert_type="large_transfer",
                    severity="INFO",
                    message=f"Large transfer detected: {f.file_name} ({f.total_egress_volume_gb:.1f} GB/month)",
                    current_value=f.total_egress_volume_gb,
                    threshold_value=self.large_transfer_gb,
                    affected_files=[f.file_id],
                ))

        return CostReport(
            timestamp=datetime.now(),
            total_daily_egress_cost=round(total_daily_egress, 2),
            total_monthly_egress_cost=round(total_monthly_egress, 2),
            total_annual_egress_cost=round(total_monthly_egress * 12, 2),
            total_storage_cost_monthly=round(total_storage, 2),
            total_monthly_cost=round(total_monthly, 2),
            total_annual_cost=round(total_annual, 2),
            egress_as_percentage=round(egress_pct, 1),
            top_cost_files=top_cost_files,
            cost_by_location={k: round(v, 2) for k, v in cost_by_location.items()},
            alerts=alerts,
            files_analyzed=len(files),
            total_data_gb=round(collection.total_size_gb, 2),
        )
