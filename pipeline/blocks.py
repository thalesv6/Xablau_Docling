from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pipeline.utils import normalize_text, stable_short_hash


@dataclass(frozen=True)
class Block:
    id: str
    page: int
    index: int
    text: str
    bbox: tuple[float, float, float, float] | None
    y_norm: float


def _parse_bbox(bbox: Any) -> tuple[float, float, float, float] | None:
    if bbox is None:
        return None
    if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
        try:
            x0, y0, x1, y1 = (float(b) for b in bbox)
            return (x0, y0, x1, y1)
        except Exception:  # noqa: BLE001
            return None
    if isinstance(bbox, dict):
        keys = ("x0", "y0", "x1", "y1")
        if all(k in bbox for k in keys):
            try:
                return (float(bbox["x0"]), float(bbox["y0"]), float(bbox["x1"]), float(bbox["y1"]))
            except Exception:  # noqa: BLE001
                return None
        # alternate key styles
        keys2 = ("left", "top", "right", "bottom")
        if all(k in bbox for k in keys2):
            try:
                return (float(bbox["left"]), float(bbox["top"]), float(bbox["right"]), float(bbox["bottom"]))
            except Exception:  # noqa: BLE001
                return None
    return None


def build_blocks(extracted: dict) -> list[Block]:
    raw_blocks = extracted.get("blocks") or []

    blocks: list[Block] = []
    for idx, rb in enumerate(raw_blocks):
        if not isinstance(rb, dict):
            continue
        page = rb.get("page")
        try:
            page_i = int(page) if page is not None else 1
        except Exception:  # noqa: BLE001
            page_i = 1
        if page_i <= 0:
            page_i = 1
        text = normalize_text(str(rb.get("text") or ""))
        bbox = _parse_bbox(rb.get("bbox"))
        blocks.append(
            Block(
                id="",
                page=page_i,
                index=idx,
                text=text,
                bbox=bbox,
                y_norm=0.0,
            )
        )

    # Compute per-page normalization for y.
    max_y_by_page: dict[int, float] = {}
    for b in blocks:
        if b.bbox is None:
            continue
        _, y0, _, y1 = b.bbox
        max_y_by_page[b.page] = max(max_y_by_page.get(b.page, 0.0), y0, y1)

    normalized: list[Block] = []
    for b in blocks:
        if b.bbox is None:
            y_norm = 0.0
        else:
            _, y0, _, _ = b.bbox
            denom = max_y_by_page.get(b.page, 0.0)
            y_norm = float(y0 / denom) if denom > 0 else 0.0

        material = f"{b.page}:{b.index}:{b.bbox}:{b.text}"
        block_id = stable_short_hash(material, length=12)
        normalized.append(
            Block(
                id=block_id,
                page=b.page,
                index=b.index,
                text=b.text,
                bbox=b.bbox,
                y_norm=y_norm,
            )
        )

    return normalized


