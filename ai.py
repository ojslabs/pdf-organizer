"""Anthropic Claude client for NIW Petition Builder.

Tasks:
  1. classify_document(text) -> {title, summary, suggested_tab, cover_paragraph}
     Runs Claude Haiku 4.5 with a JSON-output prompt to identify the uploaded
     document, classify it into one of the seven NIW tabs (A–G), and draft a
     formal-legal cover-sheet paragraph.
  2. connection_test() -> (ok: bool, message: str)
     Pings Anthropic with a trivial completion to confirm credentials work.

The Anthropic API key is read from the ANTHROPIC_API_KEY environment variable
(loaded from .env via python-dotenv at app startup).
"""
from __future__ import annotations

import json
import os
import re
from typing import Optional

import niw_template

MODEL = "claude-haiku-4-5-20251001"
MAX_TEXT_CHARS = 3000


def have_key() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _client():
    import anthropic

    return anthropic.Anthropic()


def connection_test() -> tuple[bool, str]:
    """Send a tiny completion to verify the API key + network. Returns (ok, msg)."""
    if not have_key():
        return False, "ANTHROPIC_API_KEY not set in environment (.env)"
    try:
        client = _client()
        msg = client.messages.create(
            model=MODEL,
            max_tokens=8,
            messages=[{"role": "user", "content": "Reply with the single word: ok"}],
        )
        text = "".join(b.text for b in msg.content if hasattr(b, "text"))
        return True, f"Anthropic API reachable ({MODEL}). Reply: {text.strip()[:40]}"
    except Exception as e:
        return False, f"Anthropic API error: {type(e).__name__}: {e}"


def classify_document(text: str, filename: str = "") -> dict:
    """Classify one uploaded document. Returns dict with keys
    title, summary, suggested_tab, cover_paragraph. Raises on hard failure.

    The caller is responsible for handling missing API key / quota errors.
    """
    text = (text or "").strip()
    if not text:
        # caller probably wants to handle this differently (OCR fallback first)
        raise ValueError("No text extracted from document")
    snippet = text[:MAX_TEXT_CHARS]
    user_content = (
        f"Document filename: {filename or '(unknown)'}\n\n"
        f"Document text (first {len(snippet)} characters):\n---\n{snippet}\n---"
    )
    client = _client()
    msg = client.messages.create(
        model=MODEL,
        max_tokens=600,
        system=niw_template.AI_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )
    raw = "".join(b.text for b in msg.content if hasattr(b, "text")).strip()
    return _parse_json_response(raw)


def _parse_json_response(raw: str) -> dict:
    """Tolerant JSON parse: strip markdown fences if Claude wrapped output."""
    raw = raw.strip()
    # strip ```json ... ``` fences if present
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    data = json.loads(raw)
    # validate required keys
    out = {
        "title": str(data.get("title", "")).strip() or "Untitled exhibit",
        "summary": str(data.get("summary", "")).strip(),
        "suggested_tab": str(data.get("suggested_tab", "")).strip().upper()[:1] or "A",
        "cover_paragraph": str(data.get("cover_paragraph", "")).strip(),
    }
    if out["suggested_tab"] not in [t["letter"] for t in niw_template.TABS]:
        out["suggested_tab"] = "A"
    return out
