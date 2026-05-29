"""PyMuPDF wrapper: render page thumbnails, build per-packet merged PDFs with
exhibit cover sheets prepended, generate the master exhibit index, and measure
exact merged byte size for the 12MB-per-file governor.
"""
import tempfile
from pathlib import Path

import fitz  # PyMuPDF

import cover_sheet

THUMB_WIDTH = 220  # px wide; capped for speed + small cache


def import_pdf(pdf_bytes: bytes, src_id: str, source_dir: Path, thumb_dir: Path):
    """Save an uploaded PDF, render a thumbnail per page. Returns (page_count, byte_size)."""
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
    """Render one page at a larger size for the click-to-expand lightbox. Cached to disk."""
    doc = fitz.open(source_pdf)
    pg = doc.load_page(page)
    zoom = width / pg.rect.width if pg.rect.width else 1
    pix = pg.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pix.save(out_path)
    doc.close()
    return out_path


def build_packet_pdf(
    petitioner: str,
    tab_name: str,
    exhibits_numbered,
    source_dir: Path,
    target: Path,
) -> int:
    """Build one packet's merged PDF: cover-sheet + exhibit per exhibit in order.

    exhibits_numbered: ordered iterable of (exhibit_dict, exhibit_number).
    Returns output file size in bytes.
    """
    out = fitz.open()
    cache: dict = {}
    for ex, n in exhibits_numbered:
        cover = cover_sheet.make_cover_sheet(
            exhibit_number=n,
            tab_name=tab_name,
            exhibit_title=ex.get("title") or "(untitled)",
            cover_paragraph=ex.get("cover_paragraph") or "",
            petitioner_name=petitioner,
        )
        out.insert_pdf(cover)
        cover.close()
        sid = ex["src_id"]
        if sid not in cache:
            cache[sid] = fitz.open(source_dir / f"{sid}.pdf")
        out.insert_pdf(cache[sid])

    target.parent.mkdir(parents=True, exist_ok=True)
    out.save(target, garbage=4, deflate=True)
    out.close()
    for d in cache.values():
        d.close()
    return target.stat().st_size


def measure_packet_size(
    petitioner: str,
    tab_name: str,
    exhibits_numbered,
    source_dir: Path,
) -> int:
    """Build packet to a temp file just to measure exact bytes. Returns size."""
    exhibits_numbered = list(exhibits_numbered)
    if not exhibits_numbered:
        return 0
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        return build_packet_pdf(
            petitioner, tab_name, exhibits_numbered, source_dir, tmp_path
        )
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass


def build_master_index(petitioner: str, entries, target: Path) -> int:
    doc = cover_sheet.make_master_index(petitioner_name=petitioner, entries=entries)
    target.parent.mkdir(parents=True, exist_ok=True)
    doc.save(target, garbage=4, deflate=True)
    doc.close()
    return target.stat().st_size


def exhibit_page_count(source_pdf: Path) -> int:
    with fitz.open(source_pdf) as d:
        return d.page_count
