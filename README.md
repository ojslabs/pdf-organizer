# PDF Organizer

Local, browser-based tool to organize PDFs into **packets** and merge each packet
into a single PDF. Page-level: every uploaded PDF explodes into draggable page
thumbnails you can reorder within a packet or move between packets.

- **Project** = a set of packets
- **Packet** = an ordered list of pages → merges to one output PDF
- Drag page cards within a column to reorder, across columns to move
- Live total-size estimate; exact size reported on merge
- Auto-saves to `projects/<slug>/project.json`

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
python app.py
```

Opens http://localhost:8080.

## Where files live

```
projects/<slug>/
  project.json     state (packets, page order, sources)
  source/*.pdf     copies of uploaded PDFs
  thumbs/*.png     cached page thumbnails
  output/*.pdf     merged results
```

Merged PDFs download automatically and are kept in `output/`.

## Notes

- Total size is an estimate (sum of source bytes weighted per page). The **exact**
  merged size is shown when you merge a packet.
- Uses PyMuPDF (AGPL) — fine for local personal use.
