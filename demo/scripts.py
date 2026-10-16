"""Scripted model runs for demo mode.

Run any recipe with --demo to see it work without an API key. The model's
replies below are pre-written. Everything else is the recipe's real code:
the agent loop, the tools, the checks in plain code and the report.
"""

import json

from demo.fake_model import FakeClient, reply, tool_call

BANNER = (
    "DEMO MODE: the model's replies are scripted, not live. The recipe's own code runs for real.\n"
    "Set CONTINUUM_API_KEY and drop --demo to run it against a live model.\n"
)


# ---------------------------------------------------------------------------
# Contract review
# ---------------------------------------------------------------------------

CONTRACT_FINDINGS = [
    ("liability", "7", "exception", "high",
     "Clause 7 caps the Supplier's liability at 3 months of fees and leaves the Customer's liability uncapped. "
     "Policy requires a cap of at least 12 months of fees and no uncapped liability for us.",
     "Each party's total liability under this agreement is limited to the fees paid or payable in the "
     "12 months before the claim."),
    ("data_location", "5", "exception", "high",
     "Data may be processed in Singapore or the United States, and backups are held in the United States. "
     "Policy requires all data and backups to stay in Australia.",
     "The Supplier will store and process all Customer data, including backups, only in Australia."),
    ("intellectual_property", "6", "exception", "high",
     "The Supplier keeps ownership of all deliverables and grants us only a licence for the term. "
     "Policy requires us to own deliverables created for us.",
     "The Customer owns all intellectual property in deliverables created specifically for it. The Supplier "
     "keeps its pre-existing tools and grants the Customer a perpetual licence to use them within the deliverables."),
    ("termination_for_convenience", "4", "exception", "medium",
     "We can terminate for convenience only on 180 days' notice. Policy allows at most 90 days.",
     "The Customer may terminate this agreement for convenience on 90 days' written notice."),
    ("auto_renewal", "3", "exception", "medium",
     "The agreement renews for 12-month terms unless notice is given 30 days before the end, and the Supplier "
     "has no duty to remind us. Policy requires a reminder at least 60 days before renewal.",
     "The Supplier must notify the Customer in writing at least 60 days before any renewal date. "
     "Without that notice, the agreement does not renew."),
    ("governing_law", "9", "exception", "medium",
     "The agreement is governed by Singapore law. Policy requires Victoria or New South Wales.",
     "This agreement is governed by the laws of Victoria, Australia."),
    ("payment_terms", "2", "exception", "low",
     "Invoices are due within 14 days, and late payments attract 2% interest a month. "
     "Policy is 30 days. Shorter terms need Finance approval.",
     "The Customer will pay each undisputed invoice within 30 days of receiving it."),
    ("confidentiality", "8", "compliant", "low",
     "Confidentiality lasts for 5 years after the agreement ends, beyond the 3-year minimum.", ""),
]

CONTRACT_SUMMARY = (
    "The contract does not meet our policies as drafted. Seven of eight topics need changes, and three are high "
    "risk: offshore data, a three-month liability cap and the Supplier owning our deliverables. "
    "Do not sign until clauses 5, 6 and 7 are amended."
)


def contract_review_client():
    topics = [f[0] for f in CONTRACT_FINDINGS]
    return FakeClient([
        reply(tool_calls=[tool_call("get_policy", topic=t) for t in topics]),
        reply(tool_calls=[tool_call("read_clause", number=str(n)) for n in range(2, 10)]),
        reply(tool_calls=[
            tool_call("record_finding", topic=t, clause=c, status=s, risk=r, explanation=e, suggested_redline=red)
            for t, c, s, r, e, red in CONTRACT_FINDINGS
        ]),
        reply(tool_calls=[tool_call("finish", summary=CONTRACT_SUMMARY)]),
    ])


# ---------------------------------------------------------------------------
# Research analyst
# ---------------------------------------------------------------------------

RESEARCH_ANSWER = (
    "Not yet. The board made any wider launch conditional on the Risk Committee confirming the accuracy "
    "threshold [1]. The committee set that threshold at 95% of 500 real member enquiries answered correctly [2]. "
    "The pilot scored 93.4% [3], so the threshold has not been met.\n\n"
    "The other two board conditions are in hand. Member data must stay in Australia [4], and no member data "
    "left Australia during the pilot [5]. Every answer must be reviewed by staff before it is sent [6]. "
    "The documents do not say how that review performed at scale.\n\n"
    "The committee also asked for the hand-off rate [7]. The pilot handed 12% of enquiries to a person [8]."
)

RESEARCH_CITATIONS = [
    {"doc_id": "board-minutes-2026-08",
     "quote": "The Risk Committee must confirm the pilot meets its accuracy threshold before any wider launch."},
    {"doc_id": "risk-committee-2026-09",
     "quote": "must answer at least 95% of a test set of 500 real member enquiries correctly"},
    {"doc_id": "pilot-results-2026-10", "quote": "467 were correct, an accuracy of 93.4%"},
    {"doc_id": "board-minutes-2026-08", "quote": "Member data must be stored and processed in Australia."},
    {"doc_id": "pilot-results-2026-10", "quote": "No member data left Australia during the pilot."},
    {"doc_id": "board-minutes-2026-08",
     "quote": "Every answer sent to a member must be reviewed by a staff member before it is sent."},
    {"doc_id": "risk-committee-2026-09", "quote": "report how often the assistant hands an enquiry to a person"},
    {"doc_id": "pilot-results-2026-10", "quote": "The assistant handed 12% of enquiries to a person."},
]

RESEARCH_VERDICT = {"claims": [
    {"claim": "Wider launch depends on the Risk Committee confirming the accuracy threshold.", "citations": [1],
     "supported": True, "reason": "Stated in the board minutes."},
    {"claim": "The threshold is 95% of 500 real member enquiries.", "citations": [2],
     "supported": True, "reason": "Stated in the committee minutes."},
    {"claim": "The pilot scored 93.4%, below the threshold.", "citations": [2, 3],
     "supported": True, "reason": "93.4% is below 95%."},
    {"claim": "Member data must stay in Australia, and none left during the pilot.", "citations": [4, 5],
     "supported": True, "reason": "Both stated directly."},
    {"claim": "Every answer must be reviewed by staff before it is sent.", "citations": [6],
     "supported": True, "reason": "Stated in the board minutes."},
    {"claim": "The pilot handed 12% of enquiries to a person.", "citations": [7, 8],
     "supported": True, "reason": "Stated in the pilot results."},
]}


def research_analyst_client():
    # The first answer quotes a figure that is not in the source. The recipe's code rejects it.
    invented = [{"doc_id": "pilot-results-2026-10", "quote": "an accuracy of 95.1%"}]
    return FakeClient([
        reply(tool_calls=[
            tool_call("search_documents", query="accuracy threshold before launch"),
            tool_call("search_documents", query="pilot results accuracy enquiries"),
            tool_call("search_documents", query="conditions approval data Australia review"),
        ]),
        reply(tool_calls=[
            tool_call("read_document", doc_id="board-minutes-2026-08"),
            tool_call("read_document", doc_id="risk-committee-2026-09"),
            tool_call("read_document", doc_id="pilot-results-2026-10"),
        ]),
        reply(tool_calls=[tool_call("submit_answer", answer="Yes, it is ready [1].", citations=invented)]),
        reply(tool_calls=[tool_call("submit_answer", answer=RESEARCH_ANSWER, citations=RESEARCH_CITATIONS)]),
        reply(content=json.dumps(RESEARCH_VERDICT)),
    ])


# ---------------------------------------------------------------------------
# Announcement monitor
# ---------------------------------------------------------------------------

ANNOUNCEMENTS = {
    "Ironbark": dict(
        company="Ironbark Minerals Ltd", category="guidance", material=True, direction="negative",
        headline="Copper guidance cut after pit wall failure closes haul road",
        summary="FY27 production guidance falls about 15% at the midpoint and sustaining costs rise 12%. "
                "The main haul road is expected to be closed for eight weeks. No injuries.",
        # "$5.00/lb" does not appear in the announcement. The recipe's figure check removes it.
        key_figures=["180-195kt", "210-230kt", "12%", "A$4.85/lb", "$5.00/lb"]),
    "Coralwave": dict(
        company="Coralwave Health Ltd", category="capital_raising", material=True, direction="mixed",
        headline="$85m placement at a 9.5% discount to buy 14 day-surgery clinics",
        summary="Dilutive raise funds most of a $120m acquisition, with the balance from debt. "
                "Management expects the deal to add to earnings per share in its first full year.",
        key_figures=["$85m", "$1.42", "9.5%", "$120m"]),
    "Tasman": dict(
        company="Tasman Freight Group", category="management_change", material=True, direction="negative",
        headline="Chief Executive of six years resigns, effective 31 January 2027",
        summary="The board is searching internally and externally. The Chief Financial Officer will act as "
                "interim Chief Executive if no successor is appointed in time.",
        key_figures=["31 January 2027"]),
    "Wattle": dict(
        company="Wattle Energy Ltd", category="governance_routine", material=False, direction="neutral",
        headline="All annual general meeting resolutions passed",
        summary="Routine result. No change to the business.", key_figures=[]),
    "Brindle": dict(
        company="Brindle Property Trust", category="governance_routine", material=False, direction="neutral",
        headline="Director buys 50,000 units on market at $2.18",
        summary="Small on-market purchase by a non-executive director.", key_figures=["50,000", "$2.18"]),
    "Quokka": dict(
        company="Quokka Software Ltd", category="results", material=True, direction="positive",
        headline="Revenue up 31% and first positive operating cash flow",
        summary="Half-year revenue of $48.2m, recurring revenue of $112m and $3.1m of operating cash flow. "
                "Full-year guidance unchanged.",
        key_figures=["$48.2m", "31%", "$112m", "$3.1m"]),
}


def announcement_monitor_client():
    attempts = {}

    def respond(request):
        text = request["messages"][1]["content"]
        key = next(k for k in ANNOUNCEMENTS if k in text)
        attempts[key] = attempts.get(key, 0) + 1
        if key == "Tasman" and attempts[key] == 1:
            # The first reply uses a category that is not on the list. The recipe asks for a correction.
            return reply(content=json.dumps({**ANNOUNCEMENTS[key], "category": "ceo_departure"}))
        return reply(content=json.dumps(ANNOUNCEMENTS[key]))

    return FakeClient(respond)


# ---------------------------------------------------------------------------
# Bookkeeper: supplier invoices
# ---------------------------------------------------------------------------

def _line(description, quantity, unit_price, amount, gst_free=False):
    return {"description": description, "quantity": quantity, "unit_price": unit_price,
            "amount": amount, "gst_free": gst_free}


IRONBARK_INVOICE = {
    "supplier_name": "Ironbark Plumbing Pty Ltd", "supplier_abn": "90 551 661 605", "gst_registered": True,
    "invoice_number": "INV-20417", "invoice_date": "03/10/2026", "due_date": "17/10/2026",
    "lines": [_line("Replace hot water unit, 315L electric", "1", "$1,890.00", "$1,890.00"),
              _line("Labour, licensed plumber", "3.5", "$128.00", "$448.00"),
              _line("Tempering valve", "1", "$164.00", "$164.00"),
              _line("Call-out fee", "1", "$95.00", "$95.00")],
    "subtotal_ex_gst": "$2,597.00", "gst": "$259.70", "total_inc_gst": "$2,856.70",
}

INVOICE_READINGS = {
    "Ironbark": IRONBARK_INVOICE,
    "Gumleaf": {
        "supplier_name": "Gumleaf Office Supplies", "supplier_abn": "87 192 327 523", "gst_registered": True,
        "invoice_number": "77812", "invoice_date": "6 October 2026", "due_date": None,
        "lines": [_line("A4 copy paper, 10 reams", "10", "$6.50", "$65.00"),
                  _line("Toner cartridge HL-2350", "2", "$89.00", "$178.00"),
                  _line("Milk and tea for kitchen", "1", "$18.40", "$18.40", gst_free=True)],
        "subtotal_ex_gst": "$261.40", "gst": "$24.30", "total_inc_gst": "$285.70",
    },
    "COASTAL": {
        "supplier_name": "Coastal Courier Co.", "supplier_abn": "28 322 761 078", "gst_registered": True,
        "invoice_number": "C-3391", "invoice_date": "07/10/2026", "due_date": None,
        "lines": [_line("Same-day delivery Melbourne to Geelong", "3", "$42.00", "$126.00"),
                  _line("Fuel levy 10%", "1", "$12.60", "$12.60")],
        "subtotal_ex_gst": "$138.60", "gst": "$13.86", "total_inc_gst": "$152.46",
    },
    "Wattle": {
        "supplier_name": "Wattle Electrical Services", "supplier_abn": "50 893 268 002", "gst_registered": True,
        "invoice_number": "WE-1188", "invoice_date": "08/10/2026", "due_date": "22/10/2026",
        "lines": [_line("Switchboard upgrade, 12-way, including RCDs and compliance certificate",
                        "1", "$1,250.00", "$1,250.00")],
        "subtotal_ex_gst": "$1,250.00", "gst": "$132.00", "total_inc_gst": "$1,382.00",
    },
    "Kookaburra": {
        "supplier_name": "Kookaburra Cleaning (Jess Moran)", "supplier_abn": None, "gst_registered": False,
        "invoice_number": "0042", "invoice_date": "09/10/2026", "due_date": None,
        "lines": [_line("Office clean, 4 visits", "4", "$85.00", "$340.00")],
        "subtotal_ex_gst": "$340.00", "gst": "$0.00", "total_inc_gst": "$340.00",
    },
}


def bookkeeper_client():
    """Reads each invoice. Misreads the Gumleaf total the first time, so the figure check sends it back."""
    seen = {}

    def respond(request):
        text = request["messages"][1]["content"]
        key = next(k for k in INVOICE_READINGS if k in text)
        seen[key] = seen.get(key, 0) + 1
        reading = INVOICE_READINGS[key]
        if key == "Gumleaf" and seen[key] == 1:
            reading = {**reading, "total_inc_gst": "$285.07"}  # digits swapped
        return reply(content=json.dumps(reading))

    return FakeClient(respond)


# ---------------------------------------------------------------------------
# Aged care: serious incident triage
# ---------------------------------------------------------------------------

def _incident(resident, category, priority, aware, evidence, summary, injury=False, police=False, reported=False):
    return {"resident": resident, "reportable": category != "not_reportable", "category": category,
            "priority": priority, "injury_needing_treatment": injury, "police_grounds": police,
            "reported_to_police": reported, "became_aware": aware, "evidence": evidence, "summary": summary}


INCIDENT_READINGS = {
    "IR-2611": _incident("E.W.", "not_reportable", "none", "14/10/2026 07:20",
                         "GP reviewed at 11:00 and found no injury.",
                         "Supervised fall in the bathroom while walking with a frame. No injury. Care plan followed."),
    "IR-2614": _incident("R.T.", "unexplained_absence", "P1", "14/10/2026 15:05",
                         "Staff called police at 15:30 and reported R.T. missing.",
                         "Resident left the secure memory support unit through a gate propped open by a contractor. "
                         "Reported to police and found unhurt at a bus stop two hours later.",
                         reported=True),
    "IR-2615": _incident("M.K.", "unreasonable_use_of_force", "P1", "15/10/2026 06:45",
                         "he grabbed me hard last night when I didn't want to get up",
                         "New bruising on both forearms after an overnight transfer. Resident says a care worker "
                         "grabbed her hard. GP prescribed pain relief and dressings. Worker stood down.",
                         injury=True, police=True),
    "IR-2617": _incident("J.P.", "stealing_or_financial_coercion_by_staff", "P2", "15/10/2026 11:30",
                         "The safe access log shows one staff member opened it on each of the four days.",
                         "Four unexplained cash withdrawals totalling $240 from the resident's bank card, kept in "
                         "the facility safe. One staff member accessed the safe each day. Staff member stood down.",
                         police=True),  # says P2, but police grounds make it P1. The code must raise it.
    "IR-2618": _incident("D.L.", "inappropriate_use_of_restrictive_practices", "P2", "15/10/2026 08:10",
                         "D.L. has no assessment, consent or behaviour support plan for bed rails.",
                         "Agency nurse raised both bed rails overnight to stop wandering, with no assessment, consent "
                         "or behaviour support plan. No injury or distress."),
    "IR-2620": _incident("A.N.", "neglect", "P2", "16/10/2026 12:50",
                         "She coughed on the first mouthful and staff removed the meal at once.",
                         "Resident on a minced and moist diet was served a regular-texture meal. Coughed, meal removed "
                         "at once. Checked by RN, no treatment needed."),
}


def aged_care_client():
    """Triages each report. Paraphrases the bed rails evidence the first time, so the quote check sends it back."""
    seen = {}

    def respond(request):
        text = request["messages"][1]["content"]
        key = next(k for k in INCIDENT_READINGS if k in text)
        seen[key] = seen.get(key, 0) + 1
        reading = INCIDENT_READINGS[key]
        if key == "IR-2618" and seen[key] == 1:
            reading = {**reading, "evidence": "The rails were put up without any consent to stop him wandering."}
        return reply(content=json.dumps(reading))

    return FakeClient(respond)
