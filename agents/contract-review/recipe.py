#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["openai>=1.40"]
# ///
"""Contract review agent.

Checks every clause of a contract against your organisation's policy playbook.
For each policy it finds the relevant clause, decides whether the clause complies,
rates the risk and drafts a redline. Plain code then checks that every policy was
covered, so nothing is silently skipped.

Run:  python agents/contract-review/recipe.py
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
DEFAULT_BASE_URL = "https://api.continuumlabs.ai/v1"
DEFAULT_MODEL = "glm-5.2"
DEMO_NOTE = "> Demonstration output. The model's replies were scripted. Run without --demo for a live result.\n\n"

STATUSES = {"compliant", "exception", "missing"}
RISKS = {"low", "medium", "high"}


# ---------------------------------------------------------------------------
# Connecting to the model
# ---------------------------------------------------------------------------

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
# The contract and the playbook
# ---------------------------------------------------------------------------

def split_clauses(contract_text):
    """Turn '## 7. Liability' style headings into {'7': {'title': ..., 'text': ...}}."""
    clauses = {}
    parts = re.split(r"^## (\d+)\.\s+(.+)$", contract_text, flags=re.MULTILINE)
    # parts = [preamble, number, title, body, number, title, body, ...]
    for i in range(1, len(parts) - 2, 3):
        clauses[parts[i]] = {"title": parts[i + 1].strip(), "text": parts[i + 2].strip()}
    return clauses


# ---------------------------------------------------------------------------
# The tools the agent can use
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_policy",
            "description": "Read the organisation's rule for one policy topic.",
            "parameters": {
                "type": "object",
                "properties": {"topic": {"type": "string", "description": "A topic from the policy list."}},
                "required": ["topic"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_clause",
            "description": "Read the full text of one contract clause by its number.",
            "parameters": {
                "type": "object",
                "properties": {"number": {"type": "string", "description": "Clause number, e.g. '7'."}},
                "required": ["number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "record_finding",
            "description": "Record your conclusion for one policy topic. Call once per topic.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                    "clause": {"type": "string", "description": "Clause number, or 'none' if no clause addresses the topic."},
                    "status": {"type": "string", "enum": sorted(STATUSES)},
                    "risk": {"type": "string", "enum": sorted(RISKS)},
                    "explanation": {"type": "string", "description": "One or two plain sentences."},
                    "suggested_redline": {"type": "string", "description": "Replacement wording, or '' if compliant."},
                },
                "required": ["topic", "clause", "status", "risk", "explanation", "suggested_redline"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish",
            "description": "Finish the review once every policy topic has a finding.",
            "parameters": {
                "type": "object",
                "properties": {"summary": {"type": "string", "description": "Three sentences for a busy executive."}},
                "required": ["summary"],
            },
        },
    },
]


class Review:
    """Holds the review's state and carries out each tool call."""

    def __init__(self, clauses, playbook):
        self.clauses = clauses
        self.policies = playbook["policies"]
        self.organisation = playbook.get("organisation", "the organisation")
        self.findings = {}
        self.summary = ""
        self.done = False
        self.rejected = 0  # findings the code sent back for correction

    def outstanding(self):
        return [t for t in self.policies if t not in self.findings]

    def handle(self, name, args):
        """Run one tool call. Errors go back to the model so it can correct itself."""
        if name == "get_policy":
            topic = args.get("topic", "")
            if topic not in self.policies:
                return f"Error: unknown topic '{topic}'. Topics: {', '.join(self.policies)}."
            return self.policies[topic]["rule"]

        if name == "read_clause":
            number = str(args.get("number", "")).strip().rstrip(".")
            if number not in self.clauses:
                return f"Error: no clause {number}. Clauses: {', '.join(self.clauses)}."
            c = self.clauses[number]
            return f"Clause {number}. {c['title']}\n{c['text']}"

        if name == "record_finding":
            problems = []
            if args.get("topic") not in self.policies:
                problems.append(f"topic must be one of: {', '.join(self.policies)}")
            if args.get("status") not in STATUSES:
                problems.append(f"status must be one of: {', '.join(sorted(STATUSES))}")
            if args.get("risk") not in RISKS:
                problems.append(f"risk must be one of: {', '.join(sorted(RISKS))}")
            clause = str(args.get("clause", "")).strip().rstrip(".")
            if clause != "none" and clause not in self.clauses:
                problems.append(f"clause must be a clause number ({', '.join(self.clauses)}) or 'none'")
            if not str(args.get("explanation", "")).strip():
                problems.append("explanation is required")
            if problems:
                self.rejected += 1
                return "Error: finding not recorded. " + "; ".join(problems) + "."
            self.findings[args["topic"]] = {
                "topic": args["topic"],
                "clause": clause,
                "status": args["status"],
                "risk": args["risk"],
                "explanation": args["explanation"].strip(),
                "suggested_redline": str(args.get("suggested_redline", "")).strip(),
            }
            left = self.outstanding()
            return f"Recorded. Topics still to review: {', '.join(left) if left else 'none'}."

        if name == "finish":
            left = self.outstanding()
            if left:
                return f"Error: cannot finish yet. Record findings for: {', '.join(left)}."
            self.summary = str(args.get("summary", "")).strip()
            self.done = True
            return "Review complete."

        return f"Error: unknown tool '{name}'."


# ---------------------------------------------------------------------------
# The agent loop
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You review supplier contracts for {organisation}.

Work through every policy topic in the list. For each topic:
1. Call get_policy to read the rule.
2. Call read_clause on the clause or clauses that deal with it.
3. Call record_finding once with your conclusion.

Status: "compliant" if the clause meets the rule, "exception" if it does not,
"missing" if no clause deals with the topic (use clause "none").
Risk: use the policy's stated risk for exceptions and missing topics, "low" when compliant.
A redline is replacement wording that would make the clause comply. Leave it empty when compliant.
Be precise. Quote numbers from the contract. Do not invent clauses.
When every topic has a finding, call finish with a three-sentence summary."""


def assistant_message(msg):
    """Convert a model reply into a message we can send back in the next request."""
    out = {"role": "assistant", "content": msg.content or ""}
    if msg.tool_calls:
        out["tool_calls"] = [
            {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
            for tc in msg.tool_calls
        ]
    return out


def review_contract(client, model, contract_text, playbook, max_turns=40):
    clauses = split_clauses(contract_text)
    review = Review(clauses, playbook)
    risk_by_topic = {t: p.get("risk_if_breached", "medium") for t, p in review.policies.items()}

    index = "\n".join(f"{n}. {c['title']}" for n, c in clauses.items())
    topics = "\n".join(f"- {t} (risk if breached: {risk_by_topic[t]})" for t in review.policies)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT.format(organisation=review.organisation)},
        {"role": "user", "content": f"Contract clauses:\n{index}\n\nPolicy topics:\n{topics}\n\nBegin the review."},
    ]
    usage = {"prompt_tokens": 0, "completion_tokens": 0}

    for _ in range(max_turns):
        response = client.chat.completions.create(model=model, messages=messages, tools=TOOLS, temperature=0)
        for key in usage:
            usage[key] += getattr(response.usage, key, 0) or 0
        msg = response.choices[0].message
        messages.append(assistant_message(msg))

        if not msg.tool_calls:
            if review.done:
                break
            # The model stopped talking to its tools early. Point it back at the work.
            messages.append({
                "role": "user",
                "content": f"Keep going. Record findings for: {', '.join(review.outstanding())}. Then call finish.",
            })
            continue

        for call in msg.tool_calls:
            try:
                args = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                result = "Error: arguments were not valid JSON. Try again."
            else:
                result = review.handle(call.function.name, args)
            messages.append({"role": "tool", "tool_call_id": call.id, "content": result})

        if review.done:
            break

    # Safety net in plain code: anything the agent did not cover is flagged for a person.
    for topic in review.outstanding():
        review.findings[topic] = {
            "topic": topic,
            "clause": "unknown",
            "status": "not_reviewed",
            "risk": "high",
            "explanation": "The agent did not record a finding for this topic. Review it by hand.",
            "suggested_redline": "",
        }
    return review, usage


# ---------------------------------------------------------------------------
# The report
# ---------------------------------------------------------------------------

RISK_ORDER = {"high": 0, "medium": 1, "low": 2}


def report_markdown(review):
    rows = sorted(review.findings.values(), key=lambda f: (f["status"] == "compliant", RISK_ORDER.get(f["risk"], 0)))
    issues = [f for f in rows if f["status"] != "compliant"]
    lines = ["# Contract review", ""]
    if review.summary:
        lines += [review.summary, ""]
    lines += [f"{len(issues)} of {len(rows)} policy topics need attention.", ""]
    if review.rejected:
        lines += [f"The code rejected {review.rejected} malformed finding(s), which the agent then corrected.", ""]
    skipped = [f["topic"] for f in rows if f["status"] == "not_reviewed"]
    if skipped:
        lines += [f"Not reviewed by the agent, so check by hand: {', '.join(skipped)}.", ""]
    lines += ["| Topic | Clause | Status | Risk |", "|---|---|---|---|"]
    for f in rows:
        lines.append(f"| {f['topic'].replace('_', ' ')} | {f['clause']} | {f['status']} | {f['risk']} |")
    lines.append("")
    for f in issues:
        lines += [f"## {f['topic'].replace('_', ' ').capitalize()} (clause {f['clause']})", "", f["explanation"], ""]
        if f["suggested_redline"]:
            lines += ["Suggested wording:", "", f"> {f['suggested_redline']}", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--contract", default=HERE / "data" / "contract.md", type=Path)
    parser.add_argument("--playbook", default=HERE / "data" / "playbook.json", type=Path)
    parser.add_argument("--out", default=Path("output") / "contract-review", type=Path)
    parser.add_argument("--model", default=os.environ.get("CONTINUUM_MODEL", DEFAULT_MODEL))
    parser.add_argument("--demo", action="store_true", help="Run a scripted demonstration. No API key needed.")
    args = parser.parse_args()

    client = demo_client("contract_review_client") if args.demo else make_client()
    review, usage = review_contract(
        client, args.model, args.contract.read_text(), json.loads(args.playbook.read_text())
    )
    args.out.mkdir(parents=True, exist_ok=True)
    report = report_markdown(review)
    (args.out / "report.md").write_text((DEMO_NOTE if args.demo else "") + report)
    (args.out / "report.json").write_text(
        json.dumps({"summary": review.summary, "findings": list(review.findings.values()), "usage": None if args.demo else usage}, indent=2)
    )
    print(report)
    if not args.demo:
        print(f"\nTokens used: {usage['prompt_tokens']:,} sent, {usage['completion_tokens']:,} received.")
    print(f"Saved to {args.out}/")


if __name__ == "__main__":
    main()
