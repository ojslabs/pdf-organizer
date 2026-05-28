"""NIW Petition Builder — local, browser-based EB-2 National Interest Waiver
I-140 petition assembler.

Each project corresponds to one petition. The UI presents the eight standard
NIW sections (Petition Letter & Forms; Identity; EB-2 Eligibility; Dhanasar
Prongs 1–3; Recommendation Letters; Additional) with named upload slots for
every required, recommended, conditional, or optional document. On merge,
each section becomes a single ≤12MB PDF with an auto-generated exhibit cover
sheet before each exhibit; a master exhibit index PDF ties the upload set
together for the adjudicating officer.
"""
from __future__ import annotations

import asyncio

from nicegui import app, background_tasks, events, ui

import cover_sheet  # noqa: F401  (used indirectly via pdf_engine)
import niw_template
import pdf_engine
import storage

# ---------------------------------------------------------------- app state
S = {
    "proj": None,
    # exact section sizes, keyed by section id. value: int (bytes) | None (computing) | -1 (no exhibits)
    "sizes": {},
}
_drag = {"exhibit_id": None, "from_slot_id": None}

storage.PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
app.add_static_files("/pdfdata", str(storage.PROJECTS_DIR))


# ---------------------------------------------------------------- helpers
def hsize(n: float) -> str:
    if n is None or n < 0:
        return "—"
    n = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def thumb_url(proj, src_id, page=0) -> str:
    return f"/pdfdata/{proj['slug']}/thumbs/{src_id}-{page}.png"


def ensure_preview(proj, src_id, page) -> str:
    p = storage.preview_dir(proj["slug"]) / f"{src_id}-{page}.png"
    if not p.exists():
        pdf_engine.render_preview(
            storage.source_dir(proj["slug"]) / f"{src_id}.pdf", page, p
        )
    return f"/pdfdata/{proj['slug']}/preview/{src_id}-{page}.png"


def save():
    storage.save(S["proj"])


def section_limit_bytes(proj) -> int:
    return int(proj.get("size_limit_mb", 12)) * 1024 * 1024


def completeness(proj):
    """Return (required_satisfied, required_total)."""
    sat = tot = 0
    for sec in proj["sections"]:
        for slot in sec["slots"]:
            if slot["requirement"] == "required":
                tot += 1
                if slot["exhibits"]:
                    sat += 1
    return sat, tot


def exhibit_numbering(proj):
    """Return {exhibit_id: number} assigned in petition order."""
    out, n = {}, 0
    for _s, _slot, ex, num in storage.iter_exhibits(proj):
        out[ex["id"]] = num
        n = num
    return out


def section_exhibits_numbered(proj, section, numbering):
    """List of (slot_name, exhibit_dict, exhibit_number) for one section, in order."""
    res = []
    for slot in section["slots"]:
        for ex in slot["exhibits"]:
            res.append((slot["name"], ex, numbering[ex["id"]]))
    return res


# ---------------------------------------------------------------- background sizing
def _measure_blocking(section_id):
    proj = S["proj"]
    section = next((s for s in proj["sections"] if s["id"] == section_id), None)
    if section is None:
        return 0
    numbering = exhibit_numbering(proj)
    items = section_exhibits_numbered(proj, section, numbering)
    if not items:
        return -1
    return pdf_engine.measure_section_size(
        proj.get("petitioner", ""),
        section["name"],
        items,
        storage.source_dir(proj["slug"]),
    )


async def recompute_size(section_id):
    """Mark the section as computing, run measurement in a thread, refresh UI."""
    S["sizes"][section_id] = None
    view.refresh()
    try:
        sz = await asyncio.to_thread(_measure_blocking, section_id)
        S["sizes"][section_id] = sz
    except Exception as e:
        S["sizes"][section_id] = -1
        ui.notify(f"Size computation failed: {e}", type="negative")
    view.refresh()


def schedule_section_recompute(section_id):
    background_tasks.create(recompute_size(section_id))


def schedule_all_recompute():
    if S["proj"] is None:
        return
    for sec in S["proj"]["sections"]:
        schedule_section_recompute(sec["id"])


# ---------------------------------------------------------------- mutations
async def handle_upload(e: events.UploadEventArguments, slot_id: str):
    proj = S["proj"]
    data = await e.file.read()
    name = e.file.name
    src_id = storage.new_id()
    page_count, nbytes = pdf_engine.import_pdf(
        data, src_id, storage.source_dir(proj["slug"]), storage.thumb_dir(proj["slug"])
    )
    proj["sources"][src_id] = {"filename": name, "page_count": page_count, "bytes": nbytes}

    section, slot = storage.find_slot(proj, slot_id)
    slot["exhibits"].append(
        {
            "id": storage.new_id(),
            "src_id": src_id,
            "label": name.removesuffix(".pdf"),
            "rationale": slot["rationale"],
        }
    )
    save()
    ui.notify(f"Added {name} ({page_count} pages)", type="positive")
    schedule_section_recompute(section["id"])
    view.refresh()


def delete_exhibit(exhibit_id):
    proj = S["proj"]
    section, slot, ex = storage.find_exhibit(proj, exhibit_id)
    if ex is None:
        return
    slot["exhibits"] = [x for x in slot["exhibits"] if x["id"] != exhibit_id]

    # if this source isn't referenced anywhere anymore, delete its files
    sid = ex["src_id"]
    still_used = any(
        x["src_id"] == sid
        for s in proj["sections"]
        for sl in s["slots"]
        for x in sl["exhibits"]
    )
    if not still_used:
        proj["sources"].pop(sid, None)
        (storage.source_dir(proj["slug"]) / f"{sid}.pdf").unlink(missing_ok=True)
        for d in (storage.thumb_dir(proj["slug"]), storage.preview_dir(proj["slug"])):
            for f in d.glob(f"{sid}-*.png"):
                f.unlink(missing_ok=True)

    save()
    schedule_section_recompute(section["id"])
    view.refresh()


def update_exhibit_label_rationale(exhibit_id, label, rationale):
    proj = S["proj"]
    section, slot, ex = storage.find_exhibit(proj, exhibit_id)
    if ex is None:
        return
    ex["label"] = label or ex["label"]
    ex["rationale"] = rationale or ""
    save()
    schedule_section_recompute(section["id"])
    view.refresh()


def set_drag(exhibit_id, slot_id):
    _drag["exhibit_id"] = exhibit_id
    _drag["from_slot_id"] = slot_id


def move_exhibit(dst_slot_id, dst_index):
    """Move dragged exhibit to dst_slot_id at dst_index (None = append). dst_index
    refers to position before the target exhibit (if any)."""
    proj = S["proj"]
    eid = _drag["exhibit_id"]
    if eid is None:
        return
    src_section, src_slot = None, None
    ex = None
    src_idx = -1
    for s in proj["sections"]:
        for sl in s["slots"]:
            for i, x in enumerate(sl["exhibits"]):
                if x["id"] == eid:
                    src_section, src_slot, src_idx = s, sl, i
                    ex = x
    if ex is None:
        _drag["exhibit_id"] = None
        return
    dst_section, dst_slot = storage.find_slot(proj, dst_slot_id)
    if dst_slot is None:
        _drag["exhibit_id"] = None
        return

    src_slot["exhibits"].pop(src_idx)
    if dst_index is None:
        dst_slot["exhibits"].append(ex)
    else:
        if src_slot is dst_slot and src_idx < dst_index:
            dst_index -= 1
        dst_slot["exhibits"].insert(dst_index, ex)
    _drag["exhibit_id"] = None
    save()
    schedule_section_recompute(src_section["id"])
    if dst_section["id"] != src_section["id"]:
        schedule_section_recompute(dst_section["id"])
    view.refresh()


def set_petitioner(name):
    S["proj"]["petitioner"] = name
    save()
    # cover sheets include petitioner -> invalidate sizes
    schedule_all_recompute()


def set_project_name(name):
    S["proj"]["name"] = name or "Untitled Petition"
    save()


def switch_project(slug):
    S["proj"] = storage.load(slug)
    S["sizes"] = {}
    schedule_all_recompute()
    view.refresh()


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
    S["sizes"] = {}
    dialog.close()
    view.refresh()


# ---------------------------------------------------------------- merge / export
def merge_section(section_id):
    proj = S["proj"]
    section = next((s for s in proj["sections"] if s["id"] == section_id), None)
    if section is None:
        return
    numbering = exhibit_numbering(proj)
    items = section_exhibits_numbered(proj, section, numbering)
    if not items:
        ui.notify("This section is empty.", type="warning")
        return
    sec_idx = proj["sections"].index(section) + 1
    fname = f"{sec_idx:02d}_{storage.slugify(section['name'])}.pdf"
    target = storage.output_dir(proj["slug"]) / fname
    size = pdf_engine.build_section_pdf(
        proj.get("petitioner", ""),
        section["name"],
        items,
        storage.source_dir(proj["slug"]),
        target,
    )
    S["sizes"][section_id] = size
    limit = section_limit_bytes(proj)
    if size > limit:
        ui.notify(
            f"Merged → {fname} ({hsize(size)}) — OVER 12MB LIMIT. Split before uploading.",
            type="warning",
        )
    else:
        ui.notify(f"Merged → {fname} ({hsize(size)})", type="positive")
    ui.download(f"/pdfdata/{proj['slug']}/output/{fname}")
    view.refresh()


def build_master_index_now():
    proj = S["proj"]
    numbering = exhibit_numbering(proj)
    if not numbering:
        ui.notify("No exhibits yet.", type="warning")
        return
    # compute (file, page) location of each exhibit's cover sheet
    entries = []
    for sec_idx, section in enumerate(proj["sections"], start=1):
        fname = f"{sec_idx:02d}_{storage.slugify(section['name'])}.pdf"
        page = 1
        for slot in section["slots"]:
            for ex in slot["exhibits"]:
                entries.append(
                    {
                        "number": numbering[ex["id"]],
                        "label": ex["label"],
                        "section": section["name"],
                        "output_file": fname,
                        "page": page,
                    }
                )
                # exhibit takes 1 cover-sheet page + its source page count
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
    over = []
    built = []
    for sec_idx, section in enumerate(proj["sections"], start=1):
        items = section_exhibits_numbered(proj, section, numbering)
        if not items:
            continue
        fname = f"{sec_idx:02d}_{storage.slugify(section['name'])}.pdf"
        target = storage.output_dir(proj["slug"]) / fname
        size = pdf_engine.build_section_pdf(
            proj.get("petitioner", ""), section["name"], items,
            storage.source_dir(proj["slug"]), target,
        )
        S["sizes"][section["id"]] = size
        built.append((fname, size))
        if size > section_limit_bytes(proj):
            over.append(fname)
    build_master_index_now()
    msg = f"Exported {len(built)} files to projects/{proj['slug']}/output/."
    if over:
        msg += f" ⚠ Over 12MB: {', '.join(over)}"
        ui.notify(msg, type="warning")
    else:
        ui.notify(msg, type="positive")
    view.refresh()


# ---------------------------------------------------------------- UI: view
@ui.refreshable
def view():
    proj = S["proj"]
    if proj is None:
        return

    sat, tot = completeness(proj)
    # ------------ top bar
    with ui.row().classes("w-full items-center gap-4 px-6 py-3 bg-black text-white shadow-md"):
        ui.icon("description").classes("text-3xl text-white")
        with ui.column().classes("gap-0"):
            ui.label("NIW Petition Builder").classes("text-xl font-bold leading-tight")
            ui.label("EB-2 National Interest Waiver · I-140").classes("text-[10px] text-gray-400 leading-tight")
        ui.element("div").classes("w-4")

        projects = storage.list_projects()
        ui.select(
            options={s: n for s, n in projects},
            value=proj["slug"],
            on_change=lambda e: switch_project(e.value),
        ).props("dark dense outlined").classes("min-w-48")
        ui.button(icon="add", on_click=create_project_dialog).props("flat round dense color=white").tooltip("New petition")

        ui.space()

        # required-document completeness
        ok_color = "text-emerald-400" if sat == tot and tot else "text-amber-300"
        with ui.row().classes("items-center gap-1 bg-neutral-800 rounded-lg px-3 py-1"):
            ui.icon("rule").classes(ok_color)
            ui.label(f"Required: {sat}/{tot}").classes(f"font-semibold {ok_color}")

        ui.button("Master Index", icon="list_alt", on_click=build_master_index_now).props("color=dark").tooltip("Generate the master exhibit index PDF")
        ui.button("Export All", icon="folder_zip", on_click=export_all).props("color=dark").tooltip("Build all section PDFs + master index")

    # ------------ identity row
    with ui.row().classes("w-full items-center gap-4 px-6 pt-4"):
        ui.input(value=proj["name"], on_change=lambda e: set_project_name(e.value)).props("borderless").classes("text-2xl font-bold")
        ui.space()
        with ui.row().classes("items-center gap-2"):
            ui.label("Petitioner:").classes("text-xs text-gray-500")
            ui.input(value=proj.get("petitioner", ""), on_change=lambda e: set_petitioner(e.value)).props("dense outlined").classes("min-w-56")

    # ------------ sections
    with ui.column().classes("w-full p-6 gap-4"):
        for sec in proj["sections"]:
            render_section(proj, sec)


def render_section(proj, section):
    sec_idx = proj["sections"].index(section) + 1
    size = S["sizes"].get(section["id"])
    limit = section_limit_bytes(proj)
    # size bar color
    if size is None:
        bar_color, bar_text, bar_pct = "bg-gray-300", "computing…", 0
    elif size < 0:
        bar_color, bar_text, bar_pct = "bg-gray-200", "empty", 0
    else:
        bar_pct = min(100, size * 100 / limit) if limit else 0
        if size > limit:
            bar_color = "bg-red-500"
            bar_text = f"{hsize(size)} / {limit // (1024*1024)} MB  ⚠ over"
        elif bar_pct >= 90:
            bar_color, bar_text = "bg-amber-400", f"{hsize(size)} / {limit // (1024*1024)} MB"
        else:
            bar_color, bar_text = "bg-emerald-500", f"{hsize(size)} / {limit // (1024*1024)} MB"

    with ui.column().classes("w-full bg-gray-50 rounded-xl shadow-sm overflow-hidden"):
        # section header
        with ui.row().classes("w-full items-center no-wrap gap-3 px-4 py-3 bg-white border-b border-gray-200"):
            ui.label(f"{sec_idx}").classes("text-lg font-bold text-gray-400 w-6 shrink-0")
            with ui.column().classes("grow gap-0 min-w-0"):
                ui.label(section["name"]).classes("font-semibold text-black")
                ui.label(section["hint"]).classes("text-[11px] text-gray-500 truncate")
            # size bar
            with ui.column().classes("w-48 gap-1 shrink-0"):
                ui.label(bar_text).classes("text-[11px] text-gray-600 text-right")
                with ui.element("div").classes("w-full h-2 bg-gray-200 rounded overflow-hidden"):
                    ui.element("div").classes(f"h-full {bar_color}").style(f"width:{bar_pct}%;")
            ui.button(icon="merge", on_click=lambda _e, sid=section["id"]: merge_section(sid)).props(
                "flat round dense color=dark"
            ).tooltip("Merge this section into one PDF")

        # section body — slots
        with ui.column().classes("w-full p-4 gap-3"):
            for slot in section["slots"]:
                render_slot(proj, section, slot)


def render_slot(proj, section, slot):
    sid = slot["id"]
    badge_text, badge_class = niw_template.REQUIREMENT_BADGES[slot["requirement"]]
    has = len(slot["exhibits"])
    status_icon, status_color = ("check_circle", "text-emerald-600") if has else (
        ("error", "text-red-500") if slot["requirement"] == "required" else ("circle", "text-gray-400")
    )

    card = ui.card().classes("w-full p-3 gap-2 bg-white rounded shadow-sm border border-gray-200")
    card.on("dragover.prevent", lambda: None)
    card.on("drop", lambda _e, sid=sid: move_exhibit(sid, None))  # drop on slot -> append

    with card:
        with ui.row().classes("w-full items-center no-wrap gap-2"):
            ui.icon(status_icon).classes(f"text-base {status_color}")
            ui.label(slot["name"]).classes("font-semibold text-black grow truncate")
            ui.label(badge_text).classes(f"text-[10px] px-2 py-0.5 rounded-full font-semibold {badge_class}")
            if has:
                ui.label(f"{has} file{'s' if has != 1 else ''}").classes("text-[11px] text-gray-500")
        ui.label(slot["description"]).classes("text-[12px] text-gray-600 leading-snug")

        # exhibits row (mini cards) — drag-reorder/move between slots
        if slot["exhibits"]:
            with ui.row().classes("w-full flex-wrap gap-2 pt-1"):
                for i, ex in enumerate(slot["exhibits"]):
                    render_exhibit_card(proj, section, slot, i, ex)

        # uploader
        ui.upload(
            multiple=True,
            auto_upload=True,
            on_upload=lambda _e, sid=sid: handle_upload(_e, sid),
            label="+ Add document",
        ).props("accept=.pdf flat dense color=dark").classes("w-full")


def render_exhibit_card(proj, section, slot, index, ex):
    eid = ex["id"]
    src = proj["sources"].get(ex["src_id"], {})
    numbering = exhibit_numbering(proj)
    n = numbering.get(eid, "?")

    card = ui.card().classes(
        "relative p-0 overflow-hidden cursor-pointer bg-gray-50 rounded shadow-sm "
        "hover:shadow-md hover:ring-2 hover:ring-gray-400 transition"
    ).style("width:130px;")
    card.props("draggable")
    card.on("dragstart", lambda _e, eid=eid, sid=slot["id"]: set_drag(eid, sid))
    card.on("dragover.prevent", lambda: None)
    card.on("drop.stop", lambda _e, sid=slot["id"], i=index: move_exhibit(sid, i))
    card.on("click", lambda _e, eid=eid: open_exhibit(eid))
    card.tooltip(f"Exhibit {n} · {ex['label']}")

    with card:
        ui.html(
            f'<img src="{thumb_url(proj, ex["src_id"], 0)}" '
            f'style="display:block;width:100%;height:auto;background:#fff;" />',
            sanitize=False,
        )
        # exhibit-number badge top-left
        ui.label(f"Ex {n}").classes(
            "absolute top-0 left-0 bg-black text-white text-[10px] font-bold leading-none px-1.5 py-1 rounded-br"
        )
        # filename caption bottom
        ui.label(ex["label"]).classes(
            "absolute bottom-0 left-0 right-0 bg-black/70 text-white text-[10px] leading-tight "
            "px-1 py-0.5 truncate"
        )


# ---------------------------------------------------------------- exhibit lightbox
def open_exhibit(exhibit_id):
    proj = S["proj"]
    section, slot, ex = storage.find_exhibit(proj, exhibit_id)
    if ex is None:
        return
    src = proj["sources"].get(ex["src_id"], {})
    pages = src.get("page_count", 1)
    numbering = exhibit_numbering(proj)
    n = numbering.get(exhibit_id, "?")
    st = {"page": 0}

    with ui.dialog().props("maximized") as dialog, ui.card().classes(
        "bg-black text-white w-full h-full p-0 gap-0 items-stretch"
    ):
        with ui.row().classes("w-full items-center no-wrap gap-2 px-4 py-2 bg-black"):
            cap = ui.label().classes("text-sm truncate grow")
            ui.button("Edit", icon="edit", on_click=lambda: edit_rationale_dialog(exhibit_id)).props("flat color=white dense")
            ui.button("Delete", icon="delete", on_click=lambda: confirm_delete()).props("color=red dense")
            ui.button(icon="close", on_click=dialog.close).props("flat round dense color=white")

        with ui.row().classes("w-full grow items-center justify-center overflow-auto bg-black"):
            @ui.refreshable
            def big_image():
                url = ensure_preview(proj, ex["src_id"], st["page"])
                ui.html(
                    f'<img src="{url}" style="max-height:82vh;max-width:94vw;'
                    f'object-fit:contain;display:block;margin:auto;border-radius:4px;" />',
                    sanitize=False,
                )
            big_image()

        def update_cap():
            cap.text = (
                f"Exhibit {n} · {section['name']} · {slot['name']}  ·  "
                f"{ex['label']}  ·  page {st['page'] + 1} / {pages}"
            )
        update_cap()

        def go(delta):
            st["page"] = max(0, min(pages - 1, st["page"] + delta))
            big_image.refresh(); update_cap()

        def confirm_delete():
            with ui.dialog() as cd, ui.card().classes("p-5 gap-3 min-w-80"):
                ui.label("Delete this exhibit?").classes("text-lg font-semibold text-black")
                ui.label(f'"{ex["label"]}" — {pages} page(s).').classes("text-sm text-gray-500")
                with ui.row().classes("w-full justify-end gap-2"):
                    ui.button("Cancel", on_click=cd.close).props("flat")
                    ui.button("Delete", icon="delete", on_click=lambda: (cd.close(), dialog.close(), delete_exhibit(exhibit_id))).props("color=red")
            cd.open()

        with ui.row().classes("w-full justify-center gap-6 py-2 bg-black"):
            ui.button("Prev", icon="chevron_left", on_click=lambda: go(-1)).props("flat color=white")
            ui.button("Next", icon="chevron_right", on_click=lambda: go(1)).props("flat color=white")
    dialog.open()


# ---------------------------------------------------------------- rationale editor
def edit_rationale_dialog(exhibit_id):
    proj = S["proj"]
    _section, _slot, ex = storage.find_exhibit(proj, exhibit_id)
    if ex is None:
        return
    with ui.dialog() as d, ui.card().classes("p-5 gap-3 min-w-[36rem]"):
        ui.label("Edit exhibit cover sheet").classes("text-lg font-semibold text-black")
        ui.label("This is printed on the cover sheet that precedes the exhibit in the merged PDF.").classes("text-xs text-gray-500")
        label_in = ui.input("Exhibit title", value=ex["label"]).classes("w-full")
        rationale_in = ui.textarea(
            "Rationale (why this exhibit is included)",
            value=ex.get("rationale", ""),
        ).props("autogrow").classes("w-full")
        with ui.row().classes("w-full justify-end gap-2"):
            ui.button("Cancel", on_click=d.close).props("flat")
            ui.button(
                "Save",
                on_click=lambda: (
                    update_exhibit_label_rationale(exhibit_id, label_in.value, rationale_in.value),
                    d.close(),
                ),
            ).props("color=dark")
    d.open()


# ---------------------------------------------------------------- bootstrap
def init():
    projects = storage.list_projects()
    if projects:
        S["proj"] = storage.load(projects[0][0])
    else:
        S["proj"] = storage.new_project("Untitled NIW Petition", "")
    S["sizes"] = {}
    view()
    schedule_all_recompute()


@ui.page("/")
def index():
    ui.add_head_html("<style>.nicegui-content{padding:0}</style>")
    init()


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(title="NIW Petition Builder", port=8080, reload=False, show=True, favicon="📄")
