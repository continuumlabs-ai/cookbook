# Continuum Labs Cookbook

[![Recipes](https://github.com/continuumlabs-ai/cookbook/actions/workflows/ci.yml/badge.svg)](https://github.com/continuumlabs-ai/cookbook/actions/workflows/ci.yml)
[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/continuumlabs-ai/cookbook?quickstart=1)
[![MIT licence](https://img.shields.io/badge/licence-MIT-652c90.svg)](LICENSE)

Working AI agents for real business tasks. Copy one, run it, make it yours.

Built for [Continuum Labs](https://continuumlabs.ai): world-class AI, run entirely in Australia. Every recipe also works with any OpenAI-compatible endpoint.

## See one work in 60 seconds

No sign-up and no API key. Demo mode replays a scripted model run through the recipe's real code.

**In your browser.** Click **Open in GitHub Codespaces** above. When it opens, run:

```bash
python agents/contract-review/recipe.py --demo
```

**On your computer**, with [uv](https://docs.astral.sh/uv/) installed:

```bash
git clone https://github.com/continuumlabs-ai/cookbook.git && cd cookbook
uv run agents/contract-review/recipe.py --demo
```

`uv run` installs what each recipe needs automatically. Without uv, run `pip install -r requirements.txt` first and use `python` instead.

**Or just read the result.** Every recipe has an `example-output` folder.

## Run it for real

```bash
export CONTINUUM_API_KEY=your-key
uv run agents/contract-review/recipe.py
```

| Setting | Default | What it does |
|---|---|---|
| `CONTINUUM_API_KEY` | none | Your API key |
| `CONTINUUM_BASE_URL` | `https://api.continuumlabs.ai/v1` | Any OpenAI-compatible endpoint |
| `CONTINUUM_MODEL` | `glm-5.2` | Any model on that endpoint that supports tool calling |

## Recipes

| Recipe | What it does | Example output |
|---|---|---|
| [Contract review agent](agents/contract-review/) | Checks every clause of a contract against your policy playbook and drafts replacement wording | [Report](agents/contract-review/example-output/report.md) |
| [Research analyst agent](agents/research-analyst/) | Answers a question from your own documents with citations, then proves every quote is real | [Answer](agents/research-analyst/example-output/answer.md) |
| [Announcement monitor](batch/announcement-monitor/) | Reads overnight company announcements and writes a morning digest that leads with what matters | [Digest](batch/announcement-monitor/example-output/digest.md) |

### Coming next

Financial statements to spreadsheet. Meeting recording to minutes. Policy compliance checker. Email triage agent. Private document search. Guides for LangGraph, LlamaIndex, the OpenAI Agents SDK and the Vercel AI SDK.

## Why these recipes can be trusted

Most AI examples show the happy path. These show what happens when the model gets it wrong.

- **The code checks the model.** Findings must cite real clauses. Quotes must appear word for word in their source. Figures must appear in the announcement. When a check fails, the model is told why and asked to fix it.
- **Every report says what the checks caught.** You see the rejected quote, the removed figure, the corrected reply.
- **Nothing is skipped silently.** If an agent misses part of the job, the report says so.
- **One readable file.** Each `recipe.py` holds the whole solution. No framework to learn.
- **Tested.** Eleven tests run every recipe end to end on each change, without a key or network.

## Adapt a recipe with your coding assistant

Open the repository in Claude Code, Cursor, Copilot or any assistant that reads `AGENTS.md`, and ask in plain English:

> Adapt the contract review recipe to our supplier playbook in playbook.docx.

> Change the announcement monitor to put our portfolio holdings first.

`AGENTS.md` tells the assistant how the recipes are built and which rules to keep.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Every company, person and document in the sample data is fictional.

## Licence

MIT. See [LICENSE](LICENSE).
