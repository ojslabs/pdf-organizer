"""PyMuPDF wrapper: render page thumbnails + merge selected pages into one PDF."""
from pathlib import Path

import fitz  # PyMuPDF

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


def merge_packet(pages, source_dir: Path, out_path: Path) -> int:
    """Assemble an ordered list of {src, page} into one PDF. Returns output byte size."""
    out = fitz.open()
    cache = {}
    for pg in pages:
        sid = pg["src"]
        if sid not in cache:
            cache[sid] = fitz.open(source_dir / f"{sid}.pdf")
        out.insert_pdf(cache[sid], from_page=pg["page"], to_page=pg["page"])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.save(out_path, garbage=4, deflate=True)
    out.close()
    for d in cache.values():
        d.close()
    return out_path.stat().st_size
