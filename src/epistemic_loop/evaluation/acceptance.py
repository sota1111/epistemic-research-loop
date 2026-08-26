from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from epistemic_loop.plugins.ieee_cis import IEEERunAcceptance


class AcceptanceStatus(StrEnum):
    PASS = "pass"
    PARTIAL_PASS = "partial_pass"
    FAIL = "fail"
    UNMEASURED = "unmeasured"


@dataclass(frozen=True)
class AcceptanceLayer:
    name: str
    status: AcceptanceStatus
    satisfied: tuple[str, ...]
    outstanding: tuple[str, ...]


@dataclass(frozen=True)
class V031AcceptanceReport:
    control_plane: AcceptanceLayer
    dynamic_structure_mechanism: AcceptanceLayer
    ieee_cis_capability: AcceptanceLayer
    primary_endpoint: AcceptanceLayer
    validated_high_leverage_structures: int

    @property
    def generic_structure_success(self) -> bool:
        return self.validated_high_leverage_structures >= 1

    @classmethod
    def assess(
        cls,
        *,
        control_plane_checks: dict[str, bool],
        structure_checks: dict[str, bool],
        ieee_cis: IEEERunAcceptance,
        locked_private_auc: float | None,
        matched_baseline_private_auc: float | None,
        baseline_is_matched: bool = False,
        multi_seed_passed: bool,
        multiple_competitions_passed: bool,
        validated_high_leverage_structures: int,
    ) -> V031AcceptanceReport:
        control = _layer("control_plane", control_plane_checks)
        structure = _layer("dynamic_structure_mechanism", structure_checks, partial_when_mixed=True)
        ieee_checks = {
            "validated_behavioral_client_proxy": ieee_cis.validated_behavioral_client_proxies >= 1,
            "three_forward_horizons": ieee_cis.forward_horizons >= 3,
            "fold_safe_uid_candidate": ieee_cis.fold_safe_uid_candidates >= 1,
            "known_new_client_slice": ieee_cis.known_new_client_slice,
            "two_model_families": len(ieee_cis.model_families) >= 2,
            "three_oof_candidates": ieee_cis.oof_candidates >= 3,
            "ensemble_candidate": ieee_cis.ensemble_candidates >= 1,
            "locked_submission": ieee_cis.locked_submissions >= 1,
        }
        ieee_layer = _layer("ieee_cis_capability", ieee_checks, partial_when_mixed=False)
        if locked_private_auc is None or matched_baseline_private_auc is None:
            endpoint = AcceptanceLayer(
                name="primary_endpoint",
                status=AcceptanceStatus.UNMEASURED,
                satisfied=(),
                outstanding=("locked_private_auc", "matched_baseline_private_auc"),
            )
        else:
            endpoint_checks = {
                "reference_private_auc_not_worse": locked_private_auc >= matched_baseline_private_auc,
                "matched_baseline_comparison": baseline_is_matched,
                "multi_seed": multi_seed_passed,
                "multiple_competitions": multiple_competitions_passed,
            }
            endpoint = _layer("primary_endpoint", endpoint_checks, partial_when_mixed=False)
        return cls(
            control_plane=control,
            dynamic_structure_mechanism=structure,
            ieee_cis_capability=ieee_layer,
            primary_endpoint=endpoint,
            validated_high_leverage_structures=validated_high_leverage_structures,
        )


def _layer(
    name: str,
    checks: dict[str, bool],
    *,
    partial_when_mixed: bool = False,
) -> AcceptanceLayer:
    satisfied = tuple(key for key, passed in checks.items() if passed)
    outstanding = tuple(key for key, passed in checks.items() if not passed)
    if not outstanding:
        status = AcceptanceStatus.PASS
    elif partial_when_mixed and satisfied:
        status = AcceptanceStatus.PARTIAL_PASS
    else:
        status = AcceptanceStatus.FAIL
    return AcceptanceLayer(name=name, status=status, satisfied=satisfied, outstanding=outstanding)
