# Guide for AI coding assistants

This file tells coding assistants how this repository works, so they can help a developer adapt a recipe.

## What this is

A cookbook of working AI recipes. Each recipe solves one business task with an OpenAI-compatible API. The default endpoint is Continuum Labs, which runs open models in Australia.

## Layout

```
<category>/<recipe>/recipe.py          the whole solution, standard library plus the openai package
<category>/<recipe>/README.md          what it does and how to change it
<category>/<recipe>/data/              fictional sample inputs
<category>/<recipe>/example-output/    output from a demo run
au/checks.py                           Australian checks: ABN, TFN, GST, postcodes, dates
demo/scripts.py                        scripted model replies for --demo
demo/fake_model.py                     stand-in client used by demos and tests
tests/                                 offline tests, no network or key needed
registry.yaml                          index of recipes
```

## Running

```bash
python <category>/<recipe>/recipe.py --demo     # no key needed
python <category>/<recipe>/recipe.py            # needs CONTINUUM_API_KEY
python -m unittest discover -s tests            # must pass before any change is done
```

Settings come from `CONTINUUM_API_KEY`, `CONTINUUM_BASE_URL` and `CONTINUUM_MODEL`. Never hard-code a key.

## When adapting a recipe for a user

- Keep the solution in one `recipe.py`. Do not split it into modules.
- Use `au/checks.py` for anything Australian: ABNs, GST, tax file numbers, postcodes, dates. Redact tax file numbers before text reaches a model.
- Keep the checks in plain code. They are the point of each recipe: findings validated against the playbook, quotes checked against sources, figures checked against announcements. Do not replace a code check with a model check.
- Change the input data and prompts first. Change the tools second. Change the agent loop last.
- If you add a tool, validate its arguments and return errors as text so the model can correct itself.
- Keep `--demo` working. If you change a recipe's tools, update its script in `demo/scripts.py`.
- Run the tests. Add a test for any new behaviour using `demo/fake_model.py`.

## Adding a new recipe

Follow `CONTRIBUTING.md`. A recipe is not finished until it has a README, fictional sample data, a demo script, committed example output, a test and an entry in `registry.yaml`.

## Writing style

Plain English. Short sentences. Australian spelling. Name things by what they do for the user.
