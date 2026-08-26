from __future__ import annotations

from xora_chart.config import load_config
from xora_chart.domain.models import Opportunity


def rank_opportunities(opps: list[Opportunity]) -> list[Opportunity]:
    cfg = load_config().get("ranking", {})
    weights = cfg.get("weights", {})
    w_sim = float(weights.get("similarity", 0.45))
    w_conf = float(weights.get("confidence", 0.30))
    w_rr = float(weights.get("risk_reward", 0.25))
    top_n = int(cfg.get("top_n", 10))

    for o in opps:
        sim = o.best_match.similarity if o.best_match else 0.0
        conf = o.trade.confidence if o.trade else 0.0
        rr = o.trade.risk_reward if o.trade else 0.0
        # normalize RR roughly into 0–100 (cap at 5R)
        rr_score = min(100.0, (rr / 5.0) * 100)
        o.rank_score = round(w_sim * sim + w_conf * conf + w_rr * rr_score, 2)

    opps.sort(key=lambda x: x.rank_score, reverse=True)
    return opps[:top_n]
