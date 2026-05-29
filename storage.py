"""NIW Petition Builder v2 — persistence.

Project layout:
  projects/<slug>/
    project.json     state (tabs, packets, exhibits, sources, petitioner)
    source/*.pdf     copies of uploaded PDFs (one per source document)
    thumbs/*.png     per-page thumbnails
    preview/*.png    large preview images (lazy-rendered)
    output/*.pdf     merged packet files + master index

Schema:
{
  "name":       project display name,
  "slug":       folder slug,
  "petitioner": petitioner full name (printed on cover sheets / master index),
  "size_limit_mb": 12,
  "sources":    { src_id: {filename, page_count, bytes} },
  "tabs":       [ { id, letter, key, name, hint,
                    packets: [ { id, name,
                                 exhibits: [ {id, src_id, title, summary,
                                              cover_paragraph,
                                              ai_meta:{suggested_tab,...}} ] } ] } ]
}

Migrates v1 niw projects (sections schema) and pre-niw projects (packets schema) by
landing every existing source as a placeholder exhibit in tab A packet A1; the user
can drag them to the right tab via the TOC.
"""
import json
import re
import uuid
from pathlib import Path

import niw_template

PROJECTS_DIR = Path(__file__).parent / "projects"


def slugify(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_-]+", "-", name.strip()).strip("-").lower()
    return s or "petition"


def new_id() -> str:
    return uuid.uuid4().hex[:8]


def project_dir(slug: str) -> Path:
    return PROJECTS_DIR / slug


def source_dir(slug: str) -> Path:
    return project_dir(slug) / "source"


def thumb_dir(slug: str) -> Path:
    return project_dir(slug) / "thumbs"


def preview_dir(slug: str) -> Path:
    return project_dir(slug) / "preview"


def output_dir(slug: str) -> Path:
    return project_dir(slug) / "output"


def list_projects():
    if not PROJECTS_DIR.exists():
        return []
    out = []
    for d in PROJECTS_DIR.iterdir():
        f = d / "project.json"
        if f.is_file():
            try:
                out.append((d.name, json.loads(f.read_text())["name"]))
            except Exception:
                pass
    return sorted(out, key=lambda t: t[1].lower())


def _unique_slug(base: str) -> str:
    slug, n = base, 2
    while (PROJECTS_DIR / slug).exists():
        slug = f"{base}-{n}"
        n += 1
    return slug


def new_project(name: str, petitioner: str = "") -> dict:
    slug = _unique_slug(slugify(name))
    proj = {
        "name": name,
        "slug": slug,
        "petitioner": petitioner or name,
        "size_limit_mb": 12,
        "sources": {},
        "tabs": niw_template.new_tabs(),
    }
    save(proj)
    return proj


def load(slug: str) -> dict:
    proj = json.loads((project_dir(slug) / "project.json").read_text())
    proj = _migrate_if_needed(proj)
    return proj


def save(proj: dict) -> None:
    d = project_dir(proj["slug"])
    d.mkdir(parents=True, exist_ok=True)
    (d / "project.json").write_text(json.dumps(proj, indent=2))


# ---------------------------------------------------------------- migration
def _migrate_if_needed(proj: dict) -> dict:
    """Handle two earlier schemas: v1 niw `sections` and pre-niw `packets`."""
    if "tabs" in proj and "sections" not in proj and "packets" not in proj:
        proj.setdefault("petitioner", proj.get("name", ""))
        proj.setdefault("size_limit_mb", 12)
        return proj

    new = {
        "name": proj.get("name", "Untitled Petition"),
        "slug": proj["slug"],
        "petitioner": proj.get("petitioner") or proj.get("name", ""),
        "size_limit_mb": proj.get("size_limit_mb", 12),
        "sources": proj.get("sources", {}),
        "tabs": niw_template.new_tabs(),
    }

    # land every prior source as a placeholder exhibit in A1 (user drags to right tab)
    a_pkt = new["tabs"][0]["packets"][0]
    seen = set()

    if "sections" in proj:  # v1 niw schema
        for sec in proj["sections"]:
            for slot in sec["slots"]:
                for ex in slot["exhibits"]:
                    sid = ex["src_id"]
                    if sid in seen:
                        continue
                    seen.add(sid)
                    a_pkt["exhibits"].append(
                        {
                            "id": new_id(),
                            "src_id": sid,
                            "title": ex.get("label") or new["sources"].get(sid, {}).get("filename", "Document"),
                            "summary": "",
                            "cover_paragraph": ex.get("rationale", ""),
                            "ai_meta": {},
                        }
                    )
    elif "packets" in proj:  # pre-niw schema
        for pk in proj["packets"]:
            for pg in pk.get("pages", []):
                sid = pg["src"]
                if sid in seen:
                    continue
                seen.add(sid)
                a_pkt["exhibits"].append(
                    {
                        "id": new_id(),
                        "src_id": sid,
                        "title": new["sources"].get(sid, {}).get("filename", "Document").removesuffix(".pdf"),
                        "summary": "",
                        "cover_paragraph": "",
                        "ai_meta": {},
                    }
                )

    save(new)
    return new


# ---------------------------------------------------------------- helpers
def find_tab(proj, tab_id):
    return next((t for t in proj["tabs"] if t["id"] == tab_id), None)


def find_packet(proj, packet_id):
    for t in proj["tabs"]:
        for p in t["packets"]:
            if p["id"] == packet_id:
                return t, p
    return None, None


def find_exhibit(proj, exhibit_id):
    for t in proj["tabs"]:
        for p in t["packets"]:
            for ex in p["exhibits"]:
                if ex["id"] == exhibit_id:
                    return t, p, ex
    return None, None, None


def iter_exhibits(proj):
    """Yield (tab, packet, exhibit, exhibit_number) in petition order."""
    n = 0
    for t in proj["tabs"]:
        for p in t["packets"]:
            for ex in p["exhibits"]:
                n += 1
                yield t, p, ex, n
