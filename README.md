# PDF Organizer

A simple, local tool to organize PDFs into **packets** and merge each packet into a
single PDF. Runs entirely on your own computer in your browser — **no accounts, no
cloud, no uploads to anyone**. Your files never leave your machine.

Built for the common chore of assembling one big PDF out of many: applications,
filings, portfolios, submission packets, anything where you gather pages from several
PDFs and arrange them just so.

## What it does

- **Projects → packets → pages.** A *project* holds multiple *packets* (columns).
  Each packet is an ordered list of pages that merges into one output PDF.
- **Page-level control.** Every PDF you add explodes into individual page
  thumbnails. Drag pages to reorder within a packet, or drag them between packets.
- **Always know the source.** Each page shows a label with its original document
  name and page number, so pages stay traceable after you move them.
- **Click to expand.** Click any page for a full-size preview with prev/next.
- **Delete safely.** Delete a single page or a whole document, with confirmation.
- **Track size.** Live size estimate per packet and for the whole project; exact
  size reported when you merge.
- **Auto-saves.** Every change is written to disk immediately. Close it anytime.

## Requirements

- **Python 3.9 or newer**
- A web browser

That's it. Dependencies ([NiceGUI](https://nicegui.io) and
[PyMuPDF](https://pymupdf.readthedocs.io)) install automatically via the launcher.

## Quick start

### Mac / Linux
```bash
./run.sh
```

### Windows
```bat
run.bat
```

The launcher creates a virtual environment, installs dependencies, and starts the
app. When it's running, open **http://localhost:8080** in your browser.

To stop it, press `Ctrl+C` in the terminal. Your work is already saved.

### Manual start (if you prefer)
```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

## How to use

1. The app opens with a starter project. Click **+ Add PDF** at the bottom of a
   packet to add a file — its pages appear as thumbnails.
2. **Drag** pages to reorder them, or drag them into another packet.
3. **Click** a page to see it full-size; use Prev/Next or the X to close.
4. Use **+ New Packet** to split work into sections, and the top bar to create or
   switch between projects.
5. Click **Merge** on a packet to produce its combined PDF (or **Merge all**).
   Merged files download automatically and are saved under `projects/`.

## Where your data lives

Everything is stored locally in a `projects/` folder next to the app:

```
projects/<your-project>/
  project.json     project state (packets, page order)
  source/*.pdf      copies of the PDFs you added
  thumbs/*.png      page thumbnails
  preview/*.png     full-size previews
  output/*.pdf      merged results
```

To back up or move your work, copy the `projects/` folder. To start fresh, delete it.
This folder is git-ignored, so it never gets committed or shared.

## Notes

- Size shown in the UI is an estimate (source bytes weighted per page). The exact
  merged size is reported when you merge a packet.
- Uses PyMuPDF, which is AGPL-licensed — fine for personal/local use.

## License

MIT — see [LICENSE](LICENSE).
