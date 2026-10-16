# Research analyst agent

Answers a question from your own documents, cites every claim, and then checks its own citations.

**For:** analysts, risk and governance teams, and anyone who needs an answer they can defend to a board.

## What it does

Ask a question. The agent plans what it needs to know, runs several searches across your documents, reads the most relevant ones in full and writes a short answer. Every claim is marked with a citation, and every citation carries a quote from the source.

Then the answer is checked twice.

1. **In plain code.** Every quote must appear word for word in the document it cites. Every [n] marker must point to a real citation. If anything fails, the answer is sent back to the agent to fix. An invented quote cannot get through.
2. **By a second, strict model pass.** The answer is split into individual claims, and each claim is tested against its quoted evidence. Unsupported claims are listed in the report.

The sample library holds five internal documents from a fictional super fund. The default question asks whether its AI pilot is ready to launch. Example output:

```
Not yet. The Risk Committee requires at least 95% accuracy on 500 enquiries [1].
The pilot scored 93.4% [2], so the threshold is not met. ...

## Verification
Every quote was found word for word in its source document.
5 of 5 claims are supported by their cited evidence.
```

## How it works

```
question ──► agent ──► search_documents ──► read_document ──► submit_answer
                ▲                                                  │
                └──────── rejected: quote not in source ◄── check in code
                                                                   │ accepted
                                                                   ▼
                                                 claim-by-claim check ──► report
```

Search uses BM25, a standard keyword ranking, written in about 30 lines with no extra libraries. It works well for a few hundred documents. For thousands, swap `Library.search` for embedding search: the rest of the recipe stays the same.

## Try it now

No key needed. Demo mode replays a scripted model run through this recipe's real code.

```bash
uv run agents/research-analyst/recipe.py --demo
```

Or read the [example output](example-output/answer.md).

## Run it

```bash
export CONTINUUM_API_KEY=your-key
uv run agents/research-analyst/recipe.py
uv run agents/research-analyst/recipe.py --question "Why was Chatwell rejected?"
uv run agents/research-analyst/recipe.py --docs path/to/your/markdown/folder
```

## Make it yours

- **Point it at your documents.** Any folder of Markdown files works. Convert PDFs and Word files to Markdown first.
- **Tighten the rules.** Edit `SYSTEM_PROMPT` to require a minimum number of sources, or a set answer format.
- **Use a different checker model.** Pass a second model to `verify` so the answer is checked by a model that did not write it.

## Why keep it onshore

Board papers, risk minutes and vendor reviews are among the most sensitive documents an organisation holds. Run on Continuum, every request is processed in Australian data centres and nothing is stored.

## Sample data

Banksia Super, Chatwell and every document in `data/docs` are fictional.
