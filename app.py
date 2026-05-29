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
S = {"proj": None, "ai_status": None}  # ai_status: (ok: bool, msg: str) | None

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
    view.refresh()


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

    # ---------- VISUAL PREVIEW placeholder
    with ui.column().classes("w-full px-6 pb-10 gap-2"):
        ui.label("VISUAL PREVIEW").classes("text-xs font-bold text-gray-400 tracking-widest pt-4")
        ui.label("Page thumbnails appear here after you upload exhibits. (Read-only — reorder from the TOC above.)").classes(
            "text-sm text-gray-500 italic"
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
    with ui.column().classes("w-full bg-white rounded border border-gray-200 p-3 gap-2"):
        with ui.row().classes("w-full items-center no-wrap gap-2"):
            ui.input(value=pkt["name"], on_change=lambda e, pid=pkt["id"]: rename_packet(pid, e.value)).props(
                "borderless dense"
            ).classes("font-semibold")
            ui.label(f"{len(pkt['exhibits'])} exhibit{'s' if len(pkt['exhibits']) != 1 else ''}").classes(
                "text-xs text-gray-500"
            )
            ui.space()
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
    with ui.row().classes(
        "w-full items-center gap-2 text-sm text-gray-700 p-2 rounded hover:bg-gray-50"
    ):
        ui.icon("drag_indicator").classes("text-gray-300 cursor-grab")
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
        with ui.row().classes("w-full justify-end gap-2"):
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
    view.refresh()


# ---------------------------------------------------------------- bootstrap
def init():
    projects = storage.list_projects()
    if projects:
        S["proj"] = storage.load(projects[0][0])
    else:
        S["proj"] = storage.new_project("Untitled NIW Petition", "")
    S["ai_status"] = None
    view()
    # check Anthropic in background so UI doesn't block
    from nicegui import background_tasks
    background_tasks.create(refresh_api_status())


@ui.page("/")
def index():
    ui.add_head_html("<style>.nicegui-content{padding:0}</style>")
    init()


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(title="NIW Petition Builder", port=8080, reload=False, show=False, favicon="📄")
