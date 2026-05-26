"""PDF Organizer — local, browser-based packet builder.

Run:  python app.py   (opens http://localhost:8080)

A *project* holds multiple *packets* (columns). Each packet is an ordered list of
PDF pages. Drag page-cards within a column to reorder, or across columns to move
between packets. Each packet merges to one output PDF. State auto-saves.
"""
from pathlib import Path

from nicegui import app, events, ui

import pdf_engine
import storage

# ---------------------------------------------------------------- app state
S = {"proj": None}          # current project dict
_drag = {"packet": None, "index": None}  # in-flight drag: source packet id + page index

storage.PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
# serve project files (thumbnails + merged output) as static assets
app.add_static_files("/pdfdata", str(storage.PROJECTS_DIR))


# ---------------------------------------------------------------- helpers
def hsize(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def find_packet(proj, pid):
    return next((p for p in proj["packets"] if p["id"] == pid), None)


def packet_bytes(proj, packet) -> float:
    """Estimate: each page contributes source_bytes / source_page_count."""
    total = 0.0
    for pg in packet["pages"]:
        s = proj["sources"].get(pg["src"])
        if s and s["page_count"]:
            total += s["bytes"] / s["page_count"]
    return total


def project_bytes(proj) -> float:
    return sum(packet_bytes(proj, p) for p in proj["packets"])


def thumb_url(proj, pg) -> str:
    return f"/pdfdata/{proj['slug']}/thumbs/{pg['src']}-{pg['page']}.png"


def ensure_preview(proj, pg) -> str:
    """Lazily render a high-res preview for the lightbox; cache to preview/. Returns its URL."""
    p = storage.preview_dir(proj["slug"]) / f"{pg['src']}-{pg['page']}.png"
    if not p.exists():
        pdf_engine.render_preview(
            storage.source_dir(proj["slug"]) / f"{pg['src']}.pdf", pg["page"], p
        )
    return f"/pdfdata/{proj['slug']}/preview/{pg['src']}-{pg['page']}.png"


def save():
    storage.save(S["proj"])


# ---------------------------------------------------------------- mutations
async def handle_upload(e: events.UploadEventArguments, packet_id: str):
    proj = S["proj"]
    data = await e.file.read()  # NiceGUI 3.x: file is on e.file, read() is async
    name = e.file.name
    src_id = storage.new_id()
    page_count, nbytes = pdf_engine.import_pdf(
        data, src_id, storage.source_dir(proj["slug"]), storage.thumb_dir(proj["slug"])
    )
    proj["sources"][src_id] = {"filename": name, "page_count": page_count, "bytes": nbytes}
    pk = find_packet(proj, packet_id)
    for i in range(page_count):
        pk["pages"].append({"src": src_id, "page": i})
    save()
    ui.notify(f"Added {name} ({page_count} pages)", type="positive")
    view.refresh()


def set_drag(packet_id, index):
    _drag["packet"], _drag["index"] = packet_id, index


def do_move(dst_packet, dst_index):
    sp, si = _drag["packet"], _drag["index"]
    if sp is None:
        return
    proj = S["proj"]
    src_pk, dst_pk = find_packet(proj, sp), find_packet(proj, dst_packet)
    if src_pk is None or dst_pk is None or si is None or si >= len(src_pk["pages"]):
        _drag["packet"] = None
        return
    page = src_pk["pages"].pop(si)
    if dst_index is None:
        dst_pk["pages"].append(page)
    else:
        if sp == dst_packet and si < dst_index:
            dst_index -= 1
        dst_pk["pages"].insert(dst_index, page)
    _drag["packet"] = None
    save()
    view.refresh()


def delete_document(src_id):
    """Remove every page from this source across all packets, and delete its files."""
    proj = S["proj"]
    for pk in proj["packets"]:
        pk["pages"] = [p for p in pk["pages"] if p["src"] != src_id]
    proj["sources"].pop(src_id, None)
    (storage.source_dir(proj["slug"]) / f"{src_id}.pdf").unlink(missing_ok=True)
    for d in (storage.thumb_dir(proj["slug"]), storage.preview_dir(proj["slug"])):
        for f in d.glob(f"{src_id}-*.png"):
            f.unlink(missing_ok=True)
    save()
    view.refresh()


def add_packet():
    proj = S["proj"]
    proj["packets"].append(
        {"id": storage.new_id(), "name": f"Packet {len(proj['packets']) + 1}", "pages": []}
    )
    save()
    view.refresh()


def rename_packet(pk, value):
    pk["name"] = value or "Untitled"
    save()


def delete_packet(packet_id):
    proj = S["proj"]
    proj["packets"] = [p for p in proj["packets"] if p["id"] != packet_id]
    if not proj["packets"]:
        proj["packets"].append({"id": storage.new_id(), "name": "Packet 1", "pages": []})
    save()
    view.refresh()


def merge_packet(packet_id):
    proj = S["proj"]
    pk = find_packet(proj, packet_id)
    if not pk["pages"]:
        ui.notify("Packet is empty", type="warning")
        return
    fname = storage.slugify(pk["name"]) + ".pdf"
    out_path = storage.output_dir(proj["slug"]) / fname
    size = pdf_engine.merge_packet(pk["pages"], storage.source_dir(proj["slug"]), out_path)
    ui.notify(f"Merged '{pk['name']}' → {len(pk['pages'])} pages, {hsize(size)}", type="positive")
    ui.download(f"/pdfdata/{proj['slug']}/output/{fname}")


def merge_all():
    proj = S["proj"]
    done = [p for p in proj["packets"] if p["pages"]]
    if not done:
        ui.notify("Nothing to merge", type="warning")
        return
    for pk in done:
        fname = storage.slugify(pk["name"]) + ".pdf"
        out_path = storage.output_dir(proj["slug"]) / fname
        pdf_engine.merge_packet(pk["pages"], storage.source_dir(proj["slug"]), out_path)
    ui.notify(f"Merged {len(done)} packets → output/ folder", type="positive")


def switch_project(slug):
    S["proj"] = storage.load(slug)
    view.refresh()


def create_project_dialog():
    with ui.dialog() as dialog, ui.card().classes("p-6 gap-3"):
        ui.label("New project").classes("text-lg font-semibold")
        name = ui.input("Project name", placeholder="e.g. Q3 Filing").classes("w-72")
        with ui.row().classes("w-full justify-end gap-2"):
            ui.button("Cancel", on_click=dialog.close).props("flat")
            ui.button(
                "Create",
                on_click=lambda: (_create_and_close(name.value or "Untitled", dialog)),
            ).props("color=dark")
    dialog.open()


def _create_and_close(name, dialog):
    S["proj"] = storage.new_project(name)
    dialog.close()
    view.refresh()


# ---------------------------------------------------------------- UI
@ui.refreshable
def view():
    proj = S["proj"]

    # ---- top bar
    with ui.row().classes(
        "w-full items-center gap-4 px-6 py-3 bg-black text-white shadow-md"
    ):
        ui.icon("picture_as_pdf").classes("text-3xl text-white")
        ui.label("PDF Organizer").classes("text-xl font-bold")

        projects = storage.list_projects()
        ui.select(
            options={s: n for s, n in projects},
            value=proj["slug"],
            on_change=lambda e: switch_project(e.value),
        ).props("dark dense outlined").classes("min-w-48")

        ui.button(icon="add", on_click=create_project_dialog).props("flat round dense color=white").tooltip(
            "New project"
        )

        ui.space()

        ui.label(f"{len(proj['packets'])} packets").classes("text-gray-300")
        with ui.row().classes("items-center gap-1 bg-neutral-800 rounded-lg px-3 py-1"):
            ui.icon("data_usage").classes("text-white")
            ui.label(f"~{hsize(project_bytes(proj))} total").classes("font-semibold")

        ui.button("Merge all", icon="merge", on_click=merge_all).props("color=dark")

    # ---- editable project name
    with ui.row().classes("w-full items-center px-6 pt-4"):
        ui.input(value=proj["name"], on_change=lambda e: _rename_project(e.value)).props(
            "borderless"
        ).classes("text-2xl font-bold")

    # ---- board (horizontal scroll)
    with ui.row().classes("w-full flex-nowrap overflow-x-auto items-start gap-4 p-6"):
        for pk in proj["packets"]:
            render_packet(proj, pk)

        # add-packet tile
        with ui.column().classes(
            "w-72 shrink-0 items-center justify-center rounded-xl border-2 border-dashed "
            "border-gray-300 text-gray-400 cursor-pointer hover:border-gray-500 py-10"
        ).on("click", add_packet):
            ui.icon("add").classes("text-4xl")
            ui.label("Add packet")


def render_packet(proj, pk):
    pid = pk["id"]
    col = ui.column().classes(
        "w-72 shrink-0 bg-gray-100 rounded-xl shadow-sm p-3 gap-2 self-stretch"
    )
    col.on("dragover.prevent", lambda: None)
    col.on("drop", lambda e, pid=pid: do_move(pid, None))  # drop on empty space -> append

    with col:
        # header
        with ui.row().classes("w-full items-center gap-1 no-wrap"):
            ui.input(value=pk["name"], on_change=lambda e, pk=pk: rename_packet(pk, e.value)).props(
                "borderless dense"
            ).classes("font-semibold grow")
            ui.button(icon="merge", on_click=lambda e, pid=pid: merge_packet(pid)).props(
                "flat round dense size=sm color=dark"
            ).tooltip("Merge this packet")
            ui.button(icon="delete", on_click=lambda e, pid=pid: delete_packet(pid)).props(
                "flat round dense size=sm color=red"
            ).tooltip("Delete packet")

        # size + count badge
        with ui.row().classes("w-full items-center gap-2 text-xs text-gray-500 px-1"):
            ui.label(f"{len(pk['pages'])} pages")
            ui.label("·")
            ui.label(f"~{hsize(packet_bytes(proj, pk))}")

        # page cards — compact 2-col grid, scrolls within the column
        if not pk["pages"]:
            ui.label("Drop pages here or add a PDF").classes(
                "text-xs text-gray-400 italic w-full text-center py-6"
            )
        else:
            with ui.grid(columns=1).classes("w-full gap-1 max-h-[62vh] overflow-y-auto pr-1"):
                for i, pg in enumerate(pk["pages"]):
                    render_card(proj, pid, i, pg)

        # add-PDF uploader
        ui.upload(
            multiple=True,
            auto_upload=True,
            on_upload=lambda e, pid=pid: handle_upload(e, pid),
            label="+ Add PDF",
        ).props("accept=.pdf flat dense color=dark").classes("w-full")


def render_card(proj, packet_id, index, pg):
    src = proj["sources"].get(pg["src"], {})
    card = ui.card().classes(
        "relative p-0 overflow-hidden cursor-pointer bg-white rounded shadow-sm "
        "hover:shadow-md hover:ring-2 hover:ring-gray-400 transition"
    )
    card.props("draggable")
    card.on("dragstart", lambda e, pid=packet_id, i=index: set_drag(pid, i))
    card.on("dragover.prevent", lambda: None)
    card.on("drop.stop", lambda e, pid=packet_id, i=index: do_move(pid, i))  # insert before
    card.on("click", lambda e, pid=packet_id, i=index: open_preview(pid, i))  # click -> full page
    card.tooltip(f"{src.get('filename', '?')} · p{pg['page'] + 1}")
    with card:
        # full page shown top-to-bottom at the PDF's natural aspect ratio
        ui.html(
            f'<img src="{thumb_url(proj, pg)}" '
            f'style="display:block;width:100%;height:auto;background:#f9fafb;" />',
            sanitize=False,
        )
        # overlay title: original document name + page number, so moved pages stay traceable
        ui.label(f"{src.get('filename', '?')} · p{pg['page'] + 1}").classes(
            "absolute top-0 left-0 right-0 bg-black/60 text-white text-[10px] leading-tight "
            "px-1 py-0.5 truncate"
        )


def open_preview(packet_id, index):
    """Lightbox: full-size page with prev/next + X close (Esc also closes)."""
    proj = S["proj"]
    pk = find_packet(proj, packet_id)
    if not pk or not pk["pages"]:
        return
    st = {"i": index}

    with ui.dialog().props("maximized") as dialog, ui.card().classes(
        "bg-black text-white w-full h-full p-0 gap-0 items-stretch"
    ):
        # top bar
        with ui.row().classes("w-full items-center no-wrap gap-2 px-4 py-2 bg-black"):
            cap = ui.label().classes("text-sm truncate grow")
            ui.button("Delete", icon="delete", on_click=lambda: confirm_delete()).props(
                "color=red dense"
            )
            ui.button(icon="close", on_click=dialog.close).props("flat round dense color=white")

        # full-page image, centered, fills remaining height
        with ui.row().classes("w-full grow items-center justify-center overflow-auto bg-black"):

            @ui.refreshable
            def big_image():
                pg = pk["pages"][st["i"]]
                url = ensure_preview(proj, pg)
                ui.html(
                    f'<img src="{url}" style="max-height:82vh;max-width:94vw;'
                    f'object-fit:contain;display:block;margin:auto;border-radius:4px;" />',
                    sanitize=False,
                )

            big_image()

        def update_caption():
            pg = pk["pages"][st["i"]]
            src = proj["sources"].get(pg["src"], {})
            cap.text = (
                f"{src.get('filename', '?')} · page {pg['page'] + 1}"
                f"   ({st['i'] + 1} / {len(pk['pages'])})"
            )

        update_caption()

        def go(delta):
            st["i"] = max(0, min(len(pk["pages"]) - 1, st["i"] + delta))
            big_image.refresh()
            update_caption()

        def del_this_page():
            pk["pages"].pop(st["i"])
            save()
            view.refresh()
            if not pk["pages"]:
                dialog.close()
                return
            st["i"] = min(st["i"], len(pk["pages"]) - 1)
            big_image.refresh()
            update_caption()

        def del_whole_document(src_id):
            delete_document(src_id)  # removes across all packets + files, refreshes board
            dialog.close()

        def confirm_delete():
            pg = pk["pages"][st["i"]]
            src = proj["sources"].get(pg["src"], {})
            total = sum(
                1 for P in proj["packets"] for p2 in P["pages"] if p2["src"] == pg["src"]
            )
            with ui.dialog() as cd, ui.card().classes("p-5 gap-3 min-w-80"):
                ui.label("Delete what?").classes("text-lg font-semibold text-black")
                ui.label(
                    f'Currently viewing page {pg["page"] + 1} of "{src.get("filename", "?")}"'
                ).classes("text-sm text-gray-500")
                ui.button(
                    "Delete this page only",
                    icon="delete",
                    on_click=lambda: (cd.close(), del_this_page()),
                ).props("color=red").classes("w-full")
                ui.button(
                    f"Delete whole document ({total} pages)",
                    icon="delete_forever",
                    on_click=lambda src_id=pg["src"]: (cd.close(), del_whole_document(src_id)),
                ).props("color=red outline").classes("w-full")
                ui.button("Cancel", on_click=cd.close).props("flat").classes("w-full")
            cd.open()

        with ui.row().classes("w-full justify-center gap-6 pb-1"):
            ui.button("Prev", icon="chevron_left", on_click=lambda: go(-1)).props("flat color=white")
            ui.button("Next", icon="chevron_right", on_click=lambda: go(1)).props("flat color=white")

    dialog.open()


def _rename_project(value):
    S["proj"]["name"] = value or "Untitled"
    save()


# ---------------------------------------------------------------- bootstrap
def init():
    projects = storage.list_projects()
    S["proj"] = storage.load(projects[0][0]) if projects else storage.new_project("My First Project")
    view()


@ui.page("/")
def index():
    ui.add_head_html("<style>.nicegui-content{padding:0}</style>")
    init()


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(title="PDF Organizer", port=8080, reload=False, show=True, favicon="📄")
