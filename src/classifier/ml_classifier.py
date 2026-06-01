"""
Layer 3: ML-Based Classification Engine
==========================================
Uses a trained Random Forest / Decision Tree model to classify files
into Hot/Warm/Cold/Archive tiers. Falls back to rule-based classification
if no trained model is found.

This replaces the hard-coded thresholds with a machine learning approach,
which is a key contribution of the thesis.
"""

import os
import numpy as np
import joblib
from datetime import datetime
from typing import List

from src.collector.base import FileAccessRecord
from src.classifier.hot_cold_classifier import (
    DataTier,
    TIER_LOCATIONS,
    ClassificationResult,
    ClassificationReport,
    HotColdClassifier,
)


# Tier mapping from model output (int) to DataTier enum
LABEL_TO_TIER = {
    0: DataTier.HOT,
    1: DataTier.COLD,
}


class MLClassifier:
    """
    ML-based file classifier using scikit-learn Random Forest.
    
    Key differences from rule-based HotColdClassifier:
    - Uses trained model instead of hard-coded thresholds
    - Produces probability-based confidence scores
    - Can capture complex non-linear patterns in access data
    - Falls back to rule-based if no model is available
    """

    MODEL_PATH = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "model", "rf_classifier.joblib"
    )

    def __init__(self, config: dict):
        self.config = config
        self.model = None
        self.fallback = HotColdClassifier(config)
        self.using_ml = False

        # Try to load trained model
        if os.path.exists(self.MODEL_PATH):
            try:
                self.model = joblib.load(self.MODEL_PATH)
                self.using_ml = True
                print(f"  [ML] Loaded trained model: {self.MODEL_PATH}")
            except Exception as e:
                print(f"  [ML] Failed to load model, using rule-based fallback: {e}")
        else:
            print(f"  [ML] No trained model found, using rule-based fallback")
            print(f"       Run: python scripts/train_model.py")

    def classify(self, files: List[FileAccessRecord]) -> ClassificationReport:
        """Classify all files using ML model or fallback."""
        if not self.using_ml:
            return self.fallback.classify(files)

        results = []
        summary = {t.value: 0 for t in DataTier}
        size_by_tier = {t.value: 0.0 for t in DataTier}
        migration_candidates = []

        # Extract features for all files
        X = self._extract_features(files)

        # Predict tiers
        predictions = self.model.predict(X)
        probabilities = self.model.predict_proba(X)

        for i, f in enumerate(files):
            tier = LABEL_TO_TIER[predictions[i]]
            confidence = float(np.max(probabilities[i]))
            recommended = TIER_LOCATIONS[tier]
            needs_migration = f.current_location != recommended

            # Determine migration direction
            if not needs_migration:
                direction = "none"
            elif recommended == "local":
                direction = "to_local"
            elif recommended == "cloud_glacier":
                direction = "to_glacier"
            else:
                direction = "to_cloud"

            # Build reason string with probabilities
            probs_str = ", ".join(
                f"{LABEL_TO_TIER[j].value}:{probabilities[i][j]:.0%}"
                for j in range(len(probabilities[i]))
            )
            reason = f"ML prediction: {tier.value} (confidence: {confidence:.0%}) [{probs_str}]"

            result = ClassificationResult(
                file_id=f.file_id,
                file_name=f.file_name,
                file_size_gb=f.file_size_gb,
                current_location=f.current_location,
                tier=tier,
                recommended_location=recommended,
                needs_migration=needs_migration,
                migration_direction=direction,
                confidence=confidence,
                reason=reason,
            )

            results.append(result)
            summary[tier.value] += 1
            size_by_tier[tier.value] += f.file_size_gb
            if needs_migration:
                migration_candidates.append(result)

        return ClassificationReport(
            timestamp=datetime.now(),
            results=results,
            summary=summary,
            migration_candidates=migration_candidates,
            total_files=len(files),
            total_needing_migration=len(migration_candidates),
            size_by_tier=size_by_tier,
        )

    def _extract_features(self, files: List[FileAccessRecord]) -> np.ndarray:
        """
        Extract the same 7 features used during training.
        
        Features:
          0. access_count_today
          1. access_count_weekly
          2. access_count_monthly
          3. days_since_last_access
          4. file_size_gb
          5. access_intensity (access_today / size)
          6. access_recency_ratio (access_today / days_since)
        """
        X = []
        for f in files:
            access_intensity = f.access_count_today / max(f.file_size_gb, 0.1)
            access_recency_ratio = f.access_count_today / max(f.days_since_last_access, 1)

            features = [
                f.access_count_today,
                f.access_count_weekly,
                f.access_count_monthly,
                f.days_since_last_access,
                f.file_size_gb,
                access_intensity,
                access_recency_ratio,
            ]
            X.append(features)

        return np.array(X)

    def get_method_name(self) -> str:
        """Return the classification method being used."""
        if self.using_ml:
            model_type = type(self.model).__name__
            return f"ML ({model_type})"
        return "Rule-Based (fallback)"
