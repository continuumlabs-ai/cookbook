#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["openai>=1.40"]
# ///
"""The Australian work scorecard.

Runs every recipe in this cookbook against one or more models and marks the
results against published right answers in answers.json. Each task is real
Australian work: a contract against a policy playbook, a research question
over board papers, overnight ASX-style announcements, supplier invoices with
GST and ABN problems, and aged care incident reports under SIRS.

Scores measure the model's own judgement, before the recipes' code checks
correct anything. The checks still run, so every task also shows how much
the code had to catch.

Run:  CONTINUUM_SCORECARD_MODELS="glm-5.2,gpt-oss-120b" python scorecard/run.py
"""

import argparse
import importlib.util
import json
import os
import re
import sys
import threading
import time
from datetime import date
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))
ANSWERS = json.loads((Path(__file__).parent / "answers.json").read_text())


def load(path):
    spec = importlib.util.spec_from_file_location(path.replace("/", "_").replace("-", "_"), ROOT / path / "recipe.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CountingClient:
    """Wraps a client to count calls and tokens, whichever recipe is using it."""

    def __init__(self, client):
        self._client = client
        self._lock = threading.Lock()
        self.calls = self.prompt_tokens = self.completion_tokens = 0
        self.chat = type("Chat", (), {})()
        self.chat.completions = type("Completions", (), {})()
        self.chat.completions.create = self._create

    def _create(self, **kwargs):
        response = self._client.chat.completions.create(**kwargs)
        usage = getattr(response, "usage", None)
        with self._lock:
            self.calls += 1
            self.prompt_tokens += getattr(usage, "prompt_tokens", 0) or 0
            self.completion_tokens += getattr(usage, "completion_tokens", 0) or 0
        return response


# ---------------------------------------------------------------------------
# One marking function per task. Each returns (points, out_of, notes).
# ---------------------------------------------------------------------------

def contract_review(client, model):
    recipe = load("agents/contract-review")
    data = recipe.HERE / "data"
    review, _ = recipe.review_contract(client, model, (data / "contract.md").read_text(),
                                       json.loads((data / "playbook.json").read_text()))
    points, notes = 0, []
    for topic, right in ANSWERS["contract_review"].items():
        found = review.findings.get(topic, {})
        points += found.get("status") == right["status"]
        points += str(found.get("clause")) == right["clause"]
        if found.get("status") != right["status"]:
            notes.append(f"{topic}: said {found.get('status', 'nothing')}")
    if review.rejected:
        notes.append(f"code sent back {review.rejected} findings")
    return points, 2 * len(ANSWERS["contract_review"]), notes


def research_analyst(client, model):
    recipe = load("agents/research-analyst")
    session = recipe.research(client, model, recipe.Library(recipe.HERE / "data" / "docs"), recipe.DEFAULT_QUESTION)
    right = ANSWERS["research_analyst"]
    answer = session.answer or ""
    points = int(bool(session.answer))
    points += bool(re.search(right["not_ready_pattern"], answer, re.I))
    points += sum(figure in answer for figure in right["must_mention"])
    notes = [] if session.answer else ["no answer passed the citation checks"]
    if session.rejections:
        notes.append(f"code sent back {len(session.rejections)} drafts")
    return points, 2 + len(right["must_mention"]), notes


def announcement_monitor(client, model):
    recipe = load("batch/announcement-monitor")
    results = recipe.classify_folder(client, model, recipe.HERE / "data" / "announcements", workers=6)
    by_company = {r.get("company"): r for r in results if not r.get("needs_review")}
    points, notes = 0, []
    for company, right in ANSWERS["announcement_monitor"].items():
        got = by_company.get(company, {})
        for field, value in right.items():
            if got.get(field) == value:
                points += 1
            else:
                notes.append(f"{company.split()[0]} {field}: {got.get(field, 'missing')}")
    dropped = sum(len(r.get("dropped_figures", [])) for r in results)
    if dropped:
        notes.append(f"code removed {dropped} figures not in the source")
    return points, 3 * len(ANSWERS["announcement_monitor"]), notes


def bookkeeper_invoices(client, model):
    recipe = load("jobs/bookkeeper-invoices")
    results = recipe.process_folder(client, model, recipe.HERE / "data" / "invoices", workers=6)
    by_file = {r["source"]: r for r in results}
    points, out_of, notes = 0, 0, []
    for name, right in ANSWERS["bookkeeper_invoices"].items():
        got = by_file.get(name, {})
        out_of += 1
        if got.get("status") == right["status"]:
            points += 1
        else:
            notes.append(f"{name[:2]}: {got.get('status', 'missing')} not {right['status']}")
        if "total" in right:
            out_of += 1
            total = (got.get("data") or {}).get("total_inc_gst")
            points += recipe.checks.money(total) == Decimal(right["total"]) if total else 0
    corrected = sum(1 for r in results if r.get("corrected"))
    if corrected:
        notes.append(f"code sent back {corrected} misread invoices")
    return points, out_of, notes


def aged_care_incidents(client, model):
    recipe = load("jobs/aged-care-incidents")
    results = recipe.triage_folder(client, model, recipe.HERE / "data" / "incidents", workers=6)
    by_file = {r["source"]: r for r in results}
    points, notes = 0, []
    for name, right in ANSWERS["aged_care_incidents"].items():
        got = by_file.get(name, {})
        points += got.get("category") == right["category"]
        model_priority = got.get("model_priority", got.get("priority"))
        points += model_priority == right["priority"]
        if model_priority != right["priority"]:
            notes.append(f"{name[:2]}: said {model_priority or 'nothing'}, rules say {right['priority']}")
    escalated = sum(1 for r in results if r.get("escalated"))
    if escalated:
        notes.append(f"code raised {escalated} priorities")
    return points, 2 * len(ANSWERS["aged_care_incidents"]), notes


TASKS = [
    ("Contract review", contract_review),
    ("Research", research_analyst),
    ("Announcements", announcement_monitor),
    ("Invoices", bookkeeper_invoices),
    ("Aged care incidents", aged_care_incidents),
]


def score_model(raw_client, model):
    row = {"model": model, "tasks": {}, "seconds": 0.0}
    client = CountingClient(raw_client)
    for name, task in TASKS:
        started = time.time()
        try:
            points, out_of, notes = task(client, model)
            row["tasks"][name] = {"points": points, "out_of": out_of, "notes": notes}
        except Exception as e:  # a model that cannot do the task scores zero, with the reason
            row["tasks"][name] = {"points": 0, "out_of": 1, "notes": [f"failed: {type(e).__name__}: {str(e)[:120]}"]}
        row["tasks"][name]["seconds"] = round(time.time() - started, 1)
        row["seconds"] += row["tasks"][name]["seconds"]
        print(f"  {name}: {row['tasks'][name]['points']}/{row['tasks'][name]['out_of']}", flush=True)
    row["overall"] = round(100 * sum(t["points"] / t["out_of"] for t in row["tasks"].values()) / len(TASKS))
    row["calls"], row["prompt_tokens"], row["completion_tokens"] = client.calls, client.prompt_tokens, client.completion_tokens
    return row


def markdown(rows, endpoint):
    today = date.today()
    names = [n for n, _ in TASKS]
    lines = ["# Australian work scorecard", "",
             f"Run {today.day} {today:%B %Y} against `{endpoint}`.", "",
             "Five real Australian tasks, marked against the right answers in "
             "[`answers.json`](answers.json). Scores are the model's own judgement, before the recipes' code checks "
             "step in.", "",
             "| Model | " + " | ".join(names) + " | Overall | Tokens | Time |",
             "|---|" + "---:|" * (len(names) + 3)]
    for r in sorted(rows, key=lambda r: -r["overall"]):
        cells = [f"{round(100 * r['tasks'][n]['points'] / r['tasks'][n]['out_of'])}%" for n in names]
        tokens = r["prompt_tokens"] + r["completion_tokens"]
        lines.append(f"| `{r['model']}` | " + " | ".join(cells) +
                     f" | **{r['overall']}%** | {tokens:,} | {round(r['seconds'])}s |")
    lines += ["", "## What each model got wrong, and what the code caught", ""]
    for r in rows:
        notes = [f"{n}: {'; '.join(r['tasks'][n]['notes'])}" for n in names if r["tasks"][n]["notes"]]
        lines += [f"**`{r['model']}`**", ""] + ([f"- {n}" for n in notes] or ["- Nothing."]) + [""]
    lines += ["## How it is marked", "",
              "- **Contract review:** status and clause for each of 8 policy topics.",
              "- **Research:** an answer that passes the citation checks, the right conclusion, and the two figures that decide it.",
              "- **Announcements:** category, materiality and direction for 6 announcements.",
              "- **Invoices:** where each of 6 invoices should land, and the total read from each.",
              "- **Aged care incidents:** incident type and the model's own priority for 6 reports.", "",
              "All sample data is fictional. Rerun it yourself with `python scorecard/run.py`."]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--models", default=os.environ.get("CONTINUUM_SCORECARD_MODELS")
                        or os.environ.get("CONTINUUM_MODEL", "glm-5.2"))
    parser.add_argument("--out", default=Path("output") / "scorecard", type=Path)
    args = parser.parse_args()

    client = load("batch/announcement-monitor").make_client()
    endpoint = os.environ.get("CONTINUUM_BASE_URL", "https://api.continuumlabs.ai/v1")
    rows = []
    for model in [m.strip() for m in args.models.split(",") if m.strip()]:
        print(f"Scoring {model}", flush=True)
        rows.append(score_model(client, model))
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "scorecard.md").write_text(markdown(rows, endpoint))
    (args.out / "scorecard.json").write_text(json.dumps({"endpoint": endpoint, "date": str(date.today()), "rows": rows}, indent=2))
    print(markdown(rows, endpoint))


if __name__ == "__main__":
    main()
