"""NIW petition section/slot template.

Defines the standard structure of an EB-2 National Interest Waiver (NIW) I-140
petition: eight sections (matching the Dhanasar three-prong framework plus
formal/identity/eligibility sections), each containing named slots for every
required, recommended, conditional, or optional document.

Each slot carries:
  - requirement: required | recommended | conditional | optional
  - description: what the document is and what USCIS expects
  - rationale:   default text used on the generated exhibit cover sheet,
                 explaining why this exhibit is being submitted

Slots default to allowing multiple files per slot. Exhibit numbers are
assigned continuously across the whole petition in section/slot/exhibit order.
"""

NIW_TEMPLATE = [
    {
        "key": "petition_forms",
        "name": "Petition Letter & Forms",
        "hint": (
            "The legal brief arguing the three Dhanasar prongs plus required USCIS "
            "forms. This is what the officer reads first."
        ),
        "slots": [
            {
                "key": "cover_letter",
                "name": "Petition Cover Letter / Legal Brief",
                "requirement": "required",
                "description": (
                    "Attorney brief arguing the three Dhanasar prongs (substantial "
                    "merit & national importance; well positioned; balancing factors). "
                    "Reference exhibits throughout."
                ),
                "rationale": (
                    "Sets out the legal argument that the petitioner satisfies the EB-2 "
                    "national interest waiver standard under Matter of Dhanasar, 26 I&N "
                    "Dec. 884 (AAO 2016)."
                ),
            },
            {
                "key": "form_i140",
                "name": "Form I-140 (Immigrant Petition for Alien Worker)",
                "requirement": "required",
                "description": (
                    "Completed Form I-140 with Part 2.h (NIW) selected and all "
                    "applicable parts answered."
                ),
                "rationale": (
                    "Form I-140 on which classification under INA 203(b)(2) is requested "
                    "with a national interest waiver of the job offer and labor "
                    "certification requirements."
                ),
            },
            {
                "key": "form_g28",
                "name": "Form G-28 (Notice of Entry of Appearance of Attorney)",
                "requirement": "conditional",
                "description": "Required if the petitioner is represented by counsel.",
                "rationale": (
                    "Establishes the attorney or accredited representative's "
                    "representation of record before USCIS in this matter."
                ),
            },
            {
                "key": "form_i907",
                "name": "Form I-907 (Premium Processing Request)",
                "requirement": "optional",
                "description": (
                    "Optional. Requests 45-business-day premium processing for the I-140."
                ),
                "rationale": (
                    "Requests premium processing service under INA 286(u) for expedited "
                    "adjudication of the I-140 petition."
                ),
            },
            {
                "key": "filing_fee_receipt",
                "name": "Filing fee receipt / payment confirmation",
                "requirement": "optional",
                "description": (
                    "myUSCIS handles payment electronically; include a copy for the "
                    "record if available."
                ),
                "rationale": "Confirms payment of the I-140 filing fee.",
            },
        ],
    },
    {
        "key": "identity_status",
        "name": "Identity & Immigration Status",
        "hint": (
            "Petitioner's identity, current immigration status, and prior approvals."
        ),
        "slots": [
            {
                "key": "passport",
                "name": "Passport biographic page",
                "requirement": "required",
                "description": (
                    "Color copy of the passport bio page showing name, photo, date of "
                    "birth, nationality, and expiration."
                ),
                "rationale": (
                    "Documents the petitioner's identity, nationality, and date of birth."
                ),
            },
            {
                "key": "visa",
                "name": "Most recent U.S. visa stamp",
                "requirement": "conditional",
                "description": "If applicable. Copy of the most recent U.S. visa stamp.",
                "rationale": (
                    "Documents the petitioner's most recent U.S. visa issuance and "
                    "lawful entry classification."
                ),
            },
            {
                "key": "i94",
                "name": "Most recent Form I-94 arrival record",
                "requirement": "conditional",
                "description": (
                    "If currently in the United States. Print from i94.cbp.dhs.gov."
                ),
                "rationale": (
                    "Documents the petitioner's current authorized period of stay in "
                    "the United States."
                ),
            },
            {
                "key": "i797_current",
                "name": "Current status I-797 approval notice",
                "requirement": "conditional",
                "description": (
                    "Most recent I-797 approval notice showing current nonimmigrant "
                    "status (H-1B, O-1, F-1, etc.)."
                ),
                "rationale": "Documents the petitioner's current lawful nonimmigrant status.",
            },
            {
                "key": "i797_prior",
                "name": "Prior I-797 approval notices",
                "requirement": "optional",
                "description": (
                    "All prior I-797 approval notices, demonstrating continuous lawful "
                    "status history."
                ),
                "rationale": (
                    "Documents the petitioner's prior immigration history and continuous "
                    "lawful status in the United States."
                ),
            },
            {
                "key": "ead",
                "name": "EAD card (front and back)",
                "requirement": "conditional",
                "description": "If on an EAD (F-1 OPT, H-4 EAD, etc.).",
                "rationale": "Documents the petitioner's current employment authorization.",
            },
            {
                "key": "birth_certificate",
                "name": "Birth certificate (with certified translation)",
                "requirement": "recommended",
                "description": (
                    "With a certified English translation if not originally in English. "
                    "Strongly recommended; also needed for the downstream I-485."
                ),
                "rationale": "Documents the petitioner's date and place of birth.",
            },
        ],
    },
    {
        "key": "eb2_eligibility",
        "name": "EB-2 Eligibility (Advanced Degree or Exceptional Ability)",
        "hint": (
            "Documentary proof you qualify for the EB-2 category — either an advanced "
            "degree (or U.S. bachelor's plus 5 years progressive experience) or "
            "exceptional ability (at least 3 of 6 regulatory criteria)."
        ),
        "slots": [
            {
                "key": "highest_degree",
                "name": "Highest degree diploma (PhD / Master's / equivalent)",
                "requirement": "required",
                "description": "Color copy of the highest academic degree diploma.",
                "rationale": (
                    "Demonstrates the petitioner holds an advanced degree as defined "
                    "in 8 CFR 204.5(k)(2) for EB-2 classification."
                ),
            },
            {
                "key": "highest_degree_transcript",
                "name": "Official transcripts for highest degree",
                "requirement": "required",
                "description": "Official transcripts showing the conferred advanced degree.",
                "rationale": (
                    "Verifies the coursework, grades, and conferral of the petitioner's "
                    "advanced degree."
                ),
            },
            {
                "key": "credential_evaluation",
                "name": "Foreign credential evaluation",
                "requirement": "conditional",
                "description": (
                    "Required if any degree was earned outside the U.S. Use a "
                    "NACES-member evaluator (WES, ECE, SpanTran, etc.)."
                ),
                "rationale": (
                    "Establishes that the petitioner's foreign degree is equivalent to "
                    "a U.S. advanced degree under 8 CFR 204.5(k)(3)(i)(A)."
                ),
            },
            {
                "key": "bachelors_degree",
                "name": "Bachelor's degree diploma + transcripts",
                "requirement": "conditional",
                "description": (
                    "Required if proceeding under the Bachelor's-plus-5-years-progressive "
                    "experience equivalency track."
                ),
                "rationale": (
                    "Establishes the baccalaureate degree underlying the bachelor's "
                    "plus five years progressive experience equivalency under 8 CFR "
                    "204.5(k)(3)(i)(B)."
                ),
            },
            {
                "key": "progressive_experience_letters",
                "name": "Progressive-experience employment letters (Bachelor's + 5 track)",
                "requirement": "conditional",
                "description": (
                    "Employer letters showing at least five years of progressive "
                    "post-baccalaureate experience in the specialty."
                ),
                "rationale": (
                    "Documents at least five years of progressive post-baccalaureate "
                    "experience in the specialty, qualifying the petitioner as the "
                    "equivalent of an advanced-degree holder under 8 CFR "
                    "204.5(k)(3)(i)(B)."
                ),
            },
            {
                "key": "license",
                "name": "Professional license / certification",
                "requirement": "optional",
                "description": "If the field requires licensure, include the current license.",
                "rationale": "Documents professional licensure in the petitioner's field.",
            },
        ],
    },
    {
        "key": "prong_1",
        "name": "Prong 1 — Substantial Merit & National Importance",
        "hint": (
            "Evidence the proposed endeavor has substantial merit AND national "
            "importance. Focus on the FIELD's importance, not just the petitioner."
        ),
        "slots": [
            {
                "key": "endeavor_statement",
                "name": "Statement of proposed endeavor",
                "requirement": "required",
                "description": (
                    "Written statement from the petitioner describing the specific "
                    "proposed endeavor in the United States."
                ),
                "rationale": (
                    "Defines the petitioner's specific proposed endeavor for the "
                    "Dhanasar Prong 1 analysis."
                ),
            },
            {
                "key": "industry_reports",
                "name": "Industry / market reports on the field",
                "requirement": "recommended",
                "description": (
                    "Reports from major consultancies, industry associations, or "
                    "academic bodies showing the field's economic and scientific "
                    "importance."
                ),
                "rationale": (
                    "Demonstrates the substantial merit and broader importance of the "
                    "petitioner's field of endeavor."
                ),
            },
            {
                "key": "government_priorities",
                "name": "Government reports / national priority documents",
                "requirement": "recommended",
                "description": (
                    "White House strategies, NSF/NIH/DOE/DOD priorities, CHIPS and "
                    "Science Act, IRA, OSTP reports — establishing the U.S. has "
                    "declared this field a national priority."
                ),
                "rationale": (
                    "Establishes the petitioner's field as a recognized U.S. national "
                    "priority, supporting national importance under Dhanasar Prong 1."
                ),
            },
            {
                "key": "economic_impact",
                "name": "Economic impact analysis",
                "requirement": "optional",
                "description": (
                    "Studies quantifying job creation, GDP impact, or critical "
                    "infrastructure dependence on the field."
                ),
                "rationale": (
                    "Quantifies the economic significance of the petitioner's field at "
                    "a national scale."
                ),
            },
            {
                "key": "media_field",
                "name": "News & media coverage of the field's importance",
                "requirement": "optional",
                "description": (
                    "Press coverage establishing public and governmental concern about "
                    "the field."
                ),
                "rationale": "Demonstrates broad public recognition of the field's national importance.",
            },
        ],
    },
    {
        "key": "prong_2",
        "name": "Prong 2 — Well Positioned to Advance the Endeavor",
        "hint": (
            "Evidence the petitioner specifically is well positioned to advance this "
            "endeavor — credentials, record of success, and trajectory."
        ),
        "slots": [
            {
                "key": "cv",
                "name": "Detailed CV / résumé",
                "requirement": "required",
                "description": (
                    "Up-to-date CV covering education, employment, publications, "
                    "patents, awards, presentations, and service."
                ),
                "rationale": (
                    "Provides a comprehensive overview of the petitioner's "
                    "qualifications, achievements, and trajectory under Dhanasar Prong 2."
                ),
            },
            {
                "key": "publications_list",
                "name": "Publications list",
                "requirement": "recommended",
                "description": (
                    "Comprehensive list of peer-reviewed publications with citation "
                    "metrics."
                ),
                "rationale": (
                    "Documents the petitioner's record of original contributions to "
                    "the field through peer-reviewed publication."
                ),
            },
            {
                "key": "publications_pdfs",
                "name": "Selected publication PDFs",
                "requirement": "recommended",
                "description": (
                    "Copies of the most important publications (full text or first "
                    "page + abstract). Multiple files welcome."
                ),
                "rationale": (
                    "Provides evidentiary copies of the petitioner's most significant "
                    "peer-reviewed contributions to the field."
                ),
            },
            {
                "key": "citation_report",
                "name": "Citation report (Google Scholar / Scopus / Web of Science)",
                "requirement": "recommended",
                "description": (
                    "Screenshots or exports showing h-index, total citations, and "
                    "top-cited works."
                ),
                "rationale": (
                    "Quantifies the impact and recognition of the petitioner's "
                    "published work in the field."
                ),
            },
            {
                "key": "patents",
                "name": "Patents (granted and/or pending)",
                "requirement": "optional",
                "description": (
                    "If applicable. Include the front page and abstract of each patent."
                ),
                "rationale": (
                    "Documents the petitioner's record of innovation through granted "
                    "and pending patents."
                ),
            },
            {
                "key": "awards",
                "name": "Awards and honors",
                "requirement": "optional",
                "description": (
                    "Certificates, citations, or prize announcements showing recognition."
                ),
                "rationale": (
                    "Demonstrates external recognition of the petitioner's contributions "
                    "to the field."
                ),
            },
            {
                "key": "media_petitioner",
                "name": "Media coverage of the petitioner's work",
                "requirement": "optional",
                "description": (
                    "Articles, podcasts, or interviews about the petitioner's work — "
                    "independent coverage, not paid promotional material."
                ),
                "rationale": (
                    "Documents independent media recognition of the petitioner's "
                    "contributions."
                ),
            },
            {
                "key": "memberships",
                "name": "Selective professional memberships",
                "requirement": "optional",
                "description": (
                    "Membership letters or cards for associations that require "
                    "outstanding achievement for admission."
                ),
                "rationale": (
                    "Demonstrates the petitioner's standing in selective professional "
                    "associations requiring outstanding achievement."
                ),
            },
            {
                "key": "funding_grants",
                "name": "Grants and competitive funding received",
                "requirement": "optional",
                "description": (
                    "Award letters or evidence of competitive funding the petitioner "
                    "obtained or substantially contributed to."
                ),
                "rationale": (
                    "Documents that the petitioner's work has attracted competitive "
                    "funding, evidencing peer recognition."
                ),
            },
            {
                "key": "peer_review",
                "name": "Peer review / editorial service",
                "requirement": "optional",
                "description": (
                    "Invitations to peer review for journals or conferences; editorial "
                    "board roles."
                ),
                "rationale": (
                    "Demonstrates recognition of the petitioner as an expert qualified "
                    "to evaluate the work of others in the field."
                ),
            },
            {
                "key": "conference",
                "name": "Conference presentations & invited talks",
                "requirement": "optional",
                "description": (
                    "Evidence of invited talks, keynote or plenary slots, and conference "
                    "acceptances."
                ),
                "rationale": (
                    "Documents the petitioner's invited dissemination of their work to "
                    "professional audiences."
                ),
            },
            {
                "key": "adoption",
                "name": "Evidence of adoption / implementation of the work",
                "requirement": "recommended",
                "description": (
                    "Other researchers citing or using the methods, companies adopting "
                    "the technology, policy referencing the findings."
                ),
                "rationale": (
                    "Demonstrates real-world adoption and impact of the petitioner's "
                    "contributions in the field."
                ),
            },
        ],
    },
    {
        "key": "recommendation_letters",
        "name": "Recommendation Letters",
        "hint": (
            "Independent (no prior personal/professional relationship) and dependent "
            "(advisors, collaborators) experts attesting to the petitioner's "
            "qualifications and the field's importance. Independent letters carry the "
            "most weight; aim for four to six."
        ),
        "slots": [
            {
                "key": "independent_letters",
                "name": "Independent expert letters",
                "requirement": "required",
                "description": (
                    "Letters from independent experts with no prior personal or "
                    "professional relationship with the petitioner. Each letter is its "
                    "own exhibit."
                ),
                "rationale": (
                    "Independent expert testimony attesting to the petitioner's "
                    "qualifications and the national importance of their endeavor."
                ),
            },
            {
                "key": "dependent_letters",
                "name": "Dependent expert letters (advisors, collaborators)",
                "requirement": "recommended",
                "description": (
                    "Letters from advisors, mentors, or close collaborators with "
                    "detailed first-hand knowledge of the petitioner's work."
                ),
                "rationale": (
                    "First-hand expert testimony from advisors or collaborators with "
                    "detailed knowledge of the petitioner's contributions."
                ),
            },
        ],
    },
    {
        "key": "prong_3",
        "name": "Prong 3 — Balancing Factors",
        "hint": (
            "Argument that, on balance, it would be beneficial to the United States "
            "to waive the job offer and labor certification requirements."
        ),
        "slots": [
            {
                "key": "balancing_statement",
                "name": "Balancing statement / argument (often within the brief)",
                "requirement": "required",
                "description": (
                    "Often included within the petition cover letter. If submitted "
                    "separately, attach here."
                ),
                "rationale": (
                    "Argues that, on balance, waiving the job offer and labor "
                    "certification requirements benefits the United States under "
                    "Dhanasar Prong 3."
                ),
            },
            {
                "key": "labor_cert_impracticality",
                "name": "Evidence of impracticality of labor certification",
                "requirement": "recommended",
                "description": (
                    "Evidence the petitioner's work is too specialized, novel, or "
                    "self-directed to fit within the PERM framework."
                ),
                "rationale": (
                    "Demonstrates that requiring labor certification would be "
                    "impractical for the petitioner's endeavor."
                ),
            },
            {
                "key": "us_commitment",
                "name": "U.S. employer / collaborator commitment evidence",
                "requirement": "optional",
                "description": (
                    "Letters of intent, contracts, employment offers, or MoUs showing "
                    "concrete U.S. opportunities."
                ),
                "rationale": (
                    "Documents concrete U.S. opportunities supporting the petitioner's "
                    "ability to pursue the endeavor here."
                ),
            },
            {
                "key": "urgency",
                "name": "Urgency / national interest in expedited contribution",
                "requirement": "optional",
                "description": (
                    "Evidence the United States has a time-sensitive need for the "
                    "petitioner's contribution."
                ),
                "rationale": (
                    "Establishes time-sensitivity supporting an immediate national "
                    "interest in the petitioner's contribution."
                ),
            },
        ],
    },
    {
        "key": "additional",
        "name": "Additional Supporting Evidence",
        "hint": (
            "Anything else that strengthens the petition. Add exhibits as needed."
        ),
        "slots": [
            {
                "key": "additional_evidence",
                "name": "Additional exhibits",
                "requirement": "optional",
                "description": (
                    "Any supporting evidence not covered by the slots above."
                ),
                "rationale": "Additional supporting evidence for the petition.",
            },
        ],
    },
]


REQUIREMENT_BADGES = {
    "required": ("Required", "bg-red-100 text-red-800"),
    "conditional": ("Conditional", "bg-amber-100 text-amber-800"),
    "recommended": ("Recommended", "bg-blue-100 text-blue-800"),
    "optional": ("Optional", "bg-gray-100 text-gray-700"),
}


def new_sections():
    """Build a fresh sections list (deep-copied) from the template, with new ids."""
    import uuid

    def nid():
        return uuid.uuid4().hex[:8]

    sections = []
    for s in NIW_TEMPLATE:
        slots = []
        for slot in s["slots"]:
            slots.append(
                {
                    "id": nid(),
                    "key": slot["key"],
                    "name": slot["name"],
                    "requirement": slot["requirement"],
                    "description": slot["description"],
                    "rationale": slot["rationale"],
                    "exhibits": [],  # each: {id, src_id, label, rationale}
                }
            )
        sections.append(
            {"id": nid(), "key": s["key"], "name": s["name"], "hint": s["hint"], "slots": slots}
        )
    return sections
