"""Project persistence: one folder per project, JSON state, auto-saved on every change.

Layout:
  projects/<slug>/project.json     state (packets, page order, sources)
  projects/<slug>/source/*.pdf     copies of uploaded PDFs
  projects/<slug>/thumbs/*.png     cached page thumbnails (<src>-<page>.png)
  projects/<slug>/output/*.pdf     merged results
"""
import json
import re
import uuid
from pathlib import Path

PROJECTS_DIR = Path(__file__).parent / "projects"


def slugify(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_-]+", "-", name.strip()).strip("-").lower()
    return s or "project"


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
    """Return [(slug, display_name), ...] sorted by name."""
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


def new_project(name: str) -> dict:
    slug = _unique_slug(slugify(name))
    proj = {
        "name": name,
        "slug": slug,
        "sources": {},  # src_id -> {filename, page_count, bytes}
        "packets": [{"id": new_id(), "name": "Packet 1", "pages": []}],
    }
    save(proj)
    return proj


def load(slug: str) -> dict:
    return json.loads((project_dir(slug) / "project.json").read_text())


def save(proj: dict) -> None:
    d = project_dir(proj["slug"])
    d.mkdir(parents=True, exist_ok=True)
    (d / "project.json").write_text(json.dumps(proj, indent=2))
