#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["openai>=1.40"]
# ///
"""Aged care: incident reports to a serious incident triage list.

Reads a folder of incident reports and works out which ones must be reported
under the Serious Incident Response Scheme, at what priority, and by when.
The model reads each report. Plain code enforces the priority rules, works
out every deadline from the time staff became aware, and checks that the
evidence the model relies on is really in the report.

The result is a list for the clinical manager to act on, ordered by deadline.
A person makes every reporting decision.

Run:  python jobs/aged-care-incidents/recipe.py --demo
"""

import argparse
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).parent
DEFAULT_BASE_URL = "https://api.continuumlabs.ai/v1"
DEFAULT_MODEL = "glm-5.2"
DEMO_NOTE = "> Demonstration output. The model's replies were scripted. Run without --demo for a live result.\n\n"
RULES = json.loads((HERE / "data" / "sirs-rules.json").read_text())
CATEGORIES = list(RULES["categories"])


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
    sys.path.insert(0, str(HERE.parents[1]))
    from demo import scripts

    print(scripts.BANNER)
    return getattr(scripts, name)()


# ---------------------------------------------------------------------------
# Step 1: the model reads the report
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = f"""You help an Australian aged care provider triage incident reports under the
Serious Incident Response Scheme. Read the report and reply with one JSON object only:

{{
  "resident": "the resident's initials as written",
  "reportable": true or false,
  "category": one of {json.dumps(CATEGORIES + ["not_reportable"])},
  "priority": "P1", "P2" or "none",
  "injury_needing_treatment": true if the incident caused, or could reasonably have caused, injury or discomfort that needs medical or psychological treatment,
  "police_grounds": true if there are reasonable grounds to report it to police, such as a possible crime,
  "reported_to_police": true if the report says police were told,
  "became_aware": "the time staff became aware, copied exactly",
  "evidence": "one short passage copied word for word from the report that supports your category",
  "summary": "what happened, in at most 40 words, for the notice to the Commission"
}}

The categories mean:
{json.dumps(RULES["categories"], indent=2)}

Priority 1: {RULES["priority_1"]["description"]} It applies when {"; or ".join(RULES["priority_1"]["priority_1_when"])}.
Priority 2: {RULES["priority_2"]["description"]}
A fall or other event with no failure of care and no harm is not reportable. Do not guess facts that are not in the report."""


def request_body(model, text, extra=()):
    return {
        "model": model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": text}, *extra],
    }


def squash(text):
    return re.sub(r"[\W_]+", "", str(text)).lower()


def parse_time(text):
    cleaned = str(text or "").strip().replace(".", ":")
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y %I:%M %p", "%d/%m/%Y %I:%M%p", "%d %B %Y %H:%M"):
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    return None


def reading_problems(data, report):
    """The model's mistakes. It gets one chance to fix them."""
    if not isinstance(data, dict):
        return ["the reply was not a JSON object"]
    problems = []
    for field in ["resident", "reportable", "category", "priority", "injury_needing_treatment",
                  "police_grounds", "reported_to_police", "became_aware", "evidence", "summary"]:
        if field not in data:
            problems.append(f"missing {field}")
    if problems:
        return problems
    if data["category"] not in CATEGORIES + ["not_reportable"]:
        problems.append(f"category must be one of {CATEGORIES + ['not_reportable']}")
    if data["priority"] not in ("P1", "P2", "none"):
        problems.append("priority must be P1, P2 or none")
    if data["reportable"] != (data["category"] != "not_reportable"):
        problems.append("reportable must be true exactly when the category is not not_reportable")
    if data["reportable"] and data["priority"] == "none":
        problems.append("a reportable incident needs priority P1 or P2")
    if parse_time(data["became_aware"]) is None or squash(data["became_aware"]) not in squash(report):
        problems.append("became_aware must be the time staff became aware, copied exactly from the report")
    if not data["evidence"] or squash(data["evidence"]) not in squash(report):
        problems.append("evidence must be copied word for word from the report")
    if len(str(data["summary"]).split()) > 50:
        problems.append("summary is longer than 40 words")
    return problems


# ---------------------------------------------------------------------------
# Step 2: plain code applies the rules and sets the deadlines
# ---------------------------------------------------------------------------

def minimum_priority(data):
    """The lowest priority the rules allow. The model can be stricter, never more lenient."""
    if not data["reportable"]:
        return "none", []
    reasons = []
    if data["category"] in RULES["priority_1"]["always_priority_1"]:
        reasons.append("this category is always Priority 1")
    if data["injury_needing_treatment"]:
        reasons.append("injury or discomfort needing treatment")
    if data["police_grounds"]:
        reasons.append("reasonable grounds to report to police")
    if data["category"] == "unexplained_absence" and data["reported_to_police"]:
        reasons.append("unexplained absence reported to police")
    return ("P1" if reasons else "P2"), reasons


def triage(data, report_name):
    aware = parse_time(data["became_aware"])
    required, reasons = minimum_priority(data)
    priority = data["priority"]
    escalated = data["reportable"] and required == "P1" and priority != "P1"
    if escalated:
        priority = "P1"
    result = {**data, "source": report_name, "model_priority": data["priority"], "priority": priority, "priority_reasons": reasons, "escalated": escalated}
    if priority == "P1":
        result["commission_by"] = aware + timedelta(hours=RULES["priority_1"]["hours"])
    elif priority == "P2":
        result["commission_by"] = aware + timedelta(days=RULES["priority_2"]["days"])
    if data["police_grounds"]:
        result["police_by"] = aware + timedelta(hours=RULES["police"]["hours"])
    return result


def read_report(client, model, path):
    report = path.read_text()
    body = request_body(model, report)
    problems = []
    for attempt in range(2):
        response = client.chat.completions.create(**body)
        content = response.choices[0].message.content or ""
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            data, problems = None, ["the reply was not valid JSON"]
        else:
            problems = reading_problems(data, report)
        if not problems:
            return {**triage(data, path.name), "corrected": attempt > 0}
        body = request_body(model, report, [
            {"role": "assistant", "content": content},
            {"role": "user", "content": "Fix these problems and reply with corrected JSON only: " + "; ".join(problems)},
        ])
    return {"source": path.name, "needs_review": problems}


def triage_folder(client, model, folder, workers=8):
    paths = sorted(Path(folder).glob("*.txt"))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(lambda p: read_report(client, model, p), paths))


# ---------------------------------------------------------------------------
# Step 3: the triage list
# ---------------------------------------------------------------------------

def when(dt):
    hour = dt.hour % 12 or 12
    return f"{dt:%a} {dt.day} {dt:%b %Y}, {hour}:{dt:%M}{'am' if dt.hour < 12 else 'pm'}"


def label(category):
    return category.replace("_", " ").capitalize()


def report_markdown(results):
    reportable = sorted([r for r in results if r.get("reportable")], key=lambda r: r["commission_by"])
    not_reportable = [r for r in results if r.get("reportable") is False]
    review = [r for r in results if r.get("needs_review")]
    p1 = [r for r in reportable if r["priority"] == "P1"]

    lines = ["# Serious incident triage", "",
             f"{len(results)} incident reports read. {len(p1)} Priority 1, {len(reportable) - len(p1)} Priority 2, "
             f"{len(not_reportable)} not reportable, {len(review)} for a person to read.", ""]
    if reportable:
        lines += ["## Report to the Commission, soonest first", "",
                  "| Report by | Priority | Resident | Incident | Police by |", "|---|---|---|---|---|"]
        for r in reportable:
            police = when(r["police_by"]) if r.get("police_by") else ""
            lines.append(f"| {when(r['commission_by'])} | {r['priority']} | {r['resident']} | "
                         f"{label(r['category'])} | {police} |")
        lines.append("")
        for r in reportable:
            lines += [f"### {r['resident']}: {label(r['category'])} ({r['priority']})", "",
                      r["summary"], "", f"> {r['evidence']}", "",
                      f"Staff became aware {when(parse_time(r['became_aware']))}. "
                      f"Notify the Commission by {when(r['commission_by'])}."]
            if r.get("police_by"):
                lines.append(f"Notify police by {when(r['police_by'])} if not already done.")
            if r["priority_reasons"]:
                lines.append("Priority 1 because: " + "; ".join(r["priority_reasons"]) + ".")
            lines += [f"Source: `{r['source']}`", ""]
    if not_reportable:
        lines += ["## Not reportable under SIRS", "", "Record and manage these through your incident management system.", ""]
        lines += [f"- {r['resident']}: {r['summary']} (`{r['source']}`)" for r in not_reportable] + [""]
    if review:
        lines += ["## For a person to read", ""]
        lines += [f"- `{r['source']}`: {'; '.join(r['needs_review'])}" for r in review] + [""]

    caught = [f"- {r['resident']}: the model said {r['model_priority']}, but the rules require Priority 1 "
              f"({'; '.join(r['priority_reasons'])}). Raised to P1 and the 24-hour deadline applied."
              for r in reportable if r.get("escalated")]
    caught += [f"- {r['resident']}: the model's first reading quoted text that is not in the report, or broke the "
               "format. It was sent back and corrected." for r in results if r.get("corrected")]
    if caught:
        lines += ["## What the checks caught", ""] + caught + [""]
    lines += [f"Rules from the Commission's published guidance, checked {RULES['checked']}: {RULES['source']}",
              "", f"{RULES['warning']} Every reporting decision is for an authorised person at the provider."]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--folder", default=HERE / "data" / "incidents", type=Path)
    parser.add_argument("--out", default=Path("output") / "aged-care-incidents", type=Path)
    parser.add_argument("--model", default=os.environ.get("CONTINUUM_MODEL", DEFAULT_MODEL))
    parser.add_argument("--workers", default=8, type=int)
    parser.add_argument("--demo", action="store_true", help="Run a scripted demonstration. No API key needed.")
    args = parser.parse_args()

    client = demo_client("aged_care_client") if args.demo else make_client()
    results = triage_folder(client, args.model, args.folder, args.workers)
    report = report_markdown(results)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "triage.md").write_text((DEMO_NOTE if args.demo else "") + report)
    (args.out / "triage.json").write_text(json.dumps(results, indent=2, default=str))
    print(report)
    print(f"\nSaved to {args.out}/")


if __name__ == "__main__":
    main()
