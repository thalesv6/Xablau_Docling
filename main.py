from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from config import PipelineConfig, resolve_model_path
from pipeline.blocks import build_blocks
from pipeline.candidates import generate_candidates
from pipeline.confidence import compute_confidence
from pipeline.decision_llm import decide_with_llm
from pipeline.extract_json import extract_docling_json
from pipeline.scoring import score_and_rank


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run(pdf_path: Path, out_path: Path, model_path: Path | None, cfg: PipelineConfig, debug: bool) -> dict:
    try:
        extracted = extract_docling_json(str(pdf_path), cfg=cfg)
    except Exception as exc:  # noqa: BLE001 - fail safe
        return {
            "funcionario": "INDEFINIDO",
            "empresa": "INDEFINIDO",
            "confidence": {"funcionario": 0.0, "empresa": 0.0},
            "debug": {"error": f"extract_failed:{type(exc).__name__}"},
        }

    if extracted.get("extraction_quality") != "ok":
        return {
            "funcionario": "INDEFINIDO",
            "empresa": "INDEFINIDO",
            "confidence": {"funcionario": 0.0, "empresa": 0.0},
            "debug": {"extraction_quality": extracted.get("extraction_quality", "unknown")},
        }

    blocks = build_blocks(extracted)
    candidates = generate_candidates(blocks, cfg=cfg)
    ranked = score_and_rank(blocks, candidates, cfg=cfg)

    decision = decide_with_llm(
        blocks=blocks,
        ranked=ranked,
        model_path=model_path,
        cfg=cfg,
    )
    conf = compute_confidence(ranked=ranked, decision=decision, blocks=blocks, cfg=cfg)

    debug_payload: dict = {
        "extraction_quality": extracted.get("extraction_quality", "unknown"),
    }
    if debug:
        debug_payload |= {
            "blocks_count": len(blocks),
            "candidates_count": {
                "funcionarios": len(candidates.get("funcionarios") or []),
                "empresas": len(candidates.get("empresas") or []),
            },
            "spacy": candidates.get("_meta") or {},
            "top_ranked": {
                "funcionario": (ranked.get("funcionario") or [])[:3],
                "empresa": (ranked.get("empresa") or [])[:3],
            },
            "llm_used": bool(decision.get("llm_used", False)),
        }

    return {
        "funcionario": decision["funcionario"],
        "empresa": decision["empresa"],
        "confidence": conf,
        "debug": debug_payload,
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Offline PDF pipeline (empresa, funcionario)")
    p.add_argument("--pdf", required=True, help="Path to input PDF")
    p.add_argument("--out", required=True, help="Path to output JSON")
    p.add_argument("--model", required=False, help="Path to GGUF model for llama.cpp")
    p.add_argument(
        "--chat-format",
        required=False,
        help="Optional llama.cpp chat format (e.g., qwen). Useful when the model needs an explicit template.",
    )
    p.add_argument(
        "--offline",
        action="store_true",
        help="Disable network access (no model downloads). If required models are missing, output will be INDEFINIDO.",
    )
    p.add_argument("--debug", action="store_true", help="Include debug details in the output JSON.")
    return p


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    cfg = PipelineConfig(allow_network=not bool(args.offline), llama_chat_format=args.chat_format)
    pdf_path = Path(args.pdf)
    out_path = Path(args.out)
    model_path = resolve_model_path(args.model)

    payload = run(pdf_path=pdf_path, out_path=out_path, model_path=model_path, cfg=cfg, debug=bool(args.debug))
    write_json(out_path, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))


