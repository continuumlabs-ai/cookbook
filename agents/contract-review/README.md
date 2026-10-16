# Contract review agent

Checks every clause of a supplier contract against your policy playbook, rates the risk and drafts replacement wording.

**For:** legal, procurement and risk teams who review the same kinds of contracts again and again.

## What it does

You give it two things: a contract and a playbook of your organisation's rules. Liability caps, where data may be stored, payment terms, governing law and so on.

The agent works through the playbook one rule at a time. It reads the rule, finds and reads the clause that deals with it, and records a finding: compliant, exception or missing. For each exception it rates the risk and drafts a redline.

You get a report that leads with what needs attention.

```
# Contract review

7 of 8 policy topics need attention.

| Topic          | Clause | Status    | Risk   |
|----------------|--------|-----------|--------|
| liability      | 7      | exception | high   |
| data location  | 5      | exception | high   |
| ...
```

## How it works

```
playbook ──► agent ──► get_policy ──► read_clause ──► record_finding ──┐
               ▲                                                       │
               └───────────── next topic, until all are covered ◄──────┘
                                         │
                                       finish ──► coverage check in code ──► report
```

Three design choices make it dependable.

1. **The agent reads clauses on demand.** It sees a list of clause headings, not the whole contract at once. That keeps long contracts manageable and makes every finding traceable to a clause.
2. **Findings are validated in code.** A finding with an unknown topic, a made-up clause number or an invalid status is rejected, and the error goes back to the model to correct.
3. **Nothing is silently skipped.** The agent cannot finish until every topic has a finding. If it stops early anyway, the code flags the missing topics as "not reviewed" for a person to check.

## Try it now

No key needed. Demo mode replays a scripted model run through this recipe's real code.

```bash
uv run agents/contract-review/recipe.py --demo
```

Or read the [example output](example-output/report.md).

## Run it

```bash
export CONTINUUM_API_KEY=your-key
uv run agents/contract-review/recipe.py
```

Use your own documents:

```bash
uv run agents/contract-review/recipe.py --contract my-contract.md --playbook my-playbook.json
```

The contract needs clause headings in the form `## 7. Liability`. Convert a Word or PDF contract to Markdown first.

## Make it yours

- **Edit `data/playbook.json`.** Each topic needs a plain-English rule and the risk if it is breached.
- **Choose a model.** Any model with tool calling works. Use a stronger reasoning model for complex agreements.
- **Add tools.** A `search_precedents` tool that looks up how you settled the same clause before is a natural next step.

## Why keep it onshore

Contracts hold commercially sensitive terms, pricing and counterparty details. Many organisations cannot send them to an AI service overseas. Run on Continuum, every request is processed in Australian data centres and nothing is stored.

## Sample data

The contract, playbook and both companies are fictional.

This recipe drafts suggestions for a reviewer. It is not legal advice.
