"""Generate exhibit cover sheets and the master exhibit index PDF.

Cover sheet (one page per exhibit, prepended on merge):
  EXHIBIT N
  Section / Slot
  Exhibit title
  Rationale paragraph
  Petitioner & footer

Master index PDF: lists every exhibit across the petition with the file (section
output) and page on which it begins, so the officer can navigate the upload set.
"""
from __future__ import annotations

from datetime import date
from typing import Iterable

import fitz

PAGE_W, PAGE_H = 612, 792  # US Letter in points
MARGIN = 72
INNER_W = PAGE_W - 2 * MARGIN


def _new_doc() -> fitz.Document:
    return fitz.open()


def _add_page(doc: fitz.Document):
    return doc.new_page(width=PAGE_W, height=PAGE_H)


def _draw_text(page, x, y, text, size=11, font="helv", bold=False, color=(0, 0, 0)):
    page.insert_text(
        (x, y),
        text,
        fontsize=size,
        fontname=("hebo" if bold else font),
        color=color,
    )


def _draw_textbox(page, rect, text, size=11, font="helv", align=0, color=(0, 0, 0)):
    """Wraps text inside rect. Returns remaining (negative if fully fit)."""
    return page.insert_textbox(
        rect, text, fontsize=size, fontname=font, align=align, color=color
    )


def make_cover_sheet(
    exhibit_number: int,
    section_name: str,
    slot_name: str,
    exhibit_label: str,
    rationale: str,
    petitioner_name: str = "",
) -> fitz.Document:
    """Return a one-page fitz.Document for an exhibit cover sheet."""
    doc = _new_doc()
    page = _add_page(doc)

    # accent strip
    page.draw_rect(
        fitz.Rect(0, 0, PAGE_W, 8), color=(0, 0, 0), fill=(0, 0, 0)
    )

    # "EXHIBIT N"
    y = MARGIN + 40
    _draw_text(page, MARGIN, y, f"EXHIBIT {exhibit_number}", size=36, bold=True)

    # Section / slot path
    y += 36
    _draw_textbox(
        page,
        fitz.Rect(MARGIN, y, MARGIN + INNER_W, y + 30),
        f"{section_name}  ·  {slot_name}",
        size=11,
        color=(0.4, 0.4, 0.4),
    )

    # Title (exhibit label)
    y += 30
    _draw_textbox(
        page,
        fitz.Rect(MARGIN, y, MARGIN + INNER_W, y + 80),
        exhibit_label,
        size=20,
        font="hebo",
    )

    # Divider
    y += 80
    page.draw_line((MARGIN, y), (MARGIN + INNER_W, y), color=(0.8, 0.8, 0.8), width=0.7)

    # Rationale paragraph
    y += 24
    rect = fitz.Rect(MARGIN, y, MARGIN + INNER_W, PAGE_H - MARGIN - 60)
    _draw_textbox(page, rect, rationale, size=12, color=(0.15, 0.15, 0.15))

    # Footer
    foot = (
        f"{petitioner_name + '  ·  ' if petitioner_name else ''}"
        f"EB-2 National Interest Waiver Petition  ·  Prepared {date.today():%B %Y}"
    )
    _draw_textbox(
        page,
        fitz.Rect(MARGIN, PAGE_H - MARGIN - 30, MARGIN + INNER_W, PAGE_H - MARGIN),
        foot,
        size=9,
        color=(0.5, 0.5, 0.5),
    )
    return doc


def make_master_index(
    petitioner_name: str,
    entries: Iterable[dict],
) -> fitz.Document:
    """
    Build the master exhibit index PDF.

    `entries` is an ordered iterable of dicts:
        {"number": int, "label": str, "section": str, "output_file": str, "page": int}
    """
    entries = list(entries)
    doc = _new_doc()
    page = _add_page(doc)

    # accent strip
    page.draw_rect(fitz.Rect(0, 0, PAGE_W, 8), color=(0, 0, 0), fill=(0, 0, 0))

    y = MARGIN + 30
    _draw_text(page, MARGIN, y, "MASTER EXHIBIT INDEX", size=22, bold=True)
    y += 26
    sub = f"{petitioner_name}  ·  EB-2 National Interest Waiver" if petitioner_name else "EB-2 National Interest Waiver"
    _draw_text(page, MARGIN, y, sub, size=11, color=(0.4, 0.4, 0.4))
    y += 24
    page.draw_line((MARGIN, y), (MARGIN + INNER_W, y), color=(0, 0, 0), width=0.9)
    y += 14

    # Column headers
    col_x = {
        "num": MARGIN,
        "label": MARGIN + 60,
        "section": MARGIN + INNER_W - 230,
        "file": MARGIN + INNER_W - 110,
    }
    _draw_text(page, col_x["num"], y, "#", size=10, bold=True, color=(0.3, 0.3, 0.3))
    _draw_text(page, col_x["label"], y, "Exhibit", size=10, bold=True, color=(0.3, 0.3, 0.3))
    _draw_text(page, col_x["section"], y, "Section", size=10, bold=True, color=(0.3, 0.3, 0.3))
    _draw_text(page, col_x["file"], y, "File · pg", size=10, bold=True, color=(0.3, 0.3, 0.3))
    y += 14
    page.draw_line((MARGIN, y), (MARGIN + INNER_W, y), color=(0.7, 0.7, 0.7), width=0.5)
    y += 10

    line_h = 16
    for entry in entries:
        if y > PAGE_H - MARGIN - line_h:
            page = _add_page(doc)
            y = MARGIN
        _draw_text(page, col_x["num"], y, str(entry["number"]), size=10)
        _draw_textbox(
            page,
            fitz.Rect(col_x["label"], y - 10, col_x["section"] - 6, y + 6),
            entry["label"],
            size=10,
        )
        _draw_textbox(
            page,
            fitz.Rect(col_x["section"], y - 10, col_x["file"] - 6, y + 6),
            entry["section"],
            size=9,
            color=(0.4, 0.4, 0.4),
        )
        _draw_textbox(
            page,
            fitz.Rect(col_x["file"], y - 10, MARGIN + INNER_W, y + 6),
            f"{entry['output_file']} · {entry['page']}",
            size=9,
            color=(0.4, 0.4, 0.4),
        )
        y += line_h

    return doc
