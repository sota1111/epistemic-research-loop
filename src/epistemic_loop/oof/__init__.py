"""Row-level out-of-fold storage and residual-diversity analysis."""

from epistemic_loop.oof.diversity import (
    OOFAnalysis,
    analyze,
    effective_rank,
    marginal_ensemble_gain,
    pairwise_residual_correlation,
    prediction_disagreement,
)
from epistemic_loop.oof.ensemble import blend_predictions, build_cross_fitted_ensemble
from epistemic_loop.oof.store import OOFStore

__all__ = [
    "OOFAnalysis",
    "OOFStore",
    "analyze",
    "effective_rank",
    "marginal_ensemble_gain",
    "pairwise_residual_correlation",
    "prediction_disagreement",
    "blend_predictions",
    "build_cross_fitted_ensemble",
]
