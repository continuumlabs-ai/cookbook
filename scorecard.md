# Australian work scorecard

Run 8 November 2026 against `https://openrouter.ai/api/v1`.

Five real Australian tasks, marked against the right answers in [`answers.json`](answers.json). Scores are the model's own judgement, before the recipes' code checks step in.

| Model | Contract review | Research | Announcements | Invoices | Aged care incidents | Overall | Tokens | Time |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `z-ai/glm-5.2` | 100% | 100% | 94% | 100% | 92% | **97%** | 34,001 | 28s |

## What each model got wrong, and what the code caught

**`z-ai/glm-5.2`**

- Research: code sent back 1 draft
- Announcements: Brindle direction: positive
- Aged care incidents: 06: said P1, rules say P2

## How it is marked

- **Contract review:** status and clause for each of 8 policy topics.
- **Research:** an answer that passes the citation checks, the right conclusion, and the two figures that decide it.
- **Announcements:** category, materiality and direction for 6 announcements.
- **Invoices:** where each of 6 invoices should land, and the total read from each.
- **Aged care incidents:** incident type and the model's own priority for 6 reports.

All sample data is fictional. Rerun it yourself with `python scorecard/run.py`.