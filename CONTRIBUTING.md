# Contributing a recipe

Good recipes solve a task someone is actually paid to do. Here is the standard.

## Shape

```
<category>/<recipe-name>/
  README.md     what it does, who it's for, how it works, how to run it
  recipe.py     the whole solution, readable top to bottom
  data/         fictional sample data only
tests/test_<recipe_name>.py
```

Add the recipe to `registry.yaml` and to the table in the main `README.md`.

## Rules

1. **One file.** Keep the solution in `recipe.py`. Readers should not chase imports.
2. **Standard library plus the OpenAI SDK.** Add another dependency only when the recipe is about that tool.
3. **Configurable endpoint.** Read `CONTINUUM_API_KEY`, `CONTINUUM_BASE_URL` and `CONTINUUM_MODEL` from the environment. Never hard-code a key.
4. **Fictional data.** No real companies, people, contracts or client material. Say so in the README.
5. **Verify in code.** Check the model's output with ordinary code wherever you can: required fields, allowed values, quotes that must exist in the source.
6. **Test offline.** Add a test that drives the recipe with the scripted stand-in model in `tests/fake_model.py`.
7. **Plain README.** Lead with what the recipe does in one sentence. Then who it's for, how it works, how to run it, and what to change for your own use.
8. **Credit your sources.** If you adapt someone else's example, link to it and keep its licence notice.
