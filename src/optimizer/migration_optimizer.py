"""
Layer 3b: Migration Optimizer
==============================
Decides which files to actually migrate based on:
1. Cost-benefit analysis (payback period)
2. Anti-thrashing cooldown rules
3. Batch size constraints
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from src.collector.base import FileAccessRecord
from src.classifier.hot_cold_classifier import ClassificationResult, DataTier


@dataclass
class MigrationPlan:
    """A plan for migrating a single file."""
    file_id: str
    file_name: str
    file_size_gb: float
    source_location: str
    target_location: str
    tier: DataTier
    migration_cost: float           # One-time cost to migrate ($)
    monthly_savings: float          # Expected monthly savings ($)
    payback_months: float           # Months to break even
    approved: bool                  # Passes cost-benefit check
    rejection_reason: Optional[str] = None
    priority_score: float = 0.0     # Higher = migrate first


@dataclass
class OptimizationReport:
    """Complete optimization plan."""
    timestamp: datetime
    approved_migrations: List[MigrationPlan]
    rejected_migrations: List[MigrationPlan]
    total_migration_cost: float
    total_monthly_savings: float
    total_annual_savings: float
    estimated_payback_months: float
    total_data_to_move_gb: float
    before_monthly_cost: float
    after_monthly_cost: float
    cost_reduction_percentage: float


class MigrationOptimizer:
    """
    Layer 3b of the 6-Layer Framework.
    
    Migration Decision Formula (from thesis):
        Migrate IF migration_cost < (monthly_savings × payback_months)
    
    Anti-Thrashing Rule:
        Data must stay in current location for minimum 14 days
        before being eligible for another move.
    """

    def __init__(self, config: dict):
        mig_config = config.get("migration", {})
        self.pricing = config.get("pricing", {})
        self.server_config = config.get("local_server", {})

        # Migration rules
        self.max_payback_months = mig_config.get("payback_months", 6)
        self.cooldown_days = mig_config.get("cooldown_days", 14)
        self.batch_size_gb = mig_config.get("batch_size_gb", 500)
        self.min_savings = mig_config.get("min_savings_threshold", 10)

        # Pricing
        self.egress_per_gb = self.pricing.get("egress_per_gb", 0.09)
        self.s3_per_gb = self.pricing.get("s3_storage_per_gb", 0.023)
        self.glacier_per_gb = self.pricing.get("glacier_storage_per_gb", 0.004)

        # Server costs
        investment = self.server_config.get("investment_cost", 25000)
        amort_months = self.server_config.get("amortization_months", 36)
        operating = self.server_config.get("monthly_operating", 150)
        self.monthly_server_cost = (investment / amort_months) + operating

    def optimize(
        self,
        files: List[FileAccessRecord],
        classifications: List[ClassificationResult],
        current_monthly_cost: float,
    ) -> OptimizationReport:
        """
        Evaluate each migration candidate and create an optimization plan.
        """
        approved = []
        rejected = []

        # Build lookup
        file_map = {f.file_id: f for f in files}

        # Only process files that need migration
        candidates = [c for c in classifications if c.needs_migration]

        for cls_result in candidates:
            file_record = file_map.get(cls_result.file_id)
            if not file_record:
                continue

            plan = self._evaluate_migration(file_record, cls_result)

            if plan.approved:
                approved.append(plan)
            else:
                rejected.append(plan)

        # Sort approved by priority (highest savings first)
        approved.sort(key=lambda p: p.priority_score, reverse=True)

        # Enforce batch size limit
        cumulative_gb = 0
        final_approved = []
        for plan in approved:
            if cumulative_gb + plan.file_size_gb <= self.batch_size_gb:
                final_approved.append(plan)
                cumulative_gb += plan.file_size_gb
            else:
                plan.approved = False
                plan.rejection_reason = f"Exceeds batch limit ({self.batch_size_gb}GB)"
                rejected.append(plan)

        # Calculate totals
        total_mig_cost = sum(p.migration_cost for p in final_approved)
        total_monthly_sav = sum(p.monthly_savings for p in final_approved)
        total_annual_sav = total_monthly_sav * 12
        total_data_gb = sum(p.file_size_gb for p in final_approved)

        after_cost = current_monthly_cost - total_monthly_sav
        reduction_pct = ((current_monthly_cost - after_cost) / current_monthly_cost * 100
                         if current_monthly_cost > 0 else 0)
        payback = total_mig_cost / total_monthly_sav if total_monthly_sav > 0 else 0

        return OptimizationReport(
            timestamp=datetime.now(),
            approved_migrations=final_approved,
            rejected_migrations=rejected,
            total_migration_cost=round(total_mig_cost, 2),
            total_monthly_savings=round(total_monthly_sav, 2),
            total_annual_savings=round(total_annual_sav, 2),
            estimated_payback_months=round(payback, 1),
            total_data_to_move_gb=round(total_data_gb, 2),
            before_monthly_cost=round(current_monthly_cost, 2),
            after_monthly_cost=round(after_cost, 2),
            cost_reduction_percentage=round(reduction_pct, 1),
        )

    def _evaluate_migration(
        self, f: FileAccessRecord, cls: ClassificationResult
    ) -> MigrationPlan:
        """Evaluate whether a single file migration is worthwhile."""

        # --- Anti-thrashing check ---
        if f.last_migration_date:
            days_since_migration = (datetime.now() - f.last_migration_date).days
            if days_since_migration < self.cooldown_days:
                return MigrationPlan(
                    file_id=f.file_id,
                    file_name=f.file_name,
                    file_size_gb=f.file_size_gb,
                    source_location=f.current_location,
                    target_location=cls.recommended_location,
                    tier=cls.tier,
                    migration_cost=0,
                    monthly_savings=0,
                    payback_months=0,
                    approved=False,
                    rejection_reason=(
                        f"Cooldown active: migrated {days_since_migration} days ago "
                        f"(min {self.cooldown_days} days)"
                    ),
                )

        # --- Calculate migration cost ---
        # Migration cost = egress to download + re-upload (one-time)
        migration_cost = f.file_size_gb * self.egress_per_gb

        # --- Calculate monthly savings ---
        monthly_savings = self._calculate_savings(f, cls)

        # --- Payback check ---
        if monthly_savings <= 0:
            return MigrationPlan(
                file_id=f.file_id,
                file_name=f.file_name,
                file_size_gb=f.file_size_gb,
                source_location=f.current_location,
                target_location=cls.recommended_location,
                tier=cls.tier,
                migration_cost=round(migration_cost, 2),
                monthly_savings=0,
                payback_months=0,
                approved=False,
                rejection_reason="No savings from migration",
            )

        payback_months = migration_cost / monthly_savings

        # Check minimum savings threshold
        if monthly_savings < self.min_savings:
            approved = False
            reason = f"Monthly savings ${monthly_savings:.2f} below minimum ${self.min_savings}"
        # Check payback period
        elif payback_months > self.max_payback_months:
            approved = False
            reason = f"Payback {payback_months:.1f} months exceeds max {self.max_payback_months} months"
        else:
            approved = True
            reason = None

        # Priority = monthly savings (higher = more urgent to migrate)
        priority = monthly_savings

        return MigrationPlan(
            file_id=f.file_id,
            file_name=f.file_name,
            file_size_gb=f.file_size_gb,
            source_location=f.current_location,
            target_location=cls.recommended_location,
            tier=cls.tier,
            migration_cost=round(migration_cost, 2),
            monthly_savings=round(monthly_savings, 2),
            payback_months=round(payback_months, 2),
            approved=approved,
            rejection_reason=reason,
            priority_score=round(priority, 2),
        )

    def _calculate_savings(
        self, f: FileAccessRecord, cls: ClassificationResult
    ) -> float:
        """
        Calculate monthly savings from migrating a file.
        
        Savings = (current_monthly_cost) - (new_monthly_cost)
        """
        # Current cost
        if f.current_location == "cloud_s3":
            current_storage = f.file_size_gb * self.s3_per_gb
            current_egress = f.access_count_monthly * f.file_size_gb * self.egress_per_gb
        elif f.current_location == "cloud_glacier":
            current_storage = f.file_size_gb * self.glacier_per_gb
            current_egress = (f.access_count_monthly * f.file_size_gb *
                              self.pricing.get("glacier_retrieval_per_gb", 0.01))
        else:  # local
            current_storage = 0
            current_egress = 0

        current_total = current_storage + current_egress

        # New cost after migration
        target = cls.recommended_location
        if target == "local":
            new_storage = 0  # Covered by server amortization
            new_egress = 0   # No egress for local access
        elif target == "cloud_s3":
            new_storage = f.file_size_gb * self.s3_per_gb
            new_egress = f.access_count_monthly * f.file_size_gb * self.egress_per_gb
        elif target == "cloud_glacier":
            new_storage = f.file_size_gb * self.glacier_per_gb
            new_egress = 0  # Archive = almost no access

        new_total = new_storage + new_egress

        return current_total - new_total
