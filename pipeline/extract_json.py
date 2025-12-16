from __future__ import annotations

import json
import os
from typing import Any

from config import PipelineConfig
from pipeline.utils import useful_char_count


def _maybe_to_dict(obj: Any) -> Any:
    if obj is None:
        return None
    for attr in ("model_dump", "dict", "to_dict"):
        fn = getattr(obj, attr, None)
        if callable(fn):
            try:
                return fn()
            except Exception:  # noqa: BLE001
                pass
    to_json = getattr(obj, "to_json", None)
    if callable(to_json):
        try:
            return json.loads(to_json())
        except Exception:  # noqa: BLE001
            pass
    return obj


def _extract_blocks_recursive(node: Any, page_hint: int | None = None) -> list[dict]:
    blocks: list[dict] = []
    if isinstance(node, dict):
        text = node.get("text")
        if isinstance(text, str) and text.strip():
            page = node.get("page") or node.get("page_no") or node.get("pageNumber") or page_hint
            if isinstance(page, int) and page <= 0:
                page = 1
            bbox = node.get("bbox") or node.get("bounding_box") or node.get("box")
            blocks.append({"text": text, "page": int(page) if page is not None else 1, "bbox": bbox})
        # propagate page hints
        new_page_hint = page_hint
        for k in ("page", "page_no", "pageNumber"):
            if k in node and isinstance(node.get(k), int):
                new_page_hint = int(node[k])
                break
        for v in node.values():
            blocks.extend(_extract_blocks_recursive(v, page_hint=new_page_hint))
        return blocks

    if isinstance(node, list):
        for item in node:
            blocks.extend(_extract_blocks_recursive(item, page_hint=page_hint))
        return blocks

    return blocks


def extract_docling_json(pdf_path: str, cfg: PipelineConfig) -> dict:
    """
    Convert a PDF into a normalized dict with a minimal schema:
      - blocks: list[{text,page,bbox}]
      - extraction_quality: "ok" | "weak"

    This function is intentionally defensive: Docling APIs can vary by version.
    If extraction fails or yields too little text, we return extraction_quality="weak".
    """

    raw: Any
    try:
        if not cfg.allow_network:
            # Best-effort offline mode: force HF/transformers to stay offline.
            os.environ.setdefault("HF_HUB_OFFLINE", "1")
            os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
            os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

        # Try the most common API shapes.
        try:
            from docling.document_converter import DocumentConverter  # type: ignore
        except Exception:  # noqa: BLE001
            from docling import DocumentConverter  # type: ignore

        converter = DocumentConverter()
        result = converter.convert(pdf_path)
        raw = _maybe_to_dict(result)
    except Exception:  # noqa: BLE001
        return {"blocks": [], "extraction_quality": "weak"}

    raw = _maybe_to_dict(raw)
    blocks = _extract_blocks_recursive(raw)

    quality = "ok" if useful_char_count([b["text"] for b in blocks]) >= cfg.min_useful_chars else "weak"
    return {
        "blocks": blocks,
        "extraction_quality": quality,
    }


