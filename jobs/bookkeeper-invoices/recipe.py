#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["openai>=1.40"]
# ///
"""Bookkeeper: supplier invoices to a ready-to-import spreadsheet.

Reads a folder of supplier invoices and writes a CSV you can import into
Xero, with a report of anything to query before you pay. The model reads
each invoice. Plain code does the checking: tax file numbers are redacted
before the model sees anything, ABNs are tested against the ATO check digit,
GST is recalculated, lines are added up and duplicates are caught.

Run:  python jobs/bookkeeper-invoices/recipe.py --demo
      python jobs/bookkeeper-invoices/recipe.py --folder path/to/invoices
"""

import argparse
import csv
import io
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[1]))
from au import checks  # noqa: E402  (Australian checks shared by every recipe)

DEFAULT_BASE_URL = "https://api.continuumlabs.ai/v1"
DEFAULT_MODEL = "glm-5.2"
DEMO_NOTE = "> Demonstration output. The model's replies were scripted. Run without --demo for a live result.\n\n"


def make_client():
    """An OpenAI SDK client pointed at Continuum, or any compatible endpoint."""
    key = os.environ.get("CONTINUUM_API_KEY")
    if not key:
        sys.exit("Set CONTINUUM_API_KEY first. See .env.example.")
    try:
        from openai import OpenAI
    except ImportError:
        sys.exit("Install the requirements first: pip install -r requirements.txt")
    return OpenAI(base_url=os.environ.get("CONTINUUM_BASE_URL", DEFAULT_BASE_URL), api_key=key)


def demo_client(name):
    """Load a scripted model run from the repository's demo folder."""
    from demo import scripts

    print(scripts.BANNER)
    return getattr(scripts, name)()


# ---------------------------------------------------------------------------
# Step 1: the model reads the invoice into a fixed structure
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You read supplier invoices for an Australian bookkeeper.
Reply with one JSON object only, with exactly these fields:

{
  "supplier_name": "as written",
  "supplier_abn": "the ABN exactly as written, or null if none is shown",
  "gst_registered": false only if the invoice says the supplier is not registered for GST, otherwise true,
  "invoice_number": "as written",
  "invoice_date": "as written",
  "due_date": "as written, or null",
  "lines": [{"description": "...", "quantity": "as written", "unit_price": "as written",
             "amount": "as written", "gst_free": true if the line is marked GST-free}],
  "subtotal_ex_gst": "as written, or the total if there is no GST",
  "gst": "as written, or \\"$0.00\\" if there is none",
  "total_inc_gst": "as written"
}

Copy every number exactly as it appears. Do not correct the supplier's arithmetic, even if it is wrong.
Do not invent anything that is not on the invoice."""


def request_body(model, text, extra=()):
    return {
        "model": model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": text}, *extra],
    }


def squash(text):
    return re.sub(r"[\s,$]", "", str(text)).lower()


def extraction_problems(data, source):
    """Did the model read the invoice faithfully? These are the model's mistakes, so it gets one chance to fix them."""
    if not isinstance(data, dict):
        return ["the reply was not a JSON object"]
    problems = []
    for field in ["supplier_name", "invoice_number", "invoice_date", "lines", "subtotal_ex_gst", "gst", "total_inc_gst"]:
        if data.get(field) in (None, "", []):
            if not (field == "gst" and data.get("gst_registered") is False):
                problems.append(f"missing {field}")
    if problems:
        return problems
    figures = [data["subtotal_ex_gst"], data["total_inc_gst"]] + [line.get("amount") for line in data["lines"]]
    if data.get("gst_registered") is not False:
        figures.append(data["gst"])
    for figure in figures:
        if checks.money(figure) is None:
            problems.append(f"'{figure}' is not an amount of money")
        elif squash(figure) not in squash(source) and squash(f"{checks.money(figure):.2f}") not in squash(source):
            problems.append(f"the amount {figure} does not appear on the invoice. Copy amounts exactly")
    if checks.au_date(data["invoice_date"]) is None:
        problems.append(f"invoice_date '{data['invoice_date']}' is not a date")
    return problems


def read_invoice(client, model, path):
    raw = path.read_text()
    # Tax file numbers never reach the model.
    text, tfns = checks.redact_tfns(raw)
    body = request_body(model, text)
    problems = []
    for attempt in range(2):
        response = client.chat.completions.create(**body)
        content = response.choices[0].message.content or ""
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            data, problems = None, ["the reply was not valid JSON"]
        else:
            problems = extraction_problems(data, text)
        if not problems:
            return {"source": path.name, "data": data, "tfns_redacted": tfns, "corrected": attempt > 0}
        body = request_body(model, text, [
            {"role": "assistant", "content": content},
            {"role": "user", "content": "Fix these problems and reply with corrected JSON only: " + "; ".join(problems)},
        ])
    return {"source": path.name, "data": None, "tfns_redacted": tfns, "needs_review": problems}


# ---------------------------------------------------------------------------
# Step 2: plain code checks the invoice itself
# ---------------------------------------------------------------------------

def invoice_findings(data):
    """Problems with the invoice, as the supplier wrote it. These are for the bookkeeper to query."""
    findings = []
    sub = checks.money(data["subtotal_ex_gst"])
    abn = data.get("supplier_abn")

    if not abn:
        if sub > checks.NO_ABN_THRESHOLD:
            withhold = (sub * checks.NO_ABN_WITHHOLDING_RATE).quantize(checks.CENT)
            findings.append(
                f"No ABN quoted on an invoice over ${checks.NO_ABN_THRESHOLD}. Under the ATO's no-ABN withholding "
                f"rules you may need to withhold 47% (${withhold:,.2f}) unless an exception applies. Ask for their ABN."
            )
    elif not checks.abn_valid(abn):
        findings.append(f"ABN {abn} fails the ATO check digit test, so it is probably mistyped. "
                        "Confirm it on ABN Lookup before paying.")

    gst_free = sum((checks.money(l.get("amount")) or Decimal(0)) for l in data["lines"] if l.get("gst_free"))
    if data.get("gst_registered") is False:
        if (checks.money(data.get("gst")) or Decimal(0)) != 0:
            findings.append("The supplier says they are not registered for GST but charged GST.")
    else:
        findings += checks.gst_problems(sub, data["gst"], data["total_inc_gst"], gst_free_amount=gst_free)

    line_total = sum((checks.money(l.get("amount")) or Decimal(0)) for l in data["lines"])
    if abs(line_total - sub) > checks.CENT:
        findings.append(f"The lines add up to ${line_total:,.2f} but the subtotal says ${sub:,.2f}.")
    return findings


def duplicate_key(data):
    who = checks.digits(data.get("supplier_abn")) or re.sub(r"\W", "", data["supplier_name"].lower())
    return who, re.sub(r"\W", "", str(data["invoice_number"]).lower())


def process_folder(client, model, folder, workers=8):
    paths = sorted(Path(folder).glob("*.txt"))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(lambda p: read_invoice(client, model, p), paths))
    seen = {}
    for r in results:  # in file order, so the first copy of an invoice wins
        if r.get("needs_review"):
            r["status"] = "review"
            continue
        key = duplicate_key(r["data"])
        if key in seen:
            r["status"], r["duplicate_of"] = "duplicate", seen[key]
            continue
        seen[key] = r["source"]
        r["findings"] = invoice_findings(r["data"])
        r["status"] = "hold" if r["findings"] else "ready"
    return results


# ---------------------------------------------------------------------------
# Step 3: the import file and the report
# ---------------------------------------------------------------------------

CSV_COLUMNS = ["ContactName", "InvoiceNumber", "InvoiceDate", "DueDate", "Description",
               "Quantity", "UnitAmount", "AccountCode", "TaxType", "Currency"]


def import_csv(results, default_terms=30):
    """A bills import in Xero's column layout. Amounts exclude GST. Fill AccountCode with your own chart of accounts.

    Invoices with no due date are given your standard payment terms.
    """
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(CSV_COLUMNS)
    for r in results:
        if r.get("status") != "ready":
            continue
        d = r["data"]
        invoice_date = checks.au_date(d["invoice_date"])
        due = checks.au_date(d.get("due_date")) or invoice_date + timedelta(days=default_terms)
        for line in d["lines"]:
            qty = checks.money(line.get("quantity")) or Decimal(1)
            amount = checks.money(line.get("amount"))
            unit = checks.money(line.get("unit_price")) or (amount / qty).quantize(checks.CENT)
            tax = "GST Free Expenses" if line.get("gst_free") or d.get("gst_registered") is False else "GST on Expenses"
            writer.writerow([d["supplier_name"], d["invoice_number"], f"{invoice_date:%d/%m/%Y}", f"{due:%d/%m/%Y}",
                             line["description"], f"{qty.normalize():f}", f"{unit:.2f}", "", tax, "AUD"])
    return out.getvalue()


def report_markdown(results):
    ready = [r for r in results if r.get("status") == "ready"]
    hold = [r for r in results if r.get("status") == "hold"]
    dupes = [r for r in results if r.get("status") == "duplicate"]
    review = [r for r in results if r.get("status") == "review"]
    total = sum(checks.money(r["data"]["total_inc_gst"]) for r in ready)
    gst = sum(checks.money(r["data"]["gst"]) for r in ready)

    lines = ["# Supplier invoices", "",
             f"{len(results)} files read. {len(ready)} ready to import, {len(hold)} to query before paying, "
             f"{len(dupes)} duplicate, {len(review)} for a person to read.", ""]
    if ready:
        lines += ["## Ready to import", "", "| Supplier | Invoice | Date | Total inc GST | GST |", "|---|---|---|---:|---:|"]
        for r in ready:
            d = r["data"]
            lines.append(f"| {d['supplier_name']} | {d['invoice_number']} | {checks.au_date(d['invoice_date']):%d/%m/%Y} | "
                         f"${checks.money(d['total_inc_gst']):,.2f} | ${checks.money(d['gst']):,.2f} |")
        lines += ["", f"Total ${total:,.2f}, including ${gst:,.2f} GST you can claim on your BAS. "
                      "The lines are in `bills-import.csv`.", ""]
    if hold:
        lines += ["## Query before paying", ""]
        for r in hold:
            d = r["data"]
            lines.append(f"**{d['supplier_name']}, {d['invoice_number']}** (${checks.money(d['total_inc_gst']):,.2f})")
            lines += [f"- {f}" for f in r["findings"]] + [""]
    if dupes:
        lines += ["## Duplicates, not imported", ""]
        lines += [f"- `{r['source']}` repeats {r['data']['supplier_name']} {r['data']['invoice_number']} "
                  f"from `{r['duplicate_of']}`." for r in dupes] + [""]
    if review:
        lines += ["## For a person to read", ""]
        lines += [f"- `{r['source']}`: {'; '.join(r['needs_review'])}" for r in review] + [""]

    caught = []
    for r in results:
        name = r["data"]["supplier_name"] if r.get("data") else r["source"]
        if r.get("tfns_redacted"):
            caught.append(f"- {name}: removed a tax file number before the invoice reached the model.")
        if r.get("corrected"):
            caught.append(f"- {name}: the model's first reading did not match the invoice and was corrected.")
        for f in r.get("findings", []):
            if "check digit" in f:
                caught.append(f"- {name}: ABN failed the check digit test.")
            elif f.startswith("GST is") or f.startswith("total is"):
                caught.append(f"- {name}: the supplier's GST arithmetic is wrong ({f}).")
            elif f.startswith("No ABN"):
                caught.append(f"- {name}: no ABN quoted, so withholding may apply.")
        if r.get("status") == "duplicate":
            caught.append(f"- {name}: the same invoice arrived twice. Only one copy is in the import file.")
    if caught:
        lines += ["## What the checks caught", ""] + caught + [""]
    lines += ["Checks run in plain code: tax file number redaction, ABN check digits, GST recalculation, "
              "line totals and duplicate detection. A check digit pass shows an ABN is well formed, not that it "
              "is registered. Confirm new suppliers on ABN Lookup."]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--folder", default=HERE / "data" / "invoices", type=Path)
    parser.add_argument("--out", default=Path("output") / "bookkeeper-invoices", type=Path)
    parser.add_argument("--model", default=os.environ.get("CONTINUUM_MODEL", DEFAULT_MODEL))
    parser.add_argument("--workers", default=8, type=int)
    parser.add_argument("--terms", default=30, type=int, help="Days to pay when an invoice shows no due date.")
    parser.add_argument("--demo", action="store_true", help="Run a scripted demonstration. No API key needed.")
    args = parser.parse_args()

    client = demo_client("bookkeeper_client") if args.demo else make_client()
    results = process_folder(client, args.model, args.folder, args.workers)
    report = report_markdown(results)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "report.md").write_text((DEMO_NOTE if args.demo else "") + report)
    (args.out / "bills-import.csv").write_text(import_csv(results, args.terms))
    (args.out / "invoices.json").write_text(json.dumps(results, indent=2, default=str))
    print(report)
    print(f"\nSaved to {args.out}/")


if __name__ == "__main__":
    main()
