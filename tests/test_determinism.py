from __future__ import annotations

from config import PipelineConfig
from pipeline.blocks import build_blocks
from pipeline.candidates import generate_candidates
from pipeline.confidence import compute_confidence
from pipeline.decision_llm import validate_llm_response
from pipeline.scoring import score_and_rank


def test_block_ids_are_deterministic() -> None:
    extracted = {
        "blocks": [
            {"text": "EMPRESA ACME LTDA", "page": 1, "bbox": [0, 10, 100, 30]},
            {"text": "Nome: João da Silva", "page": 1, "bbox": [0, 40, 100, 60]},
        ],
        "extraction_quality": "ok",
    }
    b1 = build_blocks(extracted)
    b2 = build_blocks(extracted)
    assert [b.id for b in b1] == [b.id for b in b2]


def test_scoring_is_stable() -> None:
    cfg = PipelineConfig()
    extracted = {
        "blocks": [
            {"text": "EMPREGADOR: EMPRESA ACME LTDA", "page": 1, "bbox": [0, 10, 100, 30]},
            {"text": "FUNCIONÁRIO Nome: João da Silva", "page": 1, "bbox": [0, 40, 100, 60]},
        ],
        "extraction_quality": "ok",
    }
    blocks = build_blocks(extracted)
    cands = generate_candidates(blocks, cfg=cfg)
    ranked1 = score_and_rank(blocks, cands, cfg=cfg)
    ranked2 = score_and_rank(blocks, cands, cfg=cfg)
    assert ranked1["empresa"] == ranked2["empresa"]
    assert ranked1["funcionario"] == ranked2["funcionario"]


def test_company_keyword_line_beats_document_title() -> None:
    cfg = PipelineConfig()
    extracted = {
        "blocks": [
            {"text": "EXAME FÍSICO - PERIÓDICO", "page": 1, "bbox": [0, 5, 100, 20]},
            {"text": "Empresa: CEI Erinice Siqueira", "page": 1, "bbox": [0, 30, 100, 45]},
            {"text": "Nome: Sandra Regina Hortencio", "page": 1, "bbox": [0, 50, 100, 65]},
        ],
        "extraction_quality": "ok",
    }
    blocks = build_blocks(extracted)
    cands = generate_candidates(blocks, cfg=cfg)
    ranked = score_and_rank(blocks, cands, cfg=cfg)
    assert ranked["empresa"], "Expected at least one company candidate"
    assert ranked["empresa"][0]["text"] == "CEI Erinice Siqueira"


def test_llm_json_validation_rejects_out_of_set() -> None:
    allowed_f = ["João da Silva"]
    allowed_e = ["EMPRESA ACME LTDA"]
    d = validate_llm_response('{"funcionario":"Maria","empresa":"EMPRESA ACME LTDA"}', allowed_f, allowed_e)
    assert d.funcionario == "INDEFINIDO"
    assert d.empresa == "EMPRESA ACME LTDA"


def test_confidence_zero_when_undefined() -> None:
    cfg = PipelineConfig()
    extracted = {
        "blocks": [{"text": "x", "page": 1, "bbox": [0, 0, 1, 1]}],
        "extraction_quality": "ok",
    }
    blocks = build_blocks(extracted)
    ranked = {"funcionario": [], "empresa": []}
    decision = {"funcionario": "INDEFINIDO", "empresa": "INDEFINIDO"}
    conf = compute_confidence(ranked=ranked, decision=decision, blocks=blocks, cfg=cfg)
    assert conf["funcionario"] == 0.0
    assert conf["empresa"] == 0.0


