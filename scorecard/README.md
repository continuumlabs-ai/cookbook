# Australian work scorecard

How well do open AI models do real Australian work? This scorecard runs every recipe in the cookbook against each model and marks the results against published right answers.

The latest results are on the [`scorecard` branch](https://github.com/continuumlabs-ai/cookbook/tree/scorecard).

## The tasks

| Task | What is marked |
|---|---|
| Contract review | Status and clause for each of 8 policy topics |
| Research | An answer that passes the citation checks, the right conclusion and the figures that decide it |
| Announcements | Category, materiality and direction for 6 company announcements |
| Invoices | Where each of 6 supplier invoices should land, and the total read from each |
| Aged care incidents | Incident type and priority under SIRS for 6 reports |

The right answers are in [`answers.json`](answers.json). They are our judgement of fictional sample data. If you think one is wrong, open an issue.

## What the score means

Scores measure the model's own judgement, before each recipe's code checks step in. The checks still run, so the results also show how often the code had to catch something: a figure not in the source, a quote that isn't real, a priority set too low.

## Run it yourself

```bash
export CONTINUUM_API_KEY=your-key
export CONTINUUM_SCORECARD_MODELS="glm-5.2,gpt-oss-120b"
python scorecard/run.py
```

Any OpenAI-compatible endpoint works. Set `CONTINUUM_BASE_URL` to compare models elsewhere.
