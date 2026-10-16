#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["openai>=1.40"]
# ///
"""Research analyst agent.

Answers a question from your own documents. The agent searches, reads, and
writes an answer where every claim carries a citation. Then two checks run:
plain code confirms every quoted passage really appears in the cited document,
and a second model pass tests whether each claim is supported by its evidence.

Run:  python agents/research-analyst/recipe.py
      python agents/research-analyst/recipe.py --question "What did the board approve?"
"""

import argparse
import json
import math
import os
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent
DEFAULT_BASE_URL = "https://api.continuumlabs.ai/v1"
DEFAULT_MODEL = "glm-5.2"
DEMO_NOTE = "> Demonstration output. The model's replies were scripted. Run without --demo for a live result.\n\n"
DEFAULT_QUESTION = "Is the member enquiry AI pilot ready for a wider launch? What conditions are still outstanding?"


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
# Search: a small BM25 keyword index over paragraphs. No extra dependencies.
# Swap in embeddings for large collections. See the README.
# ---------------------------------------------------------------------------

STOPWORDS = set("a an and are as at be by for from has have in is it its of on or that the this to was were will with".split())


def tokens(text):
    return [w for w in re.findall(r"[a-z0-9$%.]+", text.lower()) if w not in STOPWORDS]


class Library:
    def __init__(self, folder):
        self.docs = {p.stem: p.read_text() for p in sorted(Path(folder).glob("*.md"))}
        self.chunks = []  # (doc_id, text)
        for doc_id, text in self.docs.items():
            for para in re.split(r"\n\s*\n", text):
                para = para.strip()
                if para and not para.startswith("#"):
                    self.chunks.append((doc_id, para))
        self._tf = [Counter(tokens(t)) for _, t in self.chunks]
        self._len = [sum(tf.values()) for tf in self._tf]
        self._avg = sum(self._len) / max(len(self._len), 1)
        df = Counter(w for tf in self._tf for w in tf)
        n = len(self.chunks)
        self._idf = {w: math.log(1 + (n - d + 0.5) / (d + 0.5)) for w, d in df.items()}

    def search(self, query, top_k=5, k1=1.5, b=0.75):
        q = tokens(query)
        scored = []
        for i, tf in enumerate(self._tf):
            score = 0.0
            for w in q:
                if w in tf:
                    f = tf[w]
                    score += self._idf[w] * f * (k1 + 1) / (f + k1 * (1 - b + b * self._len[i] / self._avg))
            if score > 0:
                scored.append((score, i))
        scored.sort(reverse=True)
        return [{"doc_id": self.chunks[i][0], "text": self.chunks[i][1]} for _, i in scored[:top_k]]


def normalise(text):
    return re.sub(r"\s+", " ", text).strip().lower()


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_documents",
            "description": "Keyword search across the document library. Returns matching passages and their document ids.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}, "top_k": {"type": "integer", "default": 5}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_document",
            "description": "Read one whole document by its id.",
            "parameters": {"type": "object", "properties": {"doc_id": {"type": "string"}}, "required": ["doc_id"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit_answer",
            "description": "Submit the final answer. Mark each claim with [n], where n is the number of its citation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "answer": {"type": "string"},
                    "citations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "doc_id": {"type": "string"},
                                "quote": {"type": "string", "description": "Copied word for word from the document."},
                            },
                            "required": ["doc_id", "quote"],
                        },
                    },
                },
                "required": ["answer", "citations"],
            },
        },
    },
]

SYSTEM_PROMPT = """You are a careful research analyst. Answer the question using only the document library.

Work like this:
1. Plan the facts you need. Search for each one, using several different searches.
2. Read the most relevant documents in full.
3. Submit an answer of a few short paragraphs. Put [1], [2] and so on after each claim.
   Citation 1 is the first item in the citations list, citation 2 the second, and so on.
   Each citation's quote must be copied word for word from the document. Keep quotes short.
   Every figure in a sentence must appear in a quote that sentence cites.
If the library does not answer part of the question, say so plainly. Never guess."""


# A figure worth checking: a percentage, a dollar amount, a decimal, or a number of three or more digits.
# Years such as 2026 are left alone.
FIGURE = re.compile(r"\$?\d[\d,]*(?:\.\d+)?%?")


def figures_in(text):
    found = set()
    for raw in FIGURE.findall(text):
        value = raw.replace(",", "").rstrip(".")
        digits = value.strip("$%")
        if re.fullmatch(r"(19|20)\d\d", digits):
            continue
        if "%" in value or "$" in value or "." in digits or len(digits) >= 3:
            found.add(value)
    return found


def unsupported_figures(answer, citations):
    """Check 2, in plain code: every figure in a cited sentence must appear in a quote that sentence cites."""
    problems = []
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", answer):
        cited = [int(m) for m in re.findall(r"\[(\d+)\]", sentence)]
        if not cited:
            continue
        quotes = " ".join(str(citations[n - 1].get("quote", "")) for n in cited if 1 <= n <= len(citations))
        quote_figures = {f.strip("$") for f in figures_in(quotes)}
        text = re.sub(r"\[\d+\]", "", sentence)
        for figure in sorted(figures_in(text)):
            if figure.strip("$") not in quote_figures:
                short = sentence.strip()[:90]
                problems.append(
                    f"the figure {figure} in \"{short}\" is not in the quote it cites. "
                    "Cite a quote that contains it, or remove it"
                )
    return problems


class Session:
    def __init__(self, library):
        self.library = library
        self.answer = None
        self.citations = []
        self.rejections = []  # what the citation check caught

    def handle(self, name, args):
        if name == "search_documents":
            hits = self.library.search(str(args.get("query", "")), int(args.get("top_k", 5) or 5))
            return json.dumps(hits) if hits else "No matching passages. Try other words."
        if name == "read_document":
            doc_id = str(args.get("doc_id", ""))
            if doc_id not in self.library.docs:
                return f"Error: no document '{doc_id}'. Documents: {', '.join(self.library.docs)}."
            return self.library.docs[doc_id]
        if name == "submit_answer":
            return self._check_answer(args)
        return f"Error: unknown tool '{name}'."

    def _check_answer(self, args):
        """Check 1, in plain code: every citation must exist, and every quote must really be in its document."""
        answer = str(args.get("answer", "")).strip()
        citations = args.get("citations") or []
        problems = []
        if not answer:
            problems.append("the answer is empty")
        if not citations:
            problems.append("there are no citations")
        for n, c in enumerate(citations, start=1):
            doc = self.library.docs.get(str(c.get("doc_id", "")))
            if doc is None:
                problems.append(f"citation {n} names a document that does not exist")
            elif normalise(str(c.get("quote", ""))) not in normalise(doc):
                problems.append(f"citation {n}'s quote does not appear word for word in {c.get('doc_id')}")
        used = {int(m) for m in re.findall(r"\[(\d+)\]", answer)}
        for n in sorted(used):
            if n < 1 or n > len(citations):
                problems.append(f"the answer refers to [{n}] but there is no citation {n}")
        if not problems:
            problems += unsupported_figures(answer, citations)
        if problems:
            self.rejections.append(problems)
            return "Error: answer not accepted. Fix these and submit again: " + "; ".join(problems) + "."
        self.answer, self.citations = answer, citations
        return "Answer accepted."


def assistant_message(msg):
    out = {"role": "assistant", "content": msg.content or ""}
    if msg.tool_calls:
        out["tool_calls"] = [
            {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
            for tc in msg.tool_calls
        ]
    return out


def research(client, model, library, question, max_turns=20):
    session = Session(library)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Documents in the library: {', '.join(library.docs)}\n\nQuestion: {question}"},
    ]
    for _ in range(max_turns):
        response = client.chat.completions.create(model=model, messages=messages, tools=TOOLS, temperature=0)
        msg = response.choices[0].message
        messages.append(assistant_message(msg))
        if not msg.tool_calls:
            messages.append({"role": "user", "content": "Use the tools. Finish by calling submit_answer."})
            continue
        for call in msg.tool_calls:
            try:
                args = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                result = "Error: arguments were not valid JSON."
            else:
                result = session.handle(call.function.name, args)
            messages.append({"role": "tool", "tool_call_id": call.id, "content": result})
        if session.answer:
            break
    return session


# ---------------------------------------------------------------------------
# Check 2: does the evidence support each claim? A separate, strict model pass.
# ---------------------------------------------------------------------------

VERIFY_PROMPT = """You check research answers. You are strict.
Split the answer into its individual claims. For each claim, decide whether the cited quotes support it.
Reply with JSON only, in this shape:
{"claims": [{"claim": "...", "citations": [1], "supported": true, "reason": "..."}]}"""


def verify(client, model, answer, citations):
    evidence = "\n".join(f"[{n}] ({c['doc_id']}) {c['quote']}" for n, c in enumerate(citations, start=1))
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": VERIFY_PROMPT},
            {"role": "user", "content": f"Answer:\n{answer}\n\nCited evidence:\n{evidence}"},
        ],
    )
    try:
        claims = json.loads(response.choices[0].message.content)["claims"]
        return [c for c in claims if isinstance(c, dict) and "claim" in c and "supported" in c]
    except (json.JSONDecodeError, KeyError, TypeError):
        return None  # Report that verification could not run, rather than pretend it passed.


def report_markdown(question, session, claims):
    lines = ["# Research answer", "", f"**Question:** {question}", ""]
    if not session.answer:
        lines += ["The agent did not produce an answer that passed the citation check.", ""]
        return "\n".join(lines)
    lines += [session.answer, "", "## Sources", ""]
    for n, c in enumerate(session.citations, start=1):
        lines.append(f"{n}. {c['doc_id']}: “{c['quote']}”")
    lines += ["", "## Verification", "", "Every quote was found word for word in its source document, and every figure in the answer appears in a quote it cites."]
    for problems in session.rejections:
        lines.append(f"An earlier draft was rejected and corrected: {'; '.join(problems)}.")
    lines.append("")
    if claims is None:
        lines.append("The claim-by-claim check could not run. Review the answer by hand.")
    else:
        weak = [c for c in claims if not c.get("supported")]
        lines.append(f"{len(claims) - len(weak)} of {len(claims)} claims are supported by their cited evidence.")
        for c in weak:
            lines.append(f"- Not supported: {c['claim']} ({c.get('reason', 'no reason given')})")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--question", default=DEFAULT_QUESTION)
    parser.add_argument("--docs", default=HERE / "data" / "docs", type=Path)
    parser.add_argument("--out", default=Path("output") / "research-analyst", type=Path)
    parser.add_argument("--model", default=os.environ.get("CONTINUUM_MODEL", DEFAULT_MODEL))
    parser.add_argument("--demo", action="store_true", help="Run a scripted demonstration. No API key needed.")
    args = parser.parse_args()

    client = demo_client("research_analyst_client") if args.demo else make_client()
    library = Library(args.docs)
    session = research(client, args.model, library, args.question)
    claims = verify(client, args.model, session.answer, session.citations) if session.answer else None

    report = report_markdown(args.question, session, claims)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "answer.md").write_text((DEMO_NOTE if args.demo else "") + report)
    (args.out / "answer.json").write_text(
        json.dumps({"question": args.question, "answer": session.answer, "citations": session.citations,
                    "claims": claims}, indent=2)
    )
    print(report)
    print(f"\nSaved to {args.out}/")


if __name__ == "__main__":
    main()
