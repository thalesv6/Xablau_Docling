from __future__ import annotations

from config import PipelineConfig
from pipeline.extract_json import extract_docling_json


def test_extract_returns_weak_when_docling_missing() -> None:
    cfg = PipelineConfig(min_useful_chars=10)
    # This test assumes Docling may not be installed in CI; function must fail safe.
    out = extract_docling_json("nonexistent.pdf", cfg=cfg)
    assert out["extraction_quality"] in {"ok", "weak"}


