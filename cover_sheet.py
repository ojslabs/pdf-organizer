"""Generate exhibit cover sheets and the master exhibit index PDF.

Cover sheet (one page per exhibit, prepended on merge):
  EXHIBIT N
  Tab name
  Exhibit title
  Cover paragraph
  Petitioner & footer

Master index PDF: lists every exhibit across the petition with the file
(packet output name) and page on which it begins, so the officer can navigate
the upload set.
"""
from __future__ import annotations

from datetime import date
from typing import Iterable

import fitz

PAGE_W, PAGE_H = 612, 792  # US Letter
MARGIN = 72
INNER_W = PAGE_W - 2 * MARGIN


def _new_doc() -> fitz.Document:
    return fitz.open()


def _add_page(doc: fitz.Document):
    return doc.new_page(width=PAGE_W, height=PAGE_H)


def _draw_text(page, x, y, text, size=11, font="helv", bold=False, color=(0, 0, 0)):
    page.insert_text(
        (x, y), text,
        fontsize=size, fontname=("hebo" if bold else font), color=color,
    )


def _draw_textbox(page, rect, text, size=11, font="helv", align=0, color=(0, 0, 0)):
    return page.insert_textbox(
        rect, text, fontsize=size, fontname=font, align=align, color=color,
    )


def make_cover_sheet(
    exhibit_number: int,
    tab_name: str,
    exhibit_title: str,
    cover_paragraph: str,
    petitioner_name: str = "",
) -> fitz.Document:
    doc = _new_doc()
    page = _add_page(doc)

    # accent strip
    page.draw_rect(fitz.Rect(0, 0, PAGE_W, 8), color=(0, 0, 0), fill=(0, 0, 0))

    y = MARGIN + 40
    _draw_text(page, MARGIN, y, f"EXHIBIT {exhibit_number}", size=36, bold=True)

    y += 36
    _draw_textbox(
        page, fitz.Rect(MARGIN, y, MARGIN + INNER_W, y + 30),
        tab_name, size=11, color=(0.4, 0.4, 0.4),
    )

    y += 30
    _draw_textbox(
        page, fitz.Rect(MARGIN, y, MARGIN + INNER_W, y + 80),
        exhibit_title, size=20, font="hebo",
    )

    y += 80
    page.draw_line((MARGIN, y), (MARGIN + INNER_W, y), color=(0.8, 0.8, 0.8), width=0.7)

    y += 24
    rect = fitz.Rect(MARGIN, y, MARGIN + INNER_W, PAGE_H - MARGIN - 60)
    _draw_textbox(page, rect, cover_paragraph or "", size=12, color=(0.15, 0.15, 0.15))

    foot = (
        f"{petitioner_name + '  ·  ' if petitioner_name else ''}"
        f"EB-2 National Interest Waiver Petition  ·  Prepared {date.today():%B %Y}"
    )
    _draw_textbox(
        page, fitz.Rect(MARGIN, PAGE_H - MARGIN - 30, MARGIN + INNER_W, PAGE_H - MARGIN),
        foot, size=9, color=(0.5, 0.5, 0.5),
    )
    return doc


def make_master_index(petitioner_name: str, entries: Iterable[dict]) -> fitz.Document:
    """
    `entries`: ordered iterable of dicts:
        {"number": int, "title": str, "tab": str, "output_file": str, "page": int}
    """
    entries = list(entries)
    doc = _new_doc()
    page = _add_page(doc)

    page.draw_rect(fitz.Rect(0, 0, PAGE_W, 8), color=(0, 0, 0), fill=(0, 0, 0))

    y = MARGIN + 30
    _draw_text(page, MARGIN, y, "MASTER EXHIBIT INDEX", size=22, bold=True)
    y += 26
    sub = f"{petitioner_name}  ·  EB-2 National Interest Waiver" if petitioner_name else "EB-2 National Interest Waiver"
    _draw_text(page, MARGIN, y, sub, size=11, color=(0.4, 0.4, 0.4))
    y += 24
    page.draw_line((MARGIN, y), (MARGIN + INNER_W, y), color=(0, 0, 0), width=0.9)
    y += 14

    col_x = {
        "num": MARGIN,
        "title": MARGIN + 60,
        "tab": MARGIN + INNER_W - 240,
        "file": MARGIN + INNER_W - 110,
    }
    _draw_text(page, col_x["num"], y, "#", size=10, bold=True, color=(0.3, 0.3, 0.3))
    _draw_text(page, col_x["title"], y, "Exhibit", size=10, bold=True, color=(0.3, 0.3, 0.3))
    _draw_text(page, col_x["tab"], y, "Tab", size=10, bold=True, color=(0.3, 0.3, 0.3))
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
            page, fitz.Rect(col_x["title"], y - 10, col_x["tab"] - 6, y + 6),
            entry["title"], size=10,
        )
        _draw_textbox(
            page, fitz.Rect(col_x["tab"], y - 10, col_x["file"] - 6, y + 6),
            entry["tab"], size=9, color=(0.4, 0.4, 0.4),
        )
        _draw_textbox(
            page, fitz.Rect(col_x["file"], y - 10, MARGIN + INNER_W, y + 6),
            f"{entry['output_file']} · {entry['page']}", size=9, color=(0.4, 0.4, 0.4),
        )
        y += line_h

    return doc
