# Announcement monitor

Reads a folder of company announcements and writes a morning digest that leads with what matters.

**For:** fund managers, wealth teams and analysts who start each day with a pile of overnight announcements.

## What it does

Each announcement is read and turned into the same structure: company, category, whether it is material, which way it cuts, a headline, a short summary and the key figures.

The digest puts material news first, with bad news at the top. Routine notices such as meeting results and small director trades drop to a single line. Anything the model could not classify properly is listed for a person to check.

```
# Morning digest, 16 October 2026

6 announcements read. 4 material. 0 need a person to check.

## What matters

### Ironbark Minerals Ltd: Production guidance cut after pit wall failure
Negative · guidance
...
```

## How it works

```
folder ──► read announcements in parallel ──► classify each into fixed JSON
                                                     │
                                         check in code: allowed values,
                                         required fields, figures in source
                                                     │
                                  fails? ──► one correction attempt ──► still fails? flag for review
                                                     │
                                                  digest
```

The checks are what make this safe to rely on.

1. **Fixed categories.** The model must choose from a set list. Anything else is sent back for correction.
2. **Every key figure is checked against the source.** A figure that does not appear in the announcement, word for word, is dropped and recorded. The digest never shows a number the company did not publish.
3. **No silent failures.** If a reply still fails after one correction, the announcement goes to "Needs review" rather than disappearing.

## Run it

```bash
export CONTINUUM_API_KEY=your-key
python batch/announcement-monitor/recipe.py
python batch/announcement-monitor/recipe.py --folder path/to/announcements --workers 16
```

### Half-price overnight runs

Work that can wait until morning does not need instant answers. Write the requests as a batch file instead:

```bash
python batch/announcement-monitor/recipe.py --prepare-batch tonight.jsonl
```

The file uses the standard OpenAI-compatible batch format. On Continuum, batch processing will run at half the normal price from launch.

## Make it yours

- **Feed it.** Point `--folder` at text exported from your announcements feed. Schedule it with cron for 5am.
- **Change the categories.** Edit `CATEGORIES` and the prompt together.
- **Filter for your portfolio.** Add a holdings list and move holdings to the top of the digest.

## Why keep it onshore

Which announcements a fund reads, and what it concludes, reveals its positions and its thinking. Run on Continuum, every request is processed in Australian data centres and nothing is stored.

## Sample data

Every company and announcement in `data/announcements` is fictional. The digest is a reading aid, not financial advice.
