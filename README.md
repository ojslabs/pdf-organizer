# NIW Petition Builder

A local, browser-based assembler for **EB-2 National Interest Waiver (I-140)** petitions. Drops every required, recommended, and optional document into clearly labeled slots — built around USCIS guidance and *Matter of Dhanasar*, 26 I&N Dec. 884 (AAO 2016). Generates per-exhibit cover sheets and a master exhibit index, packs each section into a single ≤12MB PDF ready for myUSCIS upload, and shows your required-document completeness at a glance.

**Runs entirely on your own computer. No accounts, no cloud, no uploads to anyone. Your files never leave your machine.**

## What it gives you

- **Eight standard NIW sections** seeded into every new project:
  1. Petition Letter & Forms
  2. Identity & Immigration Status
  3. EB-2 Eligibility (advanced degree or exceptional ability)
  4. Prong 1 — Substantial Merit & National Importance
  5. Prong 2 — Well Positioned to Advance the Endeavor
  6. Recommendation Letters
  7. Prong 3 — Balancing Factors
  8. Additional Supporting Evidence
- **42 named upload slots** covering every document USCIS expects or attorneys typically include. Each slot is tagged **Required / Recommended / Conditional / Optional** with an attorney-grade description.
- **Live completeness tracker** ("Required: 7/9 ✓") in the top bar.
- **12MB-per-file governor** — colored size bar (green → amber ≥90% → red over) computed by **building the actual PDF** in the background, not a rough estimate.
- **Auto-generated exhibit cover sheets** prepended to every exhibit ("EXHIBIT 4 — Letter from Dr. Wu, Rigetti Computing" with a rationale paragraph the officer reads).
- **Master Exhibit Index** PDF — one-click generation, lists every exhibit with section and file/page location.
- **Export All** — builds all section PDFs (`01_petition_letter_and_forms.pdf`, `02_identity_and_immigration_status.pdf`, …) ready for upload.
- **Drag-and-drop reorder** within and across slots. Click any exhibit for a full-page preview; rationale and exhibit title are editable per exhibit.
- **Auto-saves** every change to disk.

## Requirements

- **Python 3.9 or newer**
- A web browser

Dependencies ([NiceGUI](https://nicegui.io) for the UI, [PyMuPDF](https://pymupdf.readthedocs.io) for PDF work) install automatically.

## Quick start

### Mac / Linux
```bash
./run.sh
```

### Windows
```bat
run.bat
```

Opens **http://localhost:8080**. To stop, press `Ctrl+C` in the terminal. Your work is already saved.

### Manual
```bash
python3 -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

## How to use

1. Create a new petition (top-right `+`). Enter the project name and the petitioner's full name.
2. Scroll through the eight sections. For every required slot (red badge), upload the document via **+ Add document**.
3. Click any exhibit thumbnail to see it full-page; click **Edit** in the preview to customize the exhibit title and the rationale paragraph that will appear on the auto-generated cover sheet.
4. Drag exhibits to reorder within a slot, or move them between slots/sections.
5. As you fill slots, each section's size bar updates with the **exact** merged file size. If a section turns red (>12MB), split a document out before uploading.
6. Click **Master Index** to generate the cross-file exhibit index. Click **Export All** to produce every section PDF + the master index in the `projects/<slug>/output/` folder, ready to upload to myUSCIS.

## USCIS online-filing constraints handled

- **12MB max per uploaded file** (myUSCIS limit).
- **PDF format only** for documents.
- **No encryption / password protection.** Merged outputs are produced unencrypted.
- **Logical organization with a master index** across the multi-file upload set, as recommended by practitioners (see, e.g., *USCIS Online Filing for EB-1A and EB-2 NIW I-140s*, Stelmakh Law).

Sources:
- [USCIS — Tips for Filing Forms Online](https://www.uscis.gov/file-online/tips-for-filing-forms-online)
- [Stelmakh Law — USCIS Online Filing for EB-1A and EB-2 NIW I-140s](https://stelmakhlaw.com/blog/uscis-online-filing/)
- *Matter of Dhanasar*, 26 I&N Dec. 884 (AAO 2016)

## Where your data lives

```
projects/<your-petition>/
  project.json     state (sections, slots, exhibits)
  source/*.pdf     copies of uploaded PDFs
  thumbs/*.png     page thumbnails
  preview/*.png    full-page previews (rendered on demand)
  output/*.pdf     merged section PDFs + master index
```

To back up: copy the `projects/` folder. To start fresh: delete it. Git-ignored, so it never gets committed.

## Disclaimer

This tool helps organize and assemble a petition. It does not provide legal advice and does not substitute for a licensed immigration attorney's review of your specific circumstances. Sample rationale text on cover sheets is a starting point; review and customize each one to your case.

## License

MIT — see [LICENSE](LICENSE).
