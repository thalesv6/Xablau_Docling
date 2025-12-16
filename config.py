from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PipelineConfig:
    seed: int = 42
    allow_network: bool = True

    # Extraction quality
    min_useful_chars: int = 200

    # Candidate generation
    spacy_model: str = "pt_core_news_lg"
    max_candidates_per_type: int = 30

    # Scoring
    top_k_for_llm: int = 5
    weight_keyword_same_block: float = 2.0
    weight_keyword_nearby: float = 1.0
    weight_top_of_doc_for_company: float = 1.5
    weight_frequency: float = 0.5
    weight_shape: float = 0.75

    # LLM decision
    llama_n_ctx: int = 2048
    llama_max_tokens: int = 256
    llama_temperature: float = 0.0
    llama_top_p: float = 1.0
    llama_top_k: int = 0
    llama_chat_format: str | None = None

    # Confidence
    min_confidence_when_defined: float = 0.2


def resolve_model_path(model_path: str | None) -> Path | None:
    if model_path is None:
        return None
    p = Path(model_path)
    return p


