"""PDF engine: import, thumbnail/preview rendering, section merge with cover
sheets, master index generation, and exact size measurement.

All cover-sheet/master-index page composition lives in cover_sheet.py; this
file orchestrates the merge and provides the size-measurement primitives the
NIW UI uses to enforce the 12MB-per-file USCIS limit.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Iterable

import fitz  # PyMuPDF

import cover_sheet

THUMB_WIDTH = 220


# ---------------------------------------------------------------- import
def import_pdf(pdf_bytes: bytes, src_id: str, source_dir: Path, thumb_dir: Path):
    """Save uploaded PDF, render a per-page thumbnail. Returns (page_count, bytes)."""
    source_dir.mkdir(parents=True, exist_ok=True)
    thumb_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = source_dir / f"{src_id}.pdf"
    pdf_path.write_bytes(pdf_bytes)

    doc = fitz.open(pdf_path)
    page_count = doc.page_count
    for i in range(page_count):
        page = doc.load_page(i)
        zoom = THUMB_WIDTH / page.rect.width if page.rect.width else 1
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        pix.save(thumb_dir / f"{src_id}-{i}.png")
    doc.close()
    return page_count, len(pdf_bytes)


def render_preview(source_pdf: Path, page: int, out_path: Path, width: int = 1100) -> Path:
    """Render one source page at a larger size for the click-to-expand lightbox."""
    doc = fitz.open(source_pdf)
    pg = doc.load_page(page)
    zoom = width / pg.rect.width if pg.rect.width else 1
    pix = pg.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pix.save(out_path)
    doc.close()
    return out_path


# ---------------------------------------------------------------- section merge
def build_section_pdf(
    petitioner: str,
    section_name: str,
    exhibits_numbered: Iterable[tuple],
    source_dir: Path,
    target: Path,
) -> int:
    """
    Build one section's merged PDF (cover sheet + exhibit per exhibit in order).

    `exhibits_numbered` is an ordered iterable of tuples:
        (slot_name: str, exhibit_dict: dict, exhibit_number: int)

    Returns the resulting file size in bytes.
    """
    out = fitz.open()
    src_cache: dict[str, fitz.Document] = {}

    for slot_name, ex, n in exhibits_numbered:
        cover = cover_sheet.make_cover_sheet(
            exhibit_number=n,
            section_name=section_name,
            slot_name=slot_name,
            exhibit_label=ex.get("label") or "(untitled)",
            rationale=ex.get("rationale") or "",
            petitioner_name=petitioner,
        )
        out.insert_pdf(cover)
        cover.close()

        sid = ex["src_id"]
        if sid not in src_cache:
            src_cache[sid] = fitz.open(source_dir / f"{sid}.pdf")
        out.insert_pdf(src_cache[sid])

    target.parent.mkdir(parents=True, exist_ok=True)
    out.save(target, garbage=4, deflate=True)
    out.close()
    for d in src_cache.values():
        d.close()
    return target.stat().st_size


def measure_section_size(
    petitioner: str,
    section_name: str,
    exhibits_numbered: Iterable[tuple],
    source_dir: Path,
) -> int:
    """Build the section PDF to a temp file just to measure exact bytes. Returns size."""
    exhibits_numbered = list(exhibits_numbered)
    if not exhibits_numbered:
        return 0
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        return build_section_pdf(
            petitioner, section_name, exhibits_numbered, source_dir, tmp_path
        )
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass


# ---------------------------------------------------------------- master index
def build_master_index(petitioner: str, entries, target: Path) -> int:
    """Write the master exhibit index PDF. Returns file size."""
    doc = cover_sheet.make_master_index(petitioner_name=petitioner, entries=entries)
    target.parent.mkdir(parents=True, exist_ok=True)
    doc.save(target, garbage=4, deflate=True)
    doc.close()
    return target.stat().st_size


# ---------------------------------------------------------------- exhibit pages
def exhibit_page_count(source_pdf: Path) -> int:
    """How many pages this source PDF has (used for index page-number arithmetic)."""
    with fitz.open(source_pdf) as d:
        return d.page_count
