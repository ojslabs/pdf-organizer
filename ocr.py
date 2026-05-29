"""PDF text extraction with Tesseract OCR fallback.

extract_or_ocr(path) -> (text, used_ocr)
  1. Tries PyMuPDF text extraction (fast, lossless for text-based PDFs).
  2. If extracted text is shorter than the threshold (image-only PDF), renders
     up to MAX_OCR_PAGES pages to PNG and feeds them to Tesseract via
     pytesseract.
  3. Returns whichever yielded more text, plus a flag indicating OCR was used.

Tesseract is an external system binary. If it's not installed the OCR path
quietly fails and the caller gets back whatever PyMuPDF could extract (often
nothing for scanned docs). Install with:
    macOS:  brew install tesseract
    Ubuntu: sudo apt install tesseract-ocr
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import fitz

MAX_CHARS = 8000          # cap on text returned to the LLM
MIN_TEXT_LEN = 100        # below this, try OCR
MAX_OCR_PAGES = 3         # OCR is slow; cap pages scanned


def extract_pdf_text(path: Path) -> str:
    """Plain text extraction via PyMuPDF."""
    parts: list[str] = []
    total = 0
    with fitz.open(path) as doc:
        for page in doc:
            t = page.get_text("text")
            parts.append(t)
            total += len(t)
            if total > MAX_CHARS:
                break
    return "\n".join(parts).strip()


def ocr_pdf(path: Path, max_pages: int = MAX_OCR_PAGES) -> str:
    """Render up to max_pages and run Tesseract on each. Raises if Tesseract missing."""
    import pytesseract  # imported lazily so app loads even if pytesseract is broken

    out: list[str] = []
    with fitz.open(path) as doc:
        for i in range(min(max_pages, doc.page_count)):
            page = doc.load_page(i)
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # ~150dpi for legible OCR
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp_path = Path(tmp.name)
            try:
                pix.save(tmp_path)
                out.append(pytesseract.image_to_string(str(tmp_path)))
            finally:
                tmp_path.unlink(missing_ok=True)
    return "\n".join(out).strip()


def extract_or_ocr(path: Path) -> tuple[str, bool]:
    """Best-effort text extraction. Returns (text, used_ocr)."""
    text = extract_pdf_text(path)
    if len(text) >= MIN_TEXT_LEN:
        return text[:MAX_CHARS], False
    # text too short — likely scanned. Try OCR.
    try:
        ocr_text = ocr_pdf(path)
        if len(ocr_text) > len(text):
            return ocr_text[:MAX_CHARS], True
    except Exception:
        pass
    return text[:MAX_CHARS], False
