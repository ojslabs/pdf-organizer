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

from nicegui import app, ui  # noqa: E402

import ai  # noqa: E402
import niw_template  # noqa: E402
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
    with ui.column().classes("w-full px-6 pt-6 pb-4 gap-2"):
        ui.label("TABLE OF CONTENTS").classes("text-xs font-bold text-gray-400 tracking-widest")
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
            ui.label("(empty — upload PDFs to land exhibits here)").classes(
                "text-xs text-gray-400 italic"
            )
        else:
            # exhibits row — Phase 1 placeholder
            for ex in pkt["exhibits"]:
                with ui.row().classes("w-full items-center gap-2 text-sm text-gray-700"):
                    ui.icon("article").classes("text-gray-500")
                    ui.label(ex.get("title", "(untitled)")).classes("truncate")


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
