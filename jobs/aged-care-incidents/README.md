# Aged care: serious incident triage

Reads incident reports and works out which must be reported under the Serious Incident Response Scheme, at what priority, and by when.

**For:** clinical care managers, quality and risk leads, and facility managers in residential and home aged care.

## What it does

Each incident report is read and classified against the scheme's eight incident types. The result is one list, soonest deadline first, with the evidence from each report quoted beside it.

```
# Serious incident triage

6 incident reports read. 3 Priority 1, 2 Priority 2, 1 not reportable, 0 for a person to read.

| Report by               | Priority | Resident | Incident                                | Police by |
|-------------------------|----------|----------|-----------------------------------------|-----------|
| Thu 15 Oct 2026, 3:05pm | P1       | R.T.     | Unexplained absence                     |           |
| Fri 16 Oct 2026, 6:45am | P1       | M.K.     | Unreasonable use of force               | Fri 16 Oct 2026, 6:45am |
```

## The checks

Deadlines matter too much to leave to a model. These run in plain code.

1. **Priority rules are enforced.** The model can be stricter than the rules, never more lenient. If it calls an incident Priority 2 when there are grounds to involve police, or injury needing treatment, the code raises it to Priority 1 and says why.
2. **Deadlines are calculated, not guessed.** 24 hours or 30 days from the moment staff became aware, read from the report. Police within 24 hours where a crime is suspected.
3. **Evidence must be real.** The passage the model relies on must appear word for word in the report. A paraphrase is sent back for correction.
4. **Impossible answers are refused.** An unknown category, or a reportable incident with no priority, is sent back.

The rules live in [`data/sirs-rules.json`](data/sirs-rules.json), with the source and the date they were checked. Update that file, not the code, when guidance changes.

## Try it now

No key needed. Demo mode replays a scripted model run through this recipe's real code.

```bash
uv run jobs/aged-care-incidents/recipe.py --demo
```

Or read the [example triage list](example-output/triage.md).

## Run it

```bash
export CONTINUUM_API_KEY=your-key
uv run jobs/aged-care-incidents/recipe.py --folder path/to/incident-reports
```

Each report needs a line giving the time staff became aware, such as `Time staff became aware: 14/10/2026 15:05`.

## Make it yours

- **Connect your incident system.** Export new reports as text each hour and run the recipe on a schedule.
- **Alert the right person.** Send Priority 1 items to the on-call manager by SMS or Teams the moment they appear.
- **Draft the notice.** Each summary is written to suit the Commission's notification form. Add the fields your provider portal asks for.

## Important

This recipe helps a person triage faster. It does not decide what to report. Every reporting decision is for an authorised person at the provider. The Commission is updating its guidance for the Aged Care Act 2024, which applies from 1 November 2025, so check the rules file against the [Commission's current guidance](https://www.agedcarequality.gov.au/providers/serious-incident-response-scheme) before relying on it.

## Why keep it onshore

Incident reports are health information about some of the most vulnerable people in the country. Run on Continuum, every request is processed in Australian data centres and nothing is stored.

## Sample data

The provider, residents and incidents in `data/incidents` are fictional.
