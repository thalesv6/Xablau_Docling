from __future__ import annotations

from config import PipelineConfig
from pipeline.blocks import Block
from pipeline.utils import normalize_for_match


def _clamp01(x: float) -> float:
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


def _margin_confidence(items: list[dict]) -> float:
    if not items:
        return 0.0
    top1 = float(items[0].get("score", 0.0))
    top2 = float(items[1].get("score", 0.0)) if len(items) > 1 else 0.0
    denom = max(abs(top1), 1.0)
    margin = (top1 - top2) / denom
    # Map roughly from [-1, +1] to [0, 1], then clamp.
    return _clamp01((margin + 1.0) / 2.0)


def _redundancy_bonus(chosen: str, blocks: list[Block]) -> float:
    if chosen == "INDEFINIDO":
        return 0.0
    chosen_norm = normalize_for_match(chosen)
    hits = 0
    for b in blocks:
        if chosen_norm and chosen_norm in normalize_for_match(b.text):
            hits += 1
    if hits <= 1:
        return 0.0
    # Deterministic small bonus capped.
    return min(0.2, 0.05 * float(hits - 1))


def compute_confidence(ranked: dict, decision: dict, blocks: list[Block], cfg: PipelineConfig) -> dict:
    ranked_f = ranked.get("funcionario") or []
    ranked_e = ranked.get("empresa") or []

    chosen_f = decision.get("funcionario", "INDEFINIDO")
    chosen_e = decision.get("empresa", "INDEFINIDO")

    def one(kind: str, ranked_items: list[dict], chosen: str) -> float:
        if chosen == "INDEFINIDO":
            return 0.0
        base = _margin_confidence(ranked_items)
        bonus = _redundancy_bonus(chosen, blocks)
        val = _clamp01(base + bonus)
        return max(cfg.min_confidence_when_defined, val)

    return {
        "funcionario": one("funcionario", ranked_f, chosen_f),
        "empresa": one("empresa", ranked_e, chosen_e),
    }


