from api.compliance.risk.evaluate import evaluate_risk_gate
from api.compliance.risk.schemas import RiskGateResult

__all__ = ["evaluate_risk_gate", "score_pld_matrix", "RiskGateResult"]


def score_pld_matrix(*args, **kwargs):
    from api.compliance.risk.matrix_score import score_pld_matrix as _score

    return _score(*args, **kwargs)

