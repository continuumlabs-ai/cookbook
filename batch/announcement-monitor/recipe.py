#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["openai>=1.40"]
# ///
"""Announcement monitor.

Reads a folder of company announcements and writes a morning digest that leads
with what matters. Each announcement is classified into a fixed structure, and
plain code checks the result: allowed categories only, required fields present,
and every key figure copied exactly from the source. Bad results are retried
once, then flagged for a person.

Run overnight on a schedule, or prepare a batch file for endpoints that offer batch processing.

Run:  python batch/announcement-monitor/recipe.py
      python batch/announcement-monitor/recipe.py --prepare-batch batch.jsonl
"""

import argparse
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

HERE = Path(__file__).parent
DEFAULT_BASE_URL = "https://api.continuumlabs.ai/v1"
DEFAULT_MODEL = "glm-5.2"
DEMO_NOTE = "> Demonstration output. The model's replies were scripted. Run without --demo for a live result.\n\n"

CATEGORIES = [
    "results",
    "guidance",
    "capital_raising",
    "acquisition_or_divestment",
    "management_change",
    "trading_halt",
    "governance_routine",
    "other",
]
DIRECTIONS = ["positive", "negative", "mixed", "neutral"]


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
# The structure every announcement is turned into
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = f"""You read company announcements for an investment team.
Classify the announcement. Reply with one JSON object only, with exactly these fields:

{{
  "company": "company name as written",
  "category": one of {json.dumps(CATEGORIES)},
  "material": true if a reasonable investor would expect it to affect the share price, otherwise false,
  "direction": one of {json.dumps(DIRECTIONS)},
  "headline": "what happened, in at most 15 words",
  "summary": "what it means for investors, in at most 50 words",
  "key_figures": ["numbers copied exactly as written in the announcement, e.g. \\"$85m\\""]
}}

Routine notices such as meeting results and small director trades are not material.
Do not add opinions or facts that are not in the announcement."""


def request_body(model, text, extra_messages=()):
    return {
        "model": model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
            *extra_messages,
        ],
    }


def squash(text):
    return re.sub(r"\s+", "", text).lower()


def check(result, source_text):
    """Validate one classification in plain code. Returns (clean_result, problems)."""
    problems = []
    if not isinstance(result, dict):
        return None, ["the reply was not a JSON object"]
    for field in ["company", "category", "material", "direction", "headline", "summary", "key_figures"]:
        if field not in result:
            problems.append(f"missing field '{field}'")
    if result.get("category") not in CATEGORIES:
        problems.append(f"category must be one of {CATEGORIES}")
    if result.get("direction") not in DIRECTIONS:
        problems.append(f"direction must be one of {DIRECTIONS}")
    if not isinstance(result.get("material"), bool):
        problems.append("material must be true or false")
    if len(str(result.get("headline", "")).split()) > 15:
        problems.append("headline is longer than 15 words")
    if len(str(result.get("summary", "")).split()) > 60:
        problems.append("summary is longer than 50 words")
    if problems:
        return None, problems

    # Keep only figures that really appear in the announcement. Drop the rest, and say so.
    figures = result.get("key_figures") or []
    verified = [f for f in figures if isinstance(f, str) and squash(f) and squash(f) in squash(source_text)]
    clean = dict(result)
    clean["key_figures"] = verified
    clean["dropped_figures"] = [f for f in figures if f not in verified]
    return clean, []


def classify(client, model, path):
    text = path.read_text()
    body = request_body(model, text)
    for attempt in range(2):
        response = client.chat.completions.create(**body)
        content = response.choices[0].message.content or ""
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            parsed, problems = None, ["the reply was not valid JSON"]
        else:
            parsed, problems = check(parsed, text)
        if parsed:
            parsed["source"] = path.name
            parsed["corrected"] = attempt > 0
            return parsed
        # Send the problems back once, so the model can correct itself.
        body = request_body(model, text, [
            {"role": "assistant", "content": content},
            {"role": "user", "content": "Fix these problems and reply with corrected JSON only: " + "; ".join(problems)},
        ])
    return {"source": path.name, "needs_review": True, "problems": problems}


def classify_folder(client, model, folder, workers=8):
    paths = sorted(Path(folder).glob("*.txt"))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(lambda p: classify(client, model, p), paths))


# ---------------------------------------------------------------------------
# Batch file: the same requests, written for overnight batch processing
# ---------------------------------------------------------------------------

def write_batch_file(model, folder, out_path):
    """One line per announcement, in the OpenAI-compatible batch format."""
    with open(out_path, "w") as f:
        for path in sorted(Path(folder).glob("*.txt")):
            line = {
                "custom_id": path.stem,
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": request_body(model, path.read_text()),
            }
            f.write(json.dumps(line) + "\n")


# ---------------------------------------------------------------------------
# The digest
# ---------------------------------------------------------------------------

DIRECTION_ORDER = {"negative": 0, "mixed": 1, "positive": 2, "neutral": 3}


def digest_markdown(results, day=None):
    today = date.today()
    day = day or f"{today.day} {today:%B %Y}"
    good = [r for r in results if not r.get("needs_review")]
    material = sorted([r for r in good if r["material"]], key=lambda r: DIRECTION_ORDER[r["direction"]])
    routine = [r for r in good if not r["material"]]
    review = [r for r in results if r.get("needs_review")]

    lines = [f"# Morning digest, {day}", "",
             f"{len(results)} announcements read. {len(material)} material. {len(review)} need a person to check.", ""]
    if material:
        lines += ["## What matters", ""]
        for r in material:
            lines += [f"### {r['company']}: {r['headline']}", "",
                      f"{r['direction'].capitalize()} · {r['category'].replace('_', ' ')}", "", r["summary"], ""]
            if r["key_figures"]:
                lines += ["Key figures: " + ", ".join(r["key_figures"]), ""]
    if routine:
        lines += ["## Routine", ""]
        lines += [f"- {r['company']}: {r['headline']}" for r in routine]
        lines.append("")
    if review:
        lines += ["## Needs review", ""]
        lines += [f"- {r['source']}: {'; '.join(r['problems'])}" for r in review]
        lines.append("")
    checks = [f"- {r['company']}: removed {', '.join(r['dropped_figures'])}, not found in the announcement."
              for r in good if r.get("dropped_figures")]
    checks += [f"- {r['company']}: first reply broke the format and was corrected." for r in good if r.get("corrected")]
    if checks:
        lines += ["## What the checks caught", ""] + checks
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--folder", default=HERE / "data" / "announcements", type=Path)
    parser.add_argument("--out", default=Path("output") / "announcement-monitor", type=Path)
    parser.add_argument("--model", default=os.environ.get("CONTINUUM_MODEL", DEFAULT_MODEL))
    parser.add_argument("--workers", default=8, type=int, help="How many announcements to read at once.")
    parser.add_argument("--prepare-batch", type=Path, help="Write a batch file instead of calling the model now.")
    parser.add_argument("--demo", action="store_true", help="Run a scripted demonstration. No API key needed.")
    args = parser.parse_args()

    if args.prepare_batch:
        write_batch_file(args.model, args.folder, args.prepare_batch)
        print(f"Batch file written to {args.prepare_batch}. Submit it through the batch endpoint.")
        return

    client = demo_client("announcement_monitor_client") if args.demo else make_client()
    results = classify_folder(client, args.model, args.folder, args.workers)
    digest = digest_markdown(results)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "digest.md").write_text((DEMO_NOTE if args.demo else "") + digest)
    (args.out / "classifications.json").write_text(json.dumps(results, indent=2))
    print(digest)
    print(f"\nSaved to {args.out}/")


if __name__ == "__main__":
    main()
