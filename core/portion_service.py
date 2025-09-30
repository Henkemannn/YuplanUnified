from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import List, Optional

from sqlalchemy import func  # noqa: F401 (may be used later for aggregation optimisations)

from .db import get_session
from .models import PortionGuideline, ServiceMetric

# --------------------------------------------------------------------------------------
# Portion Recommendation Algorithm Constants & Rationale
# --------------------------------------------------------------------------------------
# SAFETY_FACTOR: Applied after blending to provide a slight production buffer that
# covers normal variance and reduces stock-out risk without driving major waste.
# 5% was chosen as a conservative uplift that is easy to explain; tune later via A/B.
SAFETY_FACTOR = 1.05

# MIN_HISTORY_POINTS: Threshold at which we consider the historical sample size
# sufficiently representative to (a) apply statistical trimming and (b) shift
# more weight towards data vs baseline guideline. Below this threshold we still
# blend (rather than pure fallback) so early data can begin influencing output.
MIN_HISTORY_POINTS = 5

# RECENT_DAYS: Look‑back horizon for historical service metrics. Chosen to balance
# seasonality drift (too long) vs insufficient variation (too short). 120 days ≈ 4 months.
RECENT_DAYS = 120

# WEIGHTS_FEW / WEIGHTS_MANY: Two-stage weighting. With sparse data (< MIN_HISTORY_POINTS)
# the baseline guideline dominates (80%) to stabilize recommendations, while still
# letting emerging usage signal in (20%). Once we have enough points (>= MIN), we
# trust data more strongly (70%) while retaining 30% baseline anchor to mitigate
# abrupt shifts if last quarter differs from canonical target.
WEIGHTS_FEW = (0.8, 0.2)
WEIGHTS_MANY = (0.3, 0.7)

# TRIM_FRACTION: When we have many points we apply a symmetric trimmed mean to
# reduce influence from outliers (e.g., atypical events, recording errors). 10%
# per tail (total 20%) is a common robust default; if sample_size * frac < 1, we
# fall back to the plain mean.
TRIM_FRACTION = 0.1

# SAMPLE SIZE SEMANTICS: The sample_size we expose is the raw count BEFORE any
# trimming so that consumers understand total datapoints considered; the trimmed
# mean only affects the internal history_mean_used value.
# --------------------------------------------------------------------------------------

@dataclass
class BlendedResult:
    recommended_g_per_guest: int
    source: str  # baseline|blended
    sample_size: int
    baseline_used: int
    history_mean_raw: Optional[float]
    history_mean_used: Optional[float]

class PortionService:
    def blended_g_per_guest(self, tenant_id: int, category: str, week: Optional[int] = None) -> BlendedResult:
        """Return a recommended grams-per-guest value.

        Steps:
          1. Baseline retrieval: locate first matching guideline row; fallback 300g if absent.
          2. History collection: served_g_per_guest values in the last RECENT_DAYS.
          3. Branch:
             - 0 points  -> baseline_only (baseline * SAFETY_FACTOR)
             - 1..(MIN_HISTORY_POINTS-1) -> simple mean; blend WEIGHTS_FEW (baseline heavy)
             - >= MIN_HISTORY_POINTS     -> trimmed mean; blend WEIGHTS_MANY (data heavy)
          4. Apply SAFETY_FACTOR, round to nearest int.

        Returns BlendedResult capturing:
          recommended_g_per_guest  Final integer recommendation
          source                   'baseline' or 'blended'
          sample_size              Raw history count before trimming
          baseline_used            Baseline grams used in blend
          history_mean_raw         Untrimmed arithmetic mean of all points (if any)
          history_mean_used        Mean actually used in blend (trimmed mean if applicable)
        """
        baseline = self._baseline(tenant_id, category)
        history_values = self._history_values(tenant_id, category)
        sample_size = len(history_values)
        if sample_size == 0:
            recommended = int(round(baseline * SAFETY_FACTOR))
            return BlendedResult(recommended, 'baseline', 0, baseline, None, None)

        # Untrimmed raw mean (always computed when we have data for transparency)
        raw_mean = sum(history_values) / sample_size

        if sample_size < MIN_HISTORY_POINTS:
            hist_mean_used = raw_mean
            b_w, h_w = WEIGHTS_FEW
        else:
            hist_mean_used = self._trimmed_mean(history_values, TRIM_FRACTION)
            b_w, h_w = WEIGHTS_MANY

        blended = b_w * baseline + h_w * hist_mean_used
        blended *= SAFETY_FACTOR
        return BlendedResult(
            int(round(blended)),
            'blended',
            sample_size,
            baseline,
            raw_mean,
            hist_mean_used,
        )

    # --- Helpers ---
    def _baseline(self, tenant_id: int, category: str) -> int:
        db = get_session()
        try:
            row: PortionGuideline | None = db.query(PortionGuideline).filter(PortionGuideline.tenant_id == tenant_id, PortionGuideline.category == category).first()
            if row is not None and row.baseline_g_per_guest is not None:
                return int(row.baseline_g_per_guest)
            return 300
        finally:
            db.close()

    def _history_values(self, tenant_id: int, category: str) -> List[float]:
        db = get_session()
        try:
            since = date.today() - timedelta(days=RECENT_DAYS)
            q = db.query(ServiceMetric.served_g_per_guest).filter(ServiceMetric.tenant_id == tenant_id, ServiceMetric.category == category, ServiceMetric.date >= since, ServiceMetric.served_g_per_guest.isnot(None))
            values = [float(v[0]) for v in q.all() if v[0] is not None]
            values.sort()
            return values
        finally:
            db.close()

    def _trimmed_mean(self, values: List[float], frac: float) -> float:
        if not values:
            return 0.0
        n = len(values)
        trim = int(n * frac)
        if trim*2 >= n:  # not enough to trim
            return sum(values) / n
        trimmed = values[trim:n-trim]
        return sum(trimmed) / len(trimmed)

    def protein_per_100g(self, tenant_id: int, category: str) -> Optional[float]:
        db = get_session()
        try:
            row = db.query(PortionGuideline).filter(PortionGuideline.tenant_id == tenant_id, PortionGuideline.category == category).first()
            if row and row.protein_per_100g is not None:
                return float(row.protein_per_100g)
            return None
        finally:
            db.close()
