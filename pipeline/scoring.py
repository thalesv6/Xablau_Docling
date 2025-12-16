from __future__ import annotations

from dataclasses import dataclass

from config import PipelineConfig
from pipeline.blocks import Block
from pipeline.candidates import Candidate
from pipeline.utils import normalize_for_match


_KEYWORDS_EMPRESA = {
    "empregador",
    "empresa",
    "razao social",
    "razão social",
    "cnpj",
    "contratante",
}

_KEYWORDS_FUNCIONARIO = {
    "funcionario",
    "funcionário",
    "empregado",
    "nome",
    "trabalhador",
    "colaborador",
}


@dataclass(frozen=True)
class ScoredCandidate:
    candidate: Candidate
    score: float
    reasons: list[str]


def _keywords_in_text(text_norm: str, keyword_set: set[str]) -> bool:
    for kw in keyword_set:
        if normalize_for_match(kw) in text_norm:
            return True
    return False


def _shape_score(text: str) -> float:
    t = text.strip()
    if len(t) < 5:
        return -1.0
    if len(t) > 120:
        return -0.5
    if any(ch.isdigit() for ch in t):
        return -0.2
    return 0.5


def score_and_rank(blocks: list[Block], candidates_payload: dict, cfg: PipelineConfig) -> dict:
    internal = candidates_payload.get("_internal") or {}
    people: list[Candidate] = internal.get("funcionarios") or []
    companies: list[Candidate] = internal.get("empresas") or []

    blocks_by_id = {b.id: b for b in blocks}
    blocks_by_index = {b.index: b for b in blocks}

    freq: dict[tuple[str, str], int] = {}
    for b in blocks:
        norm = normalize_for_match(b.text)
        for c in people:
            if c.norm and c.norm in norm:
                freq[("funcionario", c.norm)] = freq.get(("funcionario", c.norm), 0) + 1
        for c in companies:
            if c.norm and c.norm in norm:
                freq[("empresa", c.norm)] = freq.get(("empresa", c.norm), 0) + 1

    def score_one(c: Candidate) -> ScoredCandidate:
        b = blocks_by_id.get(c.block_id)
        reasons: list[str] = []
        score = 0.0

        if c.kind == "empresa" and c.source in {"keyword_line", "label_next_line", "label_next_block"}:
            score += cfg.weight_keyword_same_block
            reasons.append("label_value")

        if b is not None:
            text_norm = normalize_for_match(b.text)
            kw_set = _KEYWORDS_FUNCIONARIO if c.kind == "funcionario" else _KEYWORDS_EMPRESA
            if _keywords_in_text(text_norm, kw_set):
                score += cfg.weight_keyword_same_block
                reasons.append("keyword_same_block")

            # Nearby blocks (same page, index +/- 2)
            for delta in (-2, -1, 1, 2):
                nb = blocks_by_index.get(b.index + delta)
                if nb is None or nb.page != b.page:
                    continue
                nb_norm = normalize_for_match(nb.text)
                if _keywords_in_text(nb_norm, kw_set):
                    score += cfg.weight_keyword_nearby
                    reasons.append("keyword_nearby")
                    break

            if c.kind == "empresa" and b.page == 1 and b.y_norm <= 0.25:
                score += cfg.weight_top_of_doc_for_company
                reasons.append("top_of_doc")

        f = freq.get((c.kind, c.norm), 0)
        if f > 1:
            score += cfg.weight_frequency * float(min(f, 5) - 1)
            reasons.append("frequency")

        ss = _shape_score(c.text)
        score += cfg.weight_shape * ss
        reasons.append("shape")

        return ScoredCandidate(candidate=c, score=score, reasons=reasons)

    scored_people = [score_one(c) for c in people]
    scored_companies = [score_one(c) for c in companies]

    def stable_sort(scored: list[ScoredCandidate]) -> list[ScoredCandidate]:
        return sorted(scored, key=lambda s: (-s.score, s.candidate.block_index, s.candidate.text))

    ranked_people = stable_sort(scored_people)
    ranked_companies = stable_sort(scored_companies)

    def simplify(scored: list[ScoredCandidate]) -> list[dict]:
        out: list[dict] = []
        for s in scored:
            out.append(
                {
                    "text": s.candidate.text,
                    "block_id": s.candidate.block_id,
                    "page": s.candidate.page,
                    "score": s.score,
                    "reasons": s.reasons,
                }
            )
        return out

    return {
        "funcionario": simplify(ranked_people),
        "empresa": simplify(ranked_companies),
        "_internal": {"funcionario": ranked_people, "empresa": ranked_companies},
    }


