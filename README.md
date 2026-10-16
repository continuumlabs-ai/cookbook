# Continuum Labs Cookbook

Working recipes for building with open AI models on [Continuum Labs](https://continuumlabs.ai): world-class AI, run entirely in Australia.

Each recipe solves a real business task end to end. Copy it, run it, adapt it.

Every recipe works with the OpenAI Python SDK. Point it at Continuum and your data is processed in Australian data centres. Point it at any other OpenAI-compatible endpoint and it works there too.

## Quick start

```bash
git clone https://github.com/continuumlabs-ai/cookbook.git
cd cookbook
pip install -r requirements.txt
cp .env.example .env        # then add your key
python agents/contract-review/recipe.py
```

Settings are read from the environment:

| Variable | Default | Meaning |
|---|---|---|
| `CONTINUUM_API_KEY` | none | Your API key |
| `CONTINUUM_BASE_URL` | `https://api.continuumlabs.ai/v1` | Any OpenAI-compatible endpoint |
| `CONTINUUM_MODEL` | `glm-5.2` | Any model on the endpoint that supports tool calling |

## Recipes

### Agents

| Recipe | What it does | Shows | Status |
|---|---|---|---|
| [Contract review agent](agents/contract-review/) | Checks every clause of a contract against your policy playbook and drafts redlines | Tool calling, agent loop, coverage checks | Ready |
| [Research analyst agent](agents/research-analyst/) | Searches your own documents, answers with citations, then verifies every quote | Retrieval, citations, self-verification | Ready |
| Policy compliance checker | Tests procedures against a regulation, clause by clause | Structured output, long documents | Planned |
| Email triage agent | Sorts customer email, routes it and drafts replies | Classification, tool calling | Planned |
| Coding assistant, onshore | Connects open-source coding agents to an Australian endpoint | Integrations | Planned |

### Batch and extraction

| Recipe | What it does | Shows | Status |
|---|---|---|---|
| [Announcement monitor](batch/announcement-monitor/) | Reads a folder of company announcements overnight and writes a morning digest of what matters | Structured output, validation, concurrency, batch files | Ready |
| Financial statements to spreadsheet | Extracts tables from annual reports into clean data | Structured output | Planned |
| Meeting to minutes | Transcribes a recording, writes minutes and lists actions | Speech to text, summarisation | Planned |
| Private document search | Question and answer over internal files, embeddings kept onshore | Embeddings, retrieval | Planned |

### Works with

Short guides for connecting popular agent frameworks are planned: LangGraph, LlamaIndex, the OpenAI Agents SDK and the Vercel AI SDK.

## How every recipe is built

- **One file you can read top to bottom.** `recipe.py` holds the whole solution. No hidden framework.
- **Sample data included.** Every company, person and document in `data/` is fictional.
- **Checks the model's work.** Each recipe verifies the output in plain code, not just by asking the model again.
- **Tested.** `tests/` drives every recipe end to end with a stand-in model, so the logic is proven without spending tokens.

## Run the tests

```bash
python -m unittest discover -s tests -v
```

No API key or network is needed. The tests use a scripted stand-in for the model.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

MIT. See [LICENSE](LICENSE).
