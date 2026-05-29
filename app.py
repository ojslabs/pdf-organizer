"""NIW Petition Builder v2 — TOC-driven, AI-assisted exhibit assembler.

Phase 1: skeleton — loads project, renders Table of Contents with seven empty
tabs (A–G), each with one default packet, plus an API-status badge driven by
the Anthropic connection-test. Upload + AI pipeline come in Phase 2.
"""
from __future__ import annotations

from pathlib import Path

import dotenv

# load .env BEFORE importing modules that read env vars
dotenv.load_dotenv(Path(__file__).parent / ".env")

import asyncio  # noqa: E402

from nicegui import app, events, ui  # noqa: E402

import ai  # noqa: E402
import niw_template  # noqa: E402
import ocr  # noqa: E402
import pdf_engine  # noqa: E402
import storage  # noqa: E402


# ---------------------------------------------------------------- app state
S = {
    "proj": None,
    "ai_status": None,    # (ok: bool, msg: str) | None
    "sizes": {},          # packet_id -> bytes | None (computing) | -1 (empty)
}
_drag = {"type": None, "id": None}     # in-flight drag: type=exhibit|packet

storage.PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
app.add_static_files("/pdfdata", str(storage.PROJECTS_DIR))


# ---------------------------------------------------------------- helpers
def save():
    storage.save(S["proj"])


def set_project_name(value):
    S["proj"]["name"] = value or "Untitled Petition"
    save()


def set_petitioner(value):
    S["proj"]["petitioner"] = value or ""
    save()


def switch_project(slug):
    S["proj"] = storage.load(slug)
    S["sizes"] = {}
    schedule_all_recompute()
    view.refresh()


# ---------------------------------------------------------------- helpers
def hsize(n) -> str:
    if n is None:
        return "—"
    if n < 0:
        return "empty"
    n = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def section_limit_bytes(proj) -> int:
    return int(proj.get("size_limit_mb", 12)) * 1024 * 1024


def exhibits_numbered_in_packet(proj, packet):
    """Return [(exhibit_dict, exhibit_number), ...] in TOC order."""
    numbering = exhibit_numbering(proj)
    return [(ex, numbering[ex["id"]]) for ex in packet["exhibits"]]


# ---------------------------------------------------------------- background sizing
def _measure_packet_blocking(packet_id):
    proj = S["proj"]
    tab, pkt = storage.find_packet(proj, packet_id)
    if pkt is None:
        return 0
    items = exhibits_numbered_in_packet(proj, pkt)
    if not items:
        return -1
    return pdf_engine.measure_packet_size(
        proj.get("petitioner", ""),
        tab["name"],
        items,
        storage.source_dir(proj["slug"]),
    )


async def recompute_packet_size(packet_id):
    S["sizes"][packet_id] = None
    view.refresh()
    try:
        sz = await asyncio.to_thread(_measure_packet_blocking, packet_id)
        S["sizes"][packet_id] = sz
    except Exception as e:
        S["sizes"][packet_id] = -1
        ui.notify(f"Size compute failed: {e}", type="negative")
    view.refresh()


def schedule_packet_recompute(packet_id):
    from nicegui import background_tasks
    background_tasks.create(recompute_packet_size(packet_id))


def schedule_all_recompute():
    proj = S.get("proj")
    if proj is None:
        return
    for tab in proj["tabs"]:
        for pkt in tab["packets"]:
            schedule_packet_recompute(pkt["id"])


# ---------------------------------------------------------------- mutations
def add_packet(tab_id):
    proj = S["proj"]
    tab = storage.find_tab(proj, tab_id)
    if tab is None:
        return
    n = len(tab["packets"]) + 1
    tab["packets"].append(
        {"id": storage.new_id(), "name": f"{tab['letter']}{n}", "exhibits": []}
    )
    save()
    view.refresh()


def delete_packet(packet_id):
    proj = S["proj"]
    tab, pkt = storage.find_packet(proj, packet_id)
    if tab is None or len(tab["packets"]) <= 1:
        ui.notify("Each tab must keep at least one packet.", type="warning")
        return
    tab["packets"] = [p for p in tab["packets"] if p["id"] != packet_id]
    save()
    view.refresh()


def rename_packet(packet_id, value):
    proj = S["proj"]
    _tab, pkt = storage.find_packet(proj, packet_id)
    if pkt is None:
        return
    pkt["name"] = (value or pkt["name"]).strip()
    save()


def move_packet(packet_id, delta):
    """Reorder a packet up/down within its tab (delta = -1 or +1)."""
    proj = S["proj"]
    tab, pkt = storage.find_packet(proj, packet_id)
    if pkt is None:
        return
    i = tab["packets"].index(pkt)
    j = max(0, min(len(tab["packets"]) - 1, i + delta))
    if i == j:
        return
    tab["packets"].pop(i)
    tab["packets"].insert(j, pkt)
    save()
    view.refresh()


def set_drag_exhibit(exhibit_id):
    _drag["type"], _drag["id"] = "exhibit", exhibit_id


def drop_on_exhibit(target_exhibit_id):
    """Drop an exhibit before the target exhibit."""
    if _drag["type"] != "exhibit" or _drag["id"] is None:
        _drag["id"] = None
        return
    proj = S["proj"]
    eid = _drag["id"]
    src_tab, src_pkt, src_ex = storage.find_exhibit(proj, eid)
    dst_tab, dst_pkt, dst_ex = storage.find_exhibit(proj, target_exhibit_id)
    if src_ex is None or dst_ex is None or src_ex is dst_ex:
        _drag["id"] = None
        return
    src_idx = src_pkt["exhibits"].index(src_ex)
    src_pkt["exhibits"].pop(src_idx)
    dst_idx = dst_pkt["exhibits"].index(dst_ex)
    if src_pkt is dst_pkt and src_idx < dst_idx:
        dst_idx -= 1
    dst_pkt["exhibits"].insert(dst_idx, src_ex)
    _drag["id"] = None
    save()
    schedule_packet_recompute(src_pkt["id"])
    if dst_pkt["id"] != src_pkt["id"]:
        schedule_packet_recompute(dst_pkt["id"])
    view.refresh()


def drop_on_packet(target_packet_id):
    """Drop an exhibit into a packet (append)."""
    if _drag["type"] != "exhibit" or _drag["id"] is None:
        _drag["id"] = None
        return
    proj = S["proj"]
    eid = _drag["id"]
    src_tab, src_pkt, src_ex = storage.find_exhibit(proj, eid)
    dst_tab, dst_pkt = storage.find_packet(proj, target_packet_id)
    if src_ex is None or dst_pkt is None:
        _drag["id"] = None
        return
    src_pkt["exhibits"].remove(src_ex)
    dst_pkt["exhibits"].append(src_ex)
    _drag["id"] = None
    save()
    schedule_packet_recompute(src_pkt["id"])
    if dst_pkt["id"] != src_pkt["id"]:
        schedule_packet_recompute(dst_pkt["id"])
    view.refresh()


def delete_exhibit(exhibit_id):
    proj = S["proj"]
    tab, pkt, ex = storage.find_exhibit(proj, exhibit_id)
    if ex is None:
        return
    pkt["exhibits"] = [x for x in pkt["exhibits"] if x["id"] != exhibit_id]
    # delete source files if no other exhibit references this src
    sid = ex["src_id"]
    still_used = any(
        x["src_id"] == sid for t in proj["tabs"] for p in t["packets"] for x in p["exhibits"]
    )
    if not still_used:
        proj["sources"].pop(sid, None)
        (storage.source_dir(proj["slug"]) / f"{sid}.pdf").unlink(missing_ok=True)
        for d in (storage.thumb_dir(proj["slug"]), storage.preview_dir(proj["slug"])):
            for f in d.glob(f"{sid}-*.png"):
                f.unlink(missing_ok=True)
    save()
    schedule_packet_recompute(pkt["id"])
    view.refresh()


# ---------------------------------------------------------------- merge / export
def packet_output_name(tab, pkt) -> str:
    return f"{pkt['name']}_{storage.slugify(tab['name'])}.pdf"


def merge_packet(packet_id):
    proj = S["proj"]
    tab, pkt = storage.find_packet(proj, packet_id)
    if pkt is None or not pkt["exhibits"]:
        ui.notify("Packet is empty.", type="warning")
        return
    fname = packet_output_name(tab, pkt)
    target = storage.output_dir(proj["slug"]) / fname
    items = exhibits_numbered_in_packet(proj, pkt)
    size = pdf_engine.build_packet_pdf(
        proj.get("petitioner", ""), tab["name"], items,
        storage.source_dir(proj["slug"]), target,
    )
    S["sizes"][packet_id] = size
    limit = section_limit_bytes(proj)
    if size > limit:
        ui.notify(f"Merged {fname} → {hsize(size)} — OVER 12MB.", type="warning")
    else:
        ui.notify(f"Merged {fname} → {hsize(size)}", type="positive")
    ui.download(f"/pdfdata/{proj['slug']}/output/{fname}")
    view.refresh()


def build_master_index():
    proj = S["proj"]
    numbering = exhibit_numbering(proj)
    if not numbering:
        ui.notify("No exhibits yet.", type="warning")
        return
    entries = []
    for tab in proj["tabs"]:
        for pkt in tab["packets"]:
            fname = packet_output_name(tab, pkt)
            page = 1
            for ex in pkt["exhibits"]:
                entries.append(
                    {
                        "number": numbering[ex["id"]],
                        "title": ex.get("title") or "(untitled)",
                        "tab": f"{tab['letter']} — {tab['name']}",
                        "output_file": fname,
                        "page": page,
                    }
                )
                src_path = storage.source_dir(proj["slug"]) / f"{ex['src_id']}.pdf"
                page += 1 + pdf_engine.exhibit_page_count(src_path)
    target = storage.output_dir(proj["slug"]) / "00_Master_Index.pdf"
    pdf_engine.build_master_index(proj.get("petitioner", ""), entries, target)
    ui.notify(f"Master Index → 00_Master_Index.pdf ({len(entries)} exhibits)", type="positive")
    ui.download(f"/pdfdata/{proj['slug']}/output/00_Master_Index.pdf")


def export_all():
    proj = S["proj"]
    numbering = exhibit_numbering(proj)
    if not numbering:
        ui.notify("No exhibits yet — nothing to export.", type="warning")
        return
    built, over = [], []
    for tab in proj["tabs"]:
        for pkt in tab["packets"]:
            if not pkt["exhibits"]:
                continue
            fname = packet_output_name(tab, pkt)
            target = storage.output_dir(proj["slug"]) / fname
            items = exhibits_numbered_in_packet(proj, pkt)
            size = pdf_engine.build_packet_pdf(
                proj.get("petitioner", ""), tab["name"], items,
                storage.source_dir(proj["slug"]), target,
            )
            S["sizes"][pkt["id"]] = size
            built.append((fname, size))
            if size > section_limit_bytes(proj):
                over.append(fname)
    build_master_index()
    msg = f"Exported {len(built)} files to projects/{proj['slug']}/output/."
    if over:
        ui.notify(msg + f" ⚠ Over 12MB: {', '.join(over)}", type="warning")
    else:
        ui.notify(msg, type="positive")
    view.refresh()


# ---------------------------------------------------------------- AI upload pipeline
async def handle_upload(e: events.UploadEventArguments):
    """Per-file upload handler: imports the PDF, optionally runs AI classify,
    then opens a review dialog for the user to accept/edit the metadata."""
    proj = S["proj"]
    data = await e.file.read()
    name = e.file.name
    src_id = storage.new_id()
    page_count, nbytes = await asyncio.to_thread(
        pdf_engine.import_pdf,
        data, src_id,
        storage.source_dir(proj["slug"]), storage.thumb_dir(proj["slug"]),
    )
    proj["sources"][src_id] = {"filename": name, "page_count": page_count, "bytes": nbytes}
    save()

    # extract text (with OCR fallback) + classify if we can
    pdf_path = storage.source_dir(proj["slug"]) / f"{src_id}.pdf"
    text, used_ocr = await asyncio.to_thread(ocr.extract_or_ocr, pdf_path)
    result = None
    ai_error = None
    if ai.have_key() and text:
        try:
            result = await asyncio.to_thread(ai.classify_document, text, name)
        except Exception as ex:
            ai_error = f"{type(ex).__name__}: {ex}"

    if result is None:
        result = {
            "title": name.removesuffix(".pdf").replace("_", " ").replace("-", " ").strip() or "Untitled",
            "summary": "",
            "suggested_tab": "A",
            "cover_paragraph": "",
        }

    open_review_dialog(
        src_id=src_id, filename=name, page_count=page_count,
        result=result, used_ocr=used_ocr, ai_error=ai_error, text_present=bool(text),
    )


def open_review_dialog(src_id, filename, page_count, result, used_ocr, ai_error, text_present):
    """Review/edit AI suggestions before landing the exhibit."""
    proj = S["proj"]
    tab_options = {t["letter"]: f"{t['letter']} — {t['name']}" for t in proj["tabs"]}

    with ui.dialog().props("persistent") as dialog, ui.card().classes("p-5 gap-3 min-w-[40rem] max-w-[48rem]"):
        ui.label(f"Review: {filename}").classes("text-lg font-semibold text-black")
        # status row
        bits = [f"{page_count} page{'s' if page_count != 1 else ''}"]
        if used_ocr:
            bits.append("OCR used")
        if ai_error:
            bits.append(f"AI failed ({ai_error})")
        elif not ai.have_key():
            bits.append("AI off (no API key)")
        elif not text_present:
            bits.append("No text extracted — AI skipped")
        else:
            bits.append("AI classified")
        ui.label(" · ".join(bits)).classes("text-xs text-gray-500")

        title_in = ui.input("Exhibit title", value=result["title"]).classes("w-full")
        tab_in = ui.select(
            options=tab_options,
            value=result["suggested_tab"] if result["suggested_tab"] in tab_options else "A",
            label="Tab",
        ).props("dense outlined").classes("w-full")
        cover_in = ui.textarea(
            "Cover-sheet paragraph (printed before this exhibit on merge)",
            value=result["cover_paragraph"],
        ).props("autogrow").classes("w-full")
        if result.get("summary"):
            with ui.expansion("AI summary (internal)").classes("w-full text-xs"):
                ui.label(result["summary"]).classes("text-xs text-gray-600")

        def cancel():
            # discard source files
            proj["sources"].pop(src_id, None)
            (storage.source_dir(proj["slug"]) / f"{src_id}.pdf").unlink(missing_ok=True)
            for d in (storage.thumb_dir(proj["slug"]), storage.preview_dir(proj["slug"])):
                for f in d.glob(f"{src_id}-*.png"):
                    f.unlink(missing_ok=True)
            save()
            dialog.close()
            view.refresh()
            ui.notify(f"Discarded {filename}", type="info")

        def accept():
            tab_letter = tab_in.value or "A"
            target_tab = next((t for t in proj["tabs"] if t["letter"] == tab_letter), proj["tabs"][0])
            target_pkt = target_tab["packets"][-1]  # land in last packet of that tab
            target_pkt["exhibits"].append(
                {
                    "id": storage.new_id(),
                    "src_id": src_id,
                    "title": (title_in.value or "Untitled").strip(),
                    "summary": result.get("summary", ""),
                    "cover_paragraph": (cover_in.value or "").strip(),
                    "ai_meta": {
                        "suggested_tab": result.get("suggested_tab", ""),
                        "ai_error": ai_error or "",
                        "used_ocr": used_ocr,
                    },
                }
            )
            save()
            dialog.close()
            schedule_packet_recompute(target_pkt["id"])
            view.refresh()
            ui.notify(f"Added {filename} to {target_tab['letter']}", type="positive")

        with ui.row().classes("w-full justify-end gap-2 pt-2"):
            ui.button("Discard", on_click=cancel).props("flat color=red")
            ui.button("Add to petition", on_click=accept).props("color=dark")
    dialog.open()


# ---------------------------------------------------------------- new-project dialog
def create_project_dialog():
    with ui.dialog() as dialog, ui.card().classes("p-6 gap-3 min-w-80"):
        ui.label("New NIW petition").classes("text-lg font-semibold text-black")
        name = ui.input("Project name", placeholder="e.g. Sarah Strong NIW").classes("w-full")
        petitioner = ui.input("Petitioner full name", placeholder="e.g. Sarah Strong").classes("w-full")
        with ui.row().classes("w-full justify-end gap-2"):
            ui.button("Cancel", on_click=dialog.close).props("flat")
            ui.button(
                "Create",
                on_click=lambda: _create_and_close(name.value or "Untitled", petitioner.value or "", dialog),
            ).props("color=dark")
    dialog.open()


def _create_and_close(name, petitioner, dialog):
    S["proj"] = storage.new_project(name, petitioner)
    dialog.close()
    view.refresh()


# ---------------------------------------------------------------- API status
async def refresh_api_status():
    ok, msg = await __import__("asyncio").to_thread(ai.connection_test)
    S["ai_status"] = (ok, msg)
    view.refresh()


# ---------------------------------------------------------------- UI
@ui.refreshable
def view():
    proj = S["proj"]
    if proj is None:
        return

    # ---------- top bar
    with ui.row().classes("w-full items-center gap-4 px-6 py-3 bg-black text-white shadow-md"):
        ui.icon("description").classes("text-3xl text-white")
        with ui.column().classes("gap-0"):
            ui.label("NIW Petition Builder").classes("text-xl font-bold leading-tight")
            ui.label("EB-2 National Interest Waiver · I-140 · v2 (AI-assisted)").classes(
                "text-[10px] text-gray-400 leading-tight"
            )

        ui.element("div").classes("w-4")
        projects = storage.list_projects()
        ui.select(
            options={s: n for s, n in projects},
            value=proj["slug"],
            on_change=lambda e: switch_project(e.value),
        ).props("dark dense outlined").classes("min-w-48")
        ui.button(icon="add", on_click=create_project_dialog).props(
            "flat round dense color=white"
        ).tooltip("New petition")

        ui.space()

        ui.button("Master Index", icon="list_alt", on_click=build_master_index).props(
            "color=dark dense"
        ).tooltip("Generate the master exhibit index PDF")
        ui.button("Export All", icon="folder_zip", on_click=export_all).props(
            "color=dark dense"
        ).tooltip("Build all packet PDFs + master index")

        # API status badge
        status = S.get("ai_status")
        if status is None:
            api_color, api_label, api_tip = "text-gray-300", "API: …", "Checking Anthropic API"
        elif status[0]:
            api_color, api_label, api_tip = "text-emerald-400", "API: connected", status[1]
        else:
            api_color, api_label, api_tip = "text-red-400", "API: not connected", status[1]
        with ui.row().classes("items-center gap-1 bg-neutral-800 rounded-lg px-3 py-1").tooltip(api_tip):
            ui.icon("bolt").classes(api_color)
            ui.label(api_label).classes(f"font-semibold {api_color} text-sm")

    # ---------- identity row
    with ui.row().classes("w-full items-center gap-4 px-6 pt-4"):
        ui.input(value=proj["name"], on_change=lambda e: set_project_name(e.value)).props(
            "borderless"
        ).classes("text-2xl font-bold")
        ui.space()
        with ui.row().classes("items-center gap-2"):
            ui.label("Petitioner:").classes("text-xs text-gray-500")
            ui.input(
                value=proj.get("petitioner", ""), on_change=lambda e: set_petitioner(e.value)
            ).props("dense outlined").classes("min-w-56")

    # ---------- compliance summary
    render_compliance_summary(proj)

    # ---------- TABLE OF CONTENTS
    with ui.column().classes("w-full px-6 pt-6 pb-2 gap-2"):
        ui.label("TABLE OF CONTENTS").classes("text-xs font-bold text-gray-400 tracking-widest")

    # ---------- upload card (AI processes new uploads)
    with ui.column().classes("w-full px-6 pb-4"):
        with ui.card().classes("w-full bg-white border-2 border-dashed border-gray-300 rounded-xl p-4"):
            with ui.row().classes("w-full items-center gap-3"):
                ui.icon("cloud_upload").classes("text-2xl text-gray-400")
                with ui.column().classes("grow gap-0"):
                    ui.label("Upload documents — AI classifies into the right tab").classes(
                        "font-semibold text-black"
                    )
                    api_hint = "" if ai.have_key() else "No API key — uploads land but you'll title them manually. "
                    ui.label(api_hint + "Drop one or many PDFs.").classes("text-xs text-gray-500")
            ui.upload(
                multiple=True, auto_upload=True, on_upload=handle_upload,
                label="+ Add documents",
            ).props("accept=.pdf flat dense color=dark").classes("w-full")

    with ui.column().classes("w-full px-6 pb-6 gap-3"):
        for tab in proj["tabs"]:
            render_tab(tab)

    # ---------- VISUAL PREVIEW (read-only, mirrors TOC order)
    with ui.column().classes("w-full px-6 pt-6 pb-2 gap-2"):
        ui.label("VISUAL PREVIEW").classes("text-xs font-bold text-gray-400 tracking-widest")
        ui.label("Read-only — reorder from the TOC above.").classes("text-xs text-gray-500")
    with ui.column().classes("w-full px-6 pb-10 gap-3"):
        numbering = exhibit_numbering(proj)
        any_exhibits = bool(numbering)
        if not any_exhibits:
            ui.label("(no exhibits yet)").classes("text-sm text-gray-400 italic")
        for tab in proj["tabs"]:
            tab_has = any(p["exhibits"] for p in tab["packets"])
            if not tab_has:
                continue
            render_visual_tab(tab, numbering)


def render_visual_tab(tab, numbering):
    with ui.column().classes("w-full bg-gray-50 rounded-xl p-3 gap-2"):
        with ui.row().classes("w-full items-center gap-2"):
            ui.label(tab["letter"]).classes("text-lg font-bold text-gray-500 w-6")
            ui.label(tab["name"]).classes("font-semibold text-black")
        with ui.row().classes("w-full flex-nowrap overflow-x-auto items-start gap-3 pb-2"):
            for pkt in tab["packets"]:
                if not pkt["exhibits"]:
                    continue
                render_visual_packet(pkt, numbering)


def render_visual_packet(pkt, numbering):
    proj = S["proj"]
    with ui.column().classes("shrink-0 bg-white rounded border border-gray-200 p-2 gap-2").style("width:200px;"):
        with ui.row().classes("w-full items-center gap-2 text-xs text-gray-500"):
            ui.label(pkt["name"]).classes("font-semibold text-black")
            ui.label(f"{len(pkt['exhibits'])} ex").classes("text-[10px]")
        with ui.column().classes("w-full gap-1 max-h-[60vh] overflow-y-auto"):
            for ex in pkt["exhibits"]:
                render_visual_exhibit(ex, numbering.get(ex["id"], "?"))


def render_visual_exhibit(ex, exhibit_number):
    proj = S["proj"]
    src = proj["sources"].get(ex["src_id"], {})
    card = ui.card().classes(
        "relative p-0 overflow-hidden cursor-pointer bg-gray-50 rounded shadow-sm "
        "hover:shadow-md hover:ring-2 hover:ring-gray-400 transition w-full"
    )
    card.on("click", lambda _e, eid=ex["id"]: open_exhibit_preview(eid))
    card.tooltip(f"Ex {exhibit_number} · {ex.get('title', '')}")
    with card:
        ui.html(
            f'<img src="/pdfdata/{proj["slug"]}/thumbs/{ex["src_id"]}-0.png" '
            f'style="display:block;width:100%;height:auto;background:#fff;" />',
            sanitize=False,
        )
        ui.label(f"Ex {exhibit_number}").classes(
            "absolute top-0 left-0 bg-black text-white text-[10px] font-bold leading-none px-1.5 py-1 rounded-br"
        )
        ui.label(ex.get("title", "")).classes(
            "absolute bottom-0 left-0 right-0 bg-black/70 text-white text-[10px] leading-tight "
            "px-1 py-0.5 truncate"
        )


def open_exhibit_preview(exhibit_id):
    """Lightbox — full-page preview of all pages of an exhibit. Read-only."""
    proj = S["proj"]
    _t, _p, ex = storage.find_exhibit(proj, exhibit_id)
    if ex is None:
        return
    pages = proj["sources"].get(ex["src_id"], {}).get("page_count", 1)
    numbering = exhibit_numbering(proj)
    n = numbering.get(exhibit_id, "?")
    st = {"page": 0}

    def preview_url(p):
        path = storage.preview_dir(proj["slug"]) / f"{ex['src_id']}-{p}.png"
        if not path.exists():
            pdf_engine.render_preview(
                storage.source_dir(proj["slug"]) / f"{ex['src_id']}.pdf", p, path
            )
        return f"/pdfdata/{proj['slug']}/preview/{ex['src_id']}-{p}.png"

    with ui.dialog().props("maximized") as dialog, ui.card().classes(
        "bg-black text-white w-full h-full p-0 gap-0 items-stretch"
    ):
        with ui.row().classes("w-full items-center no-wrap gap-2 px-4 py-2 bg-black"):
            cap = ui.label().classes("text-sm truncate grow")
            ui.button(icon="close", on_click=dialog.close).props("flat round dense color=white")
        with ui.row().classes("w-full grow items-center justify-center overflow-auto bg-black"):
            @ui.refreshable
            def big():
                ui.html(
                    f'<img src="{preview_url(st["page"])}" style="max-height:82vh;max-width:94vw;'
                    f'object-fit:contain;display:block;margin:auto;border-radius:4px;" />',
                    sanitize=False,
                )
            big()

        def update_cap():
            cap.text = f"Ex {n} · {ex.get('title','')} · page {st['page']+1} / {pages}"

        def go(delta):
            st["page"] = max(0, min(pages - 1, st["page"] + delta))
            big.refresh(); update_cap()

        with ui.row().classes("w-full justify-center gap-6 py-2 bg-black"):
            ui.button("Prev", icon="chevron_left", on_click=lambda: go(-1)).props("flat color=white")
            ui.button("Next", icon="chevron_right", on_click=lambda: go(1)).props("flat color=white")
        update_cap()
    dialog.open()


def render_compliance_summary(proj):
    total_ex = sum(len(p["exhibits"]) for t in proj["tabs"] for p in t["packets"])
    used_pkts = [p for t in proj["tabs"] for p in t["packets"] if p["exhibits"]]
    total_pkt = len(used_pkts)
    total_size = sum(s for s in S["sizes"].values() if isinstance(s, int) and s > 0)
    empty_tabs = [t["letter"] for t in proj["tabs"] if not any(p["exhibits"] for p in t["packets"])]
    limit = section_limit_bytes(proj)
    over = [p["name"] for t in proj["tabs"] for p in t["packets"] if (S["sizes"].get(p["id"]) or 0) > limit]

    def stat(label, value, color="text-black"):
        with ui.column().classes("gap-0 shrink-0"):
            ui.label(label).classes("text-[10px] uppercase tracking-wider text-gray-400")
            ui.label(str(value)).classes(f"font-semibold {color}")

    with ui.column().classes("w-full px-6 pt-4"):
        with ui.card().classes("w-full p-3 bg-gray-50 border border-gray-200"):
            with ui.row().classes("w-full gap-8 items-center no-wrap"):
                stat("Exhibits", total_ex)
                stat("Packets", total_pkt)
                stat("Total size", hsize(total_size) if total_size else "—")
                stat("Empty tabs", ", ".join(empty_tabs) or "—")
                stat(
                    "Over 12MB",
                    ", ".join(over) if over else "none",
                    color="text-red-600" if over else "text-emerald-600",
                )


def render_tab(tab):
    with ui.column().classes("w-full bg-gray-50 rounded-xl shadow-sm overflow-hidden"):
        # tab header
        with ui.row().classes("w-full items-center no-wrap gap-3 px-4 py-3 bg-white border-b border-gray-200"):
            ui.label(tab["letter"]).classes("text-2xl font-bold text-black w-8 shrink-0")
            with ui.column().classes("grow gap-0 min-w-0"):
                ui.label(tab["name"]).classes("font-semibold text-black")
                ui.label(tab["hint"]).classes("text-[11px] text-gray-500 truncate")
            ui.button("+ Packet", on_click=lambda _e, tid=tab["id"]: add_packet(tid)).props(
                "flat dense color=dark"
            ).tooltip("Add another packet in this tab (for the 12MB-per-file limit)")

        # packets
        with ui.column().classes("w-full p-3 gap-2"):
            for pkt in tab["packets"]:
                render_packet(tab, pkt)


def render_packet(tab, pkt):
    pkt_idx = tab["packets"].index(pkt)
    last_idx = len(tab["packets"]) - 1
    proj = S["proj"]
    size = S["sizes"].get(pkt["id"])
    limit = section_limit_bytes(proj)
    limit_mb = proj.get("size_limit_mb", 12)

    if size is None:
        bar_color, bar_text, bar_pct = "bg-gray-300", "computing…", 0
    elif size < 0 or size == 0:
        bar_color, bar_text, bar_pct = "bg-gray-200", "empty", 0
    else:
        bar_pct = min(100, size * 100 / limit) if limit else 0
        if size > limit:
            bar_color = "bg-red-500"
            bar_text = f"{hsize(size)} / {limit_mb} MB ⚠"
        elif bar_pct >= 90:
            bar_color = "bg-amber-400"
            bar_text = f"{hsize(size)} / {limit_mb} MB"
        else:
            bar_color = "bg-emerald-500"
            bar_text = f"{hsize(size)} / {limit_mb} MB"

    col = ui.column().classes("w-full bg-white rounded border border-gray-200 p-3 gap-2")
    col.on("dragover.prevent", lambda: None)
    col.on("drop", lambda _e, pid=pkt["id"]: drop_on_packet(pid))
    with col:
        with ui.row().classes("w-full items-center no-wrap gap-2"):
            ui.input(value=pkt["name"], on_change=lambda e, pid=pkt["id"]: rename_packet(pid, e.value)).props(
                "borderless dense"
            ).classes("font-semibold")
            ui.label(f"{len(pkt['exhibits'])} exhibit{'s' if len(pkt['exhibits']) != 1 else ''}").classes(
                "text-xs text-gray-500"
            )
            ui.space()
            # size bar
            with ui.column().classes("w-44 gap-1 shrink-0"):
                ui.label(bar_text).classes("text-[11px] text-gray-600 text-right")
                with ui.element("div").classes("w-full h-2 bg-gray-200 rounded overflow-hidden"):
                    ui.element("div").classes(f"h-full {bar_color}").style(f"width:{bar_pct}%;")
            ui.button(icon="merge", on_click=lambda _e, pid=pkt["id"]: merge_packet(pid)).props(
                "flat round dense size=sm color=dark"
            ).tooltip("Merge this packet → PDF")
            ui.button(icon="arrow_upward",
                      on_click=lambda _e, pid=pkt["id"]: move_packet(pid, -1)).props(
                f"flat round dense size=sm color=dark{' disable' if pkt_idx == 0 else ''}"
            ).tooltip("Move packet up")
            ui.button(icon="arrow_downward",
                      on_click=lambda _e, pid=pkt["id"]: move_packet(pid, 1)).props(
                f"flat round dense size=sm color=dark{' disable' if pkt_idx == last_idx else ''}"
            ).tooltip("Move packet down")
            ui.button(icon="delete", on_click=lambda _e, pid=pkt["id"]: delete_packet(pid)).props(
                "flat round dense size=sm color=red"
            ).tooltip("Delete this packet")
        if not pkt["exhibits"]:
            ui.label("(empty — upload PDFs above; AI lands them here)").classes(
                "text-xs text-gray-400 italic"
            )
        else:
            numbering = exhibit_numbering(S["proj"])
            for ex in pkt["exhibits"]:
                render_exhibit_row(ex, numbering.get(ex["id"], "?"))


def exhibit_numbering(proj):
    """Continuous Ex 1..N across the whole petition, in TOC order."""
    return {ex["id"]: n for _t, _p, ex, n in storage.iter_exhibits(proj)}


def render_exhibit_row(ex, exhibit_number):
    src = S["proj"]["sources"].get(ex["src_id"], {})
    row = ui.row().classes(
        "w-full items-center gap-2 text-sm text-gray-700 p-2 rounded hover:bg-gray-50 cursor-grab"
    )
    row.props("draggable")
    row.on("dragstart", lambda _e, eid=ex["id"]: set_drag_exhibit(eid))
    row.on("dragover.prevent", lambda: None)
    row.on("drop.stop", lambda _e, eid=ex["id"]: drop_on_exhibit(eid))
    with row:
        ui.icon("drag_indicator").classes("text-gray-300")
        ui.label(f"Ex {exhibit_number}").classes("font-mono text-xs text-gray-500 w-12")
        ui.icon("article").classes("text-gray-500")
        with ui.column().classes("grow gap-0 min-w-0"):
            ui.label(ex.get("title") or "(untitled)").classes("truncate font-medium text-black")
            ui.label(
                f"{src.get('filename', '?')}  ·  {src.get('page_count', '?')} pp"
            ).classes("text-[11px] text-gray-400 truncate")
        ui.button(icon="edit", on_click=lambda _e, eid=ex["id"]: edit_exhibit_dialog(eid)).props(
            "flat round dense size=sm color=dark"
        ).tooltip("Edit title / cover paragraph")
        ui.button(icon="delete", on_click=lambda _e, eid=ex["id"]: confirm_delete_exhibit(eid)).props(
            "flat round dense size=sm color=red"
        ).tooltip("Delete exhibit")


def confirm_delete_exhibit(exhibit_id):
    proj = S["proj"]
    _t, _p, ex = storage.find_exhibit(proj, exhibit_id)
    if ex is None:
        return
    with ui.dialog() as d, ui.card().classes("p-5 gap-3 min-w-80"):
        ui.label("Delete this exhibit?").classes("text-lg font-semibold text-black")
        ui.label(f'"{ex["title"]}"').classes("text-sm text-gray-500")
        with ui.row().classes("w-full justify-end gap-2"):
            ui.button("Cancel", on_click=d.close).props("flat")
            ui.button("Delete", icon="delete",
                      on_click=lambda: (d.close(), delete_exhibit(exhibit_id))).props("color=red")
    d.open()


def edit_exhibit_dialog(exhibit_id):
    proj = S["proj"]
    _t, _p, ex = storage.find_exhibit(proj, exhibit_id)
    if ex is None:
        return
    with ui.dialog() as d, ui.card().classes("p-5 gap-3 min-w-[40rem]"):
        ui.label("Edit exhibit").classes("text-lg font-semibold text-black")
        title_in = ui.input("Title", value=ex.get("title", "")).classes("w-full")
        cover_in = ui.textarea("Cover-sheet paragraph", value=ex.get("cover_paragraph", "")).props(
            "autogrow"
        ).classes("w-full")

        async def regen():
            if not ai.have_key():
                ui.notify("No API key — set ANTHROPIC_API_KEY in .env", type="warning")
                return
            ui.notify("Regenerating with AI…", type="info")
            pdf_path = storage.source_dir(proj["slug"]) / f"{ex['src_id']}.pdf"
            text, _ = await asyncio.to_thread(ocr.extract_or_ocr, pdf_path)
            if not text:
                ui.notify("No text extracted from source PDF", type="warning")
                return
            try:
                result = await asyncio.to_thread(
                    ai.classify_document, text, ex.get("title", "") + ".pdf"
                )
                title_in.value = result["title"]
                cover_in.value = result["cover_paragraph"]
                ui.notify("AI regenerated — review and save", type="positive")
            except Exception as ex2:
                ui.notify(f"AI failed: {ex2}", type="negative")

        with ui.row().classes("w-full justify-end gap-2"):
            ui.button("Regenerate with AI", icon="auto_awesome", on_click=regen).props(
                "flat color=dark"
            ).tooltip("Re-run Claude on the source PDF to redraft the title + cover paragraph")
            ui.button("Cancel", on_click=d.close).props("flat")
            ui.button(
                "Save",
                on_click=lambda: (
                    _save_exhibit_edits(exhibit_id, title_in.value, cover_in.value),
                    d.close(),
                ),
            ).props("color=dark")
    d.open()


def _save_exhibit_edits(exhibit_id, title, cover):
    proj = S["proj"]
    _t, _p, ex = storage.find_exhibit(proj, exhibit_id)
    if ex is None:
        return
    ex["title"] = (title or ex["title"]).strip() or "Untitled"
    ex["cover_paragraph"] = (cover or "").strip()
    save()
    _t, pkt, _e = storage.find_exhibit(S["proj"], exhibit_id)
    if pkt is not None:
        schedule_packet_recompute(pkt["id"])
    view.refresh()


# ---------------------------------------------------------------- bootstrap
def init():
    projects = storage.list_projects()
    if projects:
        S["proj"] = storage.load(projects[0][0])
    else:
        S["proj"] = storage.new_project("Untitled NIW Petition", "")
    S["ai_status"] = None
    S["sizes"] = {}
    view()
    # check Anthropic + measure all packet sizes in background
    from nicegui import background_tasks
    background_tasks.create(refresh_api_status())
    schedule_all_recompute()


@ui.page("/")
def index():
    ui.add_head_html("<style>.nicegui-content{padding:0}</style>")
    init()


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(title="NIW Petition Builder", port=8080, reload=False, show=False, favicon="📄")
