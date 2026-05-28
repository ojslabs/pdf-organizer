"""NIW petition project persistence.

A project = one EB-2 NIW I-140 petition. Stored on disk as a folder per project.

  projects/<slug>/
    project.json        sections + slots + exhibits + sources
    source/*.pdf        copies of uploaded PDFs (one per source document)
    thumbs/*.png        page-1 thumbnails (one per source document)
    preview/*.png       large preview images (rendered on demand)
    output/*.pdf        merged section files (NN_section_name.pdf) + master index

Schema (project.json):
{
  "name":       "Display name of the project",
  "slug":       "url/folder slug",
  "petitioner": "Petitioner full name (printed on cover sheets / index)",
  "size_limit_mb": 12,
  "sources":    { src_id: {filename, page_count, bytes} },
  "sections":   [ { id, key, name, hint,
                    slots: [ { id, key, name, requirement, description, rationale,
                               exhibits: [ {id, src_id, label, rationale} ] } ] } ]
}

Old format (pre-NIW) had `packets: [{id, name, pages:[...]}]`. `load()` auto-migrates.
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
        "sections": niw_template.new_sections(),
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
    """Migrate pre-NIW projects (with 'packets' instead of 'sections') into NIW shape."""
    if "sections" in proj and "packets" not in proj:
        # already NIW-shaped, ensure defaults
        proj.setdefault("petitioner", proj.get("name", ""))
        proj.setdefault("size_limit_mb", 12)
        return proj

    # build a fresh NIW skeleton
    new = {
        "name": proj.get("name", "Untitled Petition"),
        "slug": proj["slug"],
        "petitioner": proj.get("name", ""),
        "size_limit_mb": 12,
        "sources": proj.get("sources", {}),
        "sections": niw_template.new_sections(),
    }

    # land every previously-organized document as its own exhibit in
    # Section 8 (Additional Supporting Evidence) so nothing is lost
    additional = next(s for s in new["sections"] if s["key"] == "additional")
    bucket = additional["slots"][0]
    seen_srcs = set()
    for pk in proj.get("packets", []):
        for pg in pk.get("pages", []):
            sid = pg["src"]
            if sid in seen_srcs:
                continue
            seen_srcs.add(sid)
            src = new["sources"].get(sid, {})
            label = src.get("filename", "Unsorted document")
            bucket["exhibits"].append(
                {
                    "id": new_id(),
                    "src_id": sid,
                    "label": label,
                    "rationale": (
                        "Migrated from a previous version of the project. "
                        "Please re-categorize into the appropriate NIW section."
                    ),
                }
            )

    save(new)
    return new


# ---------------------------------------------------------------- helpers used by app
def find_slot(proj, slot_id):
    for s in proj["sections"]:
        for slot in s["slots"]:
            if slot["id"] == slot_id:
                return s, slot
    return None, None


def find_exhibit(proj, exhibit_id):
    for s in proj["sections"]:
        for slot in s["slots"]:
            for ex in slot["exhibits"]:
                if ex["id"] == exhibit_id:
                    return s, slot, ex
    return None, None, None


def iter_exhibits(proj):
    """Yield (section, slot, exhibit, exhibit_number) in petition order."""
    n = 0
    for s in proj["sections"]:
        for slot in s["slots"]:
            for ex in slot["exhibits"]:
                n += 1
                yield s, slot, ex, n
