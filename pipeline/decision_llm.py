from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config import PipelineConfig
from pipeline.blocks import Block


@dataclass(frozen=True)
class Decision:
    funcionario: str
    empresa: str


def _fallback_decision(ranked: dict) -> Decision:
    def break_tie(top1: dict, top2: dict) -> str | None:
        t1 = str(top1.get("text", "")).strip()
        t2 = str(top2.get("text", "")).strip()
        if not t1 or not t2:
            return None
        # If one is a strict superset of the other, prefer the more specific (longer) one.
        if t1 in t2 and len(t2) > len(t1):
            return t2
        if t2 in t1 and len(t1) > len(t2):
            return t1
        # Prefer the one with stronger evidence if available.
        r1 = set(top1.get("reasons") or [])
        r2 = set(top2.get("reasons") or [])
        if "keyword_same_block" in r1 and "keyword_same_block" not in r2:
            return t1
        if "keyword_same_block" in r2 and "keyword_same_block" not in r1:
            return t2
        if "keyword_nearby" in r1 and "keyword_nearby" not in r2:
            return t1
        if "keyword_nearby" in r2 and "keyword_nearby" not in r1:
            return t2
        return None

    def pick(kind: str) -> str:
        items = ranked.get(kind) or []
        if not items:
            return "INDEFINIDO"
        top1 = items[0]
        top2 = items[1] if len(items) > 1 else None
        if top2 is None:
            return top1["text"] if float(top1.get("score", 0.0)) > 0.0 else "INDEFINIDO"
        # simple deterministic margin rule
        s1 = float(top1.get("score", 0.0))
        s2 = float(top2.get("score", 0.0))
        if (s1 - s2) >= 1.0 and s1 > 0.0:
            return top1["text"]
        # Deterministic tie-breakers (safe, no invention): still only pick from candidates.
        if abs(s1 - s2) < 1e-9 and s1 >= 3.0:
            tied = break_tie(top1, top2)
            if tied is not None:
                return tied
            # If ranking is stable and the score is strong enough, accept the top1.
            return top1["text"]
        return "INDEFINIDO"

    return Decision(funcionario=pick("funcionario"), empresa=pick("empresa"))


def _parse_json_strict(text: str) -> dict | None:
    try:
        obj = json.loads(text)
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(obj, dict):
        return None
    return obj


def _validate_choice(value: Any, allowed: set[str]) -> str:
    if not isinstance(value, str):
        return "INDEFINIDO"
    if value == "INDEFINIDO":
        return "INDEFINIDO"
    return value if value in allowed else "INDEFINIDO"


def validate_llm_response(raw_text: str, allowed_funcionarios: list[str], allowed_empresas: list[str]) -> Decision:
    obj = _parse_json_strict(raw_text)
    if obj is None:
        return Decision(funcionario="INDEFINIDO", empresa="INDEFINIDO")
    allowed_f = set(allowed_funcionarios) | {"INDEFINIDO"}
    allowed_e = set(allowed_empresas) | {"INDEFINIDO"}
    funcionario = _validate_choice(obj.get("funcionario"), allowed_f)
    empresa = _validate_choice(obj.get("empresa"), allowed_e)
    return Decision(funcionario=funcionario, empresa=empresa)


def _build_prompt(allowed_funcionarios: list[str], allowed_empresas: list[str]) -> str:
    return (
        "You are a strict information extractor.\n"
        "You must answer with a single JSON object and nothing else.\n"
        "Rules:\n"
        "- You are NOT allowed to invent names.\n"
        "- You MUST choose ONLY from the provided candidates, or INDEFINIDO.\n"
        "- Output must be strict JSON.\n\n"
        f"FUNCIONARIO_CANDIDATES = {json.dumps(allowed_funcionarios, ensure_ascii=False)}\n"
        f"EMPRESA_CANDIDATES = {json.dumps(allowed_empresas, ensure_ascii=False)}\n\n"
        'Return JSON exactly like: {"funcionario": "...|INDEFINIDO", "empresa": "...|INDEFINIDO"}\n'
    )


def decide_with_llm(blocks: list[Block], ranked: dict, model_path: Path | None, cfg: PipelineConfig) -> dict:
    # Use only top-K candidates to constrain the model.
    top_f = [c["text"] for c in (ranked.get("funcionario") or [])[: cfg.top_k_for_llm]]
    top_e = [c["text"] for c in (ranked.get("empresa") or [])[: cfg.top_k_for_llm]]

    if model_path is None or not model_path.exists():
        d = _fallback_decision(ranked)
        return {"funcionario": d.funcionario, "empresa": d.empresa, "llm_used": False}

    try:
        from llama_cpp import Llama  # type: ignore
    except Exception:  # noqa: BLE001
        d = _fallback_decision(ranked)
        return {"funcionario": d.funcionario, "empresa": d.empresa, "llm_used": False}

    prompt = _build_prompt(top_f, top_e)

    try:
        llm = Llama(
            model_path=str(model_path),
            n_ctx=cfg.llama_n_ctx,
            seed=cfg.seed,
            chat_format=cfg.llama_chat_format,
        )
        # Prefer chat completion API if available.
        if hasattr(llm, "create_chat_completion"):
            resp = llm.create_chat_completion(
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": "Select the best options now."},
                ],
                temperature=cfg.llama_temperature,
                top_p=cfg.llama_top_p,
                top_k=cfg.llama_top_k,
                max_tokens=cfg.llama_max_tokens,
            )
            content = (
                resp.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
        else:
            resp = llm(
                prompt,
                temperature=cfg.llama_temperature,
                top_p=cfg.llama_top_p,
                top_k=cfg.llama_top_k,
                max_tokens=cfg.llama_max_tokens,
            )
            content = resp.get("choices", [{}])[0].get("text", "")
    except Exception:  # noqa: BLE001
        d = _fallback_decision(ranked)
        return {"funcionario": d.funcionario, "empresa": d.empresa, "llm_used": False}

    decision = validate_llm_response(content or "", allowed_funcionarios=top_f, allowed_empresas=top_e)
    return {"funcionario": decision.funcionario, "empresa": decision.empresa, "llm_used": True}


