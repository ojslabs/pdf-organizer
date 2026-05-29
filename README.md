# NIW Petition Builder

A local, browser-based **AI-assisted assembler for EB-2 National Interest Waiver (I-140)** petitions. Drop your PDFs in, Claude reads each one and classifies it into the right NIW tab, writes a formal-legal exhibit cover sheet, and you reorder everything from a single Table of Contents. Per-tab packets stay under the 12MB-per-file myUSCIS upload limit with an exact-size governor.

Branch `niw-v2` of github.com/ojslabs/pdf-organizer. The `main` branch holds the generic page-level PDF organizer; the `niw` branch holds the v1 8-section NIW builder.

**Runs entirely on your own computer.** The only thing that leaves your machine is the first ~3000 characters of each uploaded PDF, sent to Anthropic's Claude API for classification + cover-letter drafting. PDFs themselves stay local.

## What's inside

- **Seven fixed NIW tabs** (A–G) matching the standard exhibit organization under *Matter of Dhanasar*, 26 I&N Dec. 884 (AAO 2016):
  A · Petition Letter · B · Qualifying Advanced Degree · C · Substantial Merit and National Importance · D · Well Positioned to Advance the Proposed Endeavor · E · On Balance Beneficial to the United States · F · Recommendation Letters · G · Identity and Immigration Documents.
- **Multiple packets per tab** so you can fit each upload file under 12MB. Add / reorder / rename / delete packets per tab.
- **TOC-driven assembly.** Drag exhibits within or across packets/tabs; ↑↓ buttons reorder packets within a tab. Continuous exhibit numbering (Ex 1, Ex 2, ...) recomputes automatically.
- **AI classification on upload.** Claude reads the document, suggests the tab (A–G), drafts a 5–10 word title, and writes a 3–5 sentence formal-legal cover paragraph. You review and accept/edit each one before it lands.
- **OCR fallback** (Tesseract) for image-only PDFs.
- **Exact 12MB-per-packet governor.** Color size bar (green / amber / red) computed by **building the actual merged PDF** in a background thread, not estimating.
- **Cover sheets prepended at merge time** — one page per exhibit, regenerated whenever you edit the title or paragraph.
- **Master Exhibit Index** PDF — one-click TOC across the whole upload set.
- **Export All** — produces every packet PDF (`A1_petition_letter.pdf`, `A2_…`, `B1_…`) plus the master index, ready to upload to myUSCIS in order.
- **Read-only visual preview** below the TOC: every exhibit's thumbnail, click to expand to full-page view.
- **Auto-saves** every change to disk.

## Requirements

- **Python 3.9 or newer**
- A web browser
- An **Anthropic API key** (https://console.anthropic.com). Optional but heavily recommended — the AI classification + cover-letter drafting is the headline feature. Without a key uploads still work; you title and write cover paragraphs by hand.
- **Tesseract** (optional; only needed for OCR of image-only PDFs):
  - macOS: `brew install tesseract`
  - Ubuntu/Debian: `sudo apt install tesseract-ocr`

## Setup

```bash
# 1. clone
git clone https://github.com/ojslabs/pdf-organizer.git
cd pdf-organizer
git switch niw-v2

# 2. install (one-time)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. configure API key
cp .env.example .env
# edit .env, paste your key after ANTHROPIC_API_KEY=
```

## Run

```bash
./run.sh        # mac/linux
run.bat         # windows
```

Opens http://localhost:8080. Press Ctrl+C to stop. Your work auto-saves.

## How to use

1. Click **+** in the top bar to create a new petition. Enter the project + petitioner name.
2. Drag PDFs into the **Upload documents** card at the top of the TOC. AI processes them in parallel.
3. For each file, a review dialog opens showing the AI's suggested **title**, **tab**, and **cover-sheet paragraph**. Edit anything, accept, or discard.
4. Each accepted exhibit lands in the last packet of its assigned tab. Drag it to reorder within or move between packets/tabs. Use the **↑↓** buttons to reorder packets within a tab. Click **+ Packet** on any tab to add another packet inside it (for the 12MB limit).
5. Each packet's **size bar** turns green / amber / red as you add exhibits. When it goes red, split exhibits into a new packet inside the same tab.
6. Click an exhibit's **Edit** to revise the title / cover paragraph, or **Regenerate with AI** to redraft from the source PDF.
7. Click **Master Index** to produce the cross-file exhibit TOC PDF.
8. Click **Export All** to build every packet PDF + the master index into `projects/<slug>/output/`, named `A1_…pdf`, `A2_…pdf`, `B1_…pdf` etc. — upload them to myUSCIS in name order.

## USCIS rules the tool enforces

- **12MB max per uploaded file.** Exact merged byte size shown per packet; red over-limit warning on merge.
- **PDF-only outputs.** No password protection or encryption.
- Logical multi-file organization with a master index across the upload set, as practitioners recommend (see e.g. *USCIS Online Filing for EB-1A and EB-2 NIW I-140s*, Stelmakh Law).

Sources:
- [USCIS — Tips for Filing Forms Online](https://www.uscis.gov/file-online/tips-for-filing-forms-online)
- [Stelmakh Law — USCIS Online Filing for EB-1A and EB-2 NIW I-140s](https://stelmakhlaw.com/blog/uscis-online-filing/)
- *Matter of Dhanasar*, 26 I&N Dec. 884 (AAO 2016)

## Where your data lives

```
projects/<your-petition>/
  project.json     state (tabs, packets, exhibits, sources, petitioner)
  source/*.pdf     copies of uploaded PDFs
  thumbs/*.png     page-1 thumbnails
  preview/*.png    full-page previews (rendered on demand)
  output/*.pdf     merged packet PDFs + master index
```

To back up: copy the `projects/` folder. To start fresh: delete it. Git-ignored, never committed.

## What's sent to Anthropic

For each upload: the first ~3000 characters of extracted text, the original filename, and the seven-tab prompt template. Anthropic's API privacy and retention policies apply.

If `ANTHROPIC_API_KEY` is missing, AI features no-op gracefully; uploads still land, you fill in title and cover paragraph manually.

## Disclaimer

This tool helps organize and assemble a petition. It does not provide legal advice and does not substitute for a licensed immigration attorney's review of your specific circumstances. AI-generated cover-letter text is a starting point; review and customize each one to your case.

## License

MIT — see [LICENSE](LICENSE).
