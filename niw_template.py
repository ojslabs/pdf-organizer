"""NIW Petition Builder v2 — tab definitions.

Seven fixed tabs (A–G) following the standard EB-2 NIW exhibit organization
under Matter of Dhanasar, 26 I&N Dec. 884 (AAO 2016). Each tab holds one or
more packets; each packet is one ≤12MB myUSCIS upload file; each packet holds
ordered exhibits (one source PDF per exhibit).
"""

TABS = [
    {
        "letter": "A",
        "key": "petition_letter",
        "name": "Petition Letter",
        "hint": (
            "The legal brief arguing the three Dhanasar prongs, plus required "
            "USCIS forms (I-140, G-28, I-907)."
        ),
    },
    {
        "letter": "B",
        "key": "qualifying_degree",
        "name": "Qualifying Advanced Degree",
        "hint": (
            "Evidence the petitioner qualifies for the EB-2 category — diplomas, "
            "transcripts, foreign credential evaluations, or the Bachelor's-plus-5-"
            "years-experience equivalency package."
        ),
    },
    {
        "letter": "C",
        "key": "substantial_merit",
        "name": "Substantial Merit and National Importance",
        "hint": (
            "Dhanasar Prong 1 evidence: statement of proposed endeavor and "
            "documentation that the field has substantial merit and is of "
            "national importance."
        ),
    },
    {
        "letter": "D",
        "key": "well_positioned",
        "name": "Well Positioned to Advance the Proposed Endeavor",
        "hint": (
            "Dhanasar Prong 2 evidence: CV, publications, citations, patents, "
            "awards, media coverage, memberships, grants, evidence of adoption."
        ),
    },
    {
        "letter": "E",
        "key": "on_balance",
        "name": "On Balance Beneficial to the United States",
        "hint": (
            "Dhanasar Prong 3 evidence: argument and support that waiving the "
            "job-offer and labor-certification requirements benefits the U.S."
        ),
    },
    {
        "letter": "F",
        "key": "recommendation_letters",
        "name": "Recommendation Letters",
        "hint": (
            "Independent and dependent expert letters attesting to the "
            "petitioner's qualifications and the field's importance."
        ),
    },
    {
        "letter": "G",
        "key": "identity",
        "name": "Identity and Immigration Documents",
        "hint": (
            "Passport, visas, I-94, current and prior I-797 notices, EAD, "
            "birth certificate."
        ),
    },
]


# Mapping used in the AI prompt: letter -> short description for the model
TAB_LABELS_FOR_AI = {t["letter"]: f"{t['name']} — {t['hint']}" for t in TABS}


def tab_letters():
    return [t["letter"] for t in TABS]


def find_tab_def(letter):
    return next((t for t in TABS if t["letter"] == letter), None)


def new_tabs():
    """Build a fresh empty tabs list (one default packet per tab) with new ids."""
    import uuid

    def nid():
        return uuid.uuid4().hex[:8]

    out = []
    for t in TABS:
        out.append(
            {
                "id": nid(),
                "letter": t["letter"],
                "key": t["key"],
                "name": t["name"],
                "hint": t["hint"],
                "packets": [
                    {
                        "id": nid(),
                        "name": f"{t['letter']}1",
                        "exhibits": [],
                    }
                ],
            }
        )
    return out


# ---------------------------------------------------------------- AI prompt
AI_SYSTEM_PROMPT = """You are a paralegal assistant for an EB-2 National Interest Waiver \
(I-140) petition. You will be given the first ~3000 characters of an uploaded PDF document. \
Identify what the document is, classify it into one of the seven NIW exhibit tabs, and \
write a brief formal-legal cover-sheet paragraph explaining its relevance.

The tabs are:
A — Petition Letter (legal brief + USCIS forms)
B — Qualifying Advanced Degree (diplomas, transcripts, credential evaluation)
C — Substantial Merit and National Importance (Dhanasar Prong 1)
D — Well Positioned to Advance the Proposed Endeavor (Dhanasar Prong 2: CV, publications, awards, etc.)
E — On Balance Beneficial to the United States (Dhanasar Prong 3)
F — Recommendation Letters (independent and dependent expert letters)
G — Identity and Immigration Documents (passport, visa, I-94, I-797, EAD, etc.)

Respond with ONLY a JSON object, no surrounding text, in this exact shape:

{
  "title": "5–10 word descriptive title (used as the exhibit label)",
  "summary": "One short paragraph internal summary of what the document is.",
  "suggested_tab": "single letter A through G",
  "cover_paragraph": "3–5 sentence formal-legal paragraph explaining what this exhibit is and which Dhanasar prong or NIW requirement it supports. Written in third person, neutral tone, suitable for a USCIS officer reviewing the petition."
}
"""
