from __future__ import annotations

import re
from dataclasses import dataclass

from config import PipelineConfig
from pipeline.blocks import Block
from pipeline.utils import normalize_for_match, normalize_text


_PERSON_FALLBACK_RE = re.compile(
    r"\b([A-ZÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇ][a-záàâãéèêíìîóòôõúùûç]+(?:\s+"
    r"[A-ZÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇ][a-záàâãéèêíìîóòôõúùûç]+){1,3})\b"
)

_PERSON_ALLCAPS_RE = re.compile(
    r"\b([A-ZÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇ]{2,}(?:\s+(?:DA|DE|DO|DOS|DAS)\s+)?"
    r"[A-ZÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇ]{2,}(?:\s+[A-ZÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇ]{2,}){0,2})\b"
)

_PERSON_KEYWORD_LINE_RE = re.compile(
    r"(?i)\b(?:nome|funcion[áa]rio|empregado)\b\s*[:\-]\s*(.+)$"
)

_COMPANY_HINT_RE = re.compile(
    r"\b(LTDA|Ltda|S\/A|SA|EIRELI|ME|EPP|E\.?P\.?P\.?|IND[ÚU]STRIA|COM[ÉE]RCIO|SERVI[ÇC]OS)\b"
)

_COMPANY_KEYWORD_LINE_RE = re.compile(
    r"(?i)\b(?:empresa|empregador|raz[aã]o\s+social|unidade|estabelecimento|local|fantasia|nome\s+fantasia)\b\s*(?:[:\-]\s*)?(.+)$"
)

_COMPANY_PREFIX_RE = re.compile(r"(?i)\b(CEI|EMEI|EMEF|EE|E\.E\.|E\.M\.|E\.M\.E\.I\.)\b")

_STOP_TOKENS = {
    "cpf",
    "rg",
    "cnpj",
    "ctps",
    "pis",
    "nascimento",
    "endereco",
    "endereço",
    "empresa",
    "empregador",
    "funcionario",
    "funcionário",
    "nome",
    "razao",
    "razão",
    "social",
    "medica",
    "médica",
    "saude",
    "saúde",
    "ocupacional",
}

_COMPANY_STOP_PHRASES = {
    "exame",
    "físico",
    "fisico",
    "periódico",
    "periodico",
    "atestado",
    "laudo",
    "resultado",
    "relatório",
    "relatorio",
    "ocupacional",
    "saúde ocupacional",
    "saude ocupacional",
}

_NAME_CONNECTORS = {"da", "de", "do", "dos", "das"}
_COMPANY_LABELS = {
    "empresa",
    "empregador",
    "razao social",
    "razão social",
    "fantasia",
    "nome fantasia",
    "unidade",
    "estabelecimento",
    "local",
}


@dataclass(frozen=True)
class Candidate:
    kind: str  # "funcionario" | "empresa"
    text: str
    norm: str
    block_id: str
    page: int
    block_index: int
    source: str


def _looks_like_person(text: str) -> bool:
    t = normalize_text(text)
    if any(ch.isdigit() for ch in t):
        return False
    parts = [p for p in t.split(" ") if p]
    if not (2 <= len(parts) <= 4):
        return False
    lowered = normalize_for_match(t)
    if any(tok in _STOP_TOKENS for tok in lowered.split()):
        return False
    # Allow ALL-CAPS names (very common in forms), but still require sane tokens.
    if t.isupper():
        alpha_tokens = [p for p in parts if p.isalpha() or p in {"DA", "DE", "DO", "DOS", "DAS"}]
        return len(alpha_tokens) >= 2

    # Require at least two tokens starting with uppercase, ignoring connectors.
    title_tokens = 0
    for p in parts:
        if normalize_for_match(p) in _NAME_CONNECTORS:
            continue
        if p[:1].isupper():
            title_tokens += 1
    return title_tokens >= 2


def _extract_person_candidates_spacy(blocks: list[Block], cfg: PipelineConfig) -> list[Candidate]:
    try:
        import spacy  # type: ignore
    except Exception:  # noqa: BLE001
        return []

    try:
        nlp = spacy.load(cfg.spacy_model)
    except Exception:  # noqa: BLE001
        return []

    candidates: list[Candidate] = []
    for b in blocks:
        if not b.text:
            continue
        doc = nlp(b.text)
        for ent in doc.ents:
            label = (ent.label_ or "").upper()
            if label not in {"PER", "PERSON"}:
                continue
            value = normalize_text(ent.text)
            if not _looks_like_person(value):
                continue
            candidates.append(
                Candidate(
                    kind="funcionario",
                    text=value,
                    norm=normalize_for_match(value),
                    block_id=b.id,
                    page=b.page,
                    block_index=b.index,
                    source="spacy",
                )
            )
    return candidates


def _extract_person_candidates_fallback(blocks: list[Block]) -> list[Candidate]:
    candidates: list[Candidate] = []
    for b in blocks:
        for m in _PERSON_FALLBACK_RE.finditer(b.text or ""):
            value = normalize_text(m.group(1))
            if not _looks_like_person(value):
                continue
            candidates.append(
                Candidate(
                    kind="funcionario",
                    text=value,
                    norm=normalize_for_match(value),
                    block_id=b.id,
                    page=b.page,
                    block_index=b.index,
                    source="regex",
                )
            )
        for m in _PERSON_ALLCAPS_RE.finditer(b.text or ""):
            value = normalize_text(m.group(1))
            if not _looks_like_person(value):
                continue
            candidates.append(
                Candidate(
                    kind="funcionario",
                    text=value,
                    norm=normalize_for_match(value),
                    block_id=b.id,
                    page=b.page,
                    block_index=b.index,
                    source="regex_caps",
                )
            )
    return candidates


def _extract_person_candidates_keyword_line(blocks: list[Block]) -> list[Candidate]:
    candidates: list[Candidate] = []
    for b in blocks:
        txt = b.text or ""
        m = _PERSON_KEYWORD_LINE_RE.search(txt)
        if not m:
            continue
        value = normalize_text(m.group(1))
        # Cut after 4 tokens to avoid carrying trailing fields (CPF/RG/etc.).
        parts = [p for p in value.split(" ") if p]
        value = " ".join(parts[:4])
        if not _looks_like_person(value):
            continue
        candidates.append(
            Candidate(
                kind="funcionario",
                text=value,
                norm=normalize_for_match(value),
                block_id=b.id,
                page=b.page,
                block_index=b.index,
                source="keyword_line",
            )
        )
    return candidates


def _extract_company_candidates(blocks: list[Block]) -> list[Candidate]:
    candidates: list[Candidate] = []

    def looks_like_company(value: str) -> bool:
        v = normalize_text(value)
        if len(v) < 3 or len(v) > 140:
            return False
        # Allow small numbers (e.g., "CEI 1"), but reject identifiers (CNPJ/CPF) by long digit runs.
        if re.search(r"\d{8,}", v):
            return False
        v_norm = normalize_for_match(v)
        for bad in _COMPANY_STOP_PHRASES:
            if normalize_for_match(bad) in v_norm:
                return False
        # Require either a known prefix (CEI/EMEI/...) or 2+ tokens.
        parts = [p for p in v.split(" ") if p]
        if _COMPANY_PREFIX_RE.search(v):
            return True
        return len(parts) >= 2

    for b in blocks:
        txt = b.text or ""
        if not txt.strip():
            continue

        # Keyword line in the SAME block, e.g. "Empresa: CEI Erinice Siqueira"
        # Also supports "Empresa\nCEI Erinice Siqueira" and "Fantasia: ..."
        lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]
        if lines:
            first_norm = normalize_for_match(lines[0])
            if first_norm in _COMPANY_LABELS and len(lines) >= 2:
                value = normalize_text(lines[1])
                parts = [p for p in value.split(" ") if p]
                value = " ".join(parts[:12])
                if looks_like_company(value):
                    candidates.append(
                        Candidate(
                            kind="empresa",
                            text=value,
                            norm=normalize_for_match(value),
                            block_id=b.id,
                            page=b.page,
                            block_index=b.index,
                            source="label_next_line",
                        )
                    )

        m = _COMPANY_KEYWORD_LINE_RE.search(txt)
        if m and m.group(1).strip():
            value = normalize_text(m.group(1))
            # Keep at most ~12 tokens to avoid carrying trailing fields.
            parts = [p for p in value.split(" ") if p]
            value = " ".join(parts[:12])
            if looks_like_company(value):
                candidates.append(
                    Candidate(
                        kind="empresa",
                        text=value,
                        norm=normalize_for_match(value),
                        block_id=b.id,
                        page=b.page,
                        block_index=b.index,
                        source="keyword_line",
                    )
                )

        # Label in one block, value in the next block(s) on the same page.
        if normalize_for_match(txt) in _COMPANY_LABELS:
            for delta in (1, 2, 3):
                # blocks list is in stable order by index
                nxt_index = b.index + delta
                if nxt_index >= len(blocks):
                    break
                nb = blocks[nxt_index]
                if nb.page != b.page:
                    break
                val = normalize_text(nb.text)
                if not val:
                    continue
                parts = [p for p in val.split(" ") if p]
                val = " ".join(parts[:12])
                if looks_like_company(val):
                    candidates.append(
                        Candidate(
                            kind="empresa",
                            text=val,
                            norm=normalize_for_match(val),
                            block_id=nb.id,
                            page=nb.page,
                            block_index=nb.index,
                            source="label_next_block",
                        )
                    )
                    break

        if _COMPANY_HINT_RE.search(txt):
            value = normalize_text(txt)
            if len(value) < 4 or not looks_like_company(value):
                continue
            candidates.append(
                Candidate(
                    kind="empresa",
                    text=value,
                    norm=normalize_for_match(value),
                    block_id=b.id,
                    page=b.page,
                    block_index=b.index,
                    source="company_hint",
                )
            )

        # all-caps blocks are often headers / company names
        if len(txt) >= 8 and txt.isupper() and not any(ch.isdigit() for ch in txt):
            value = normalize_text(txt)
            if not looks_like_company(value):
                continue
            candidates.append(
                Candidate(
                    kind="empresa",
                    text=value,
                    norm=normalize_for_match(value),
                    block_id=b.id,
                    page=b.page,
                    block_index=b.index,
                    source="caps",
                )
            )

    return candidates


def _dedupe(cands: list[Candidate]) -> list[Candidate]:
    seen: set[tuple[str, str]] = set()
    out: list[Candidate] = []
    for c in cands:
        key = (c.kind, c.norm)
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out


def generate_candidates(blocks: list[Block], cfg: PipelineConfig) -> dict:
    spacy_ok = False
    spacy_error: str | None = None
    try:
        person = _extract_person_candidates_spacy(blocks, cfg=cfg)
        spacy_ok = True
    except Exception as exc:  # noqa: BLE001
        person = []
        spacy_ok = False
        spacy_error = type(exc).__name__

    person.extend(_extract_person_candidates_keyword_line(blocks))
    person.extend(_extract_person_candidates_fallback(blocks))
    company = _extract_company_candidates(blocks)

    person = _dedupe(person)[: cfg.max_candidates_per_type]
    company = _dedupe(company)[: cfg.max_candidates_per_type]

    return {
        "funcionarios": [{"text": c.text, "block_id": c.block_id, "page": c.page} for c in person],
        "empresas": [{"text": c.text, "block_id": c.block_id, "page": c.page} for c in company],
        "_internal": {"funcionarios": person, "empresas": company},
        "_meta": {"spacy_ok": spacy_ok, "spacy_error": spacy_error},
    }


