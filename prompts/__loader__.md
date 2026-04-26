---
name: prompt loader specification
version: 1
---

# Prompt loader format

Every prompt in JobHunt is a versioned `.md` file with YAML frontmatter.
The loader (`backend/app/ai/prompt_loader.py`, lands in P0-T4) reads
these files fresh on every call — no caching, so users can edit a prompt
and see the effect on the next run without restarting the backend.

## Layout

```
prompts/
├── meta/        # Layer-1 prompts that produce a structured brief
├── execution/   # Layer-2 prompts that consume a brief and produce output
└── static/      # One-shot prompts where strategy doesn't vary
```

## Frontmatter schema

Every prompt file MUST start with this frontmatter block:

```yaml
---
name: <slug, matches the filename without .md>
kind: meta | execution | static
version: <integer, bump on every change>
inputs:
  - name: <var_name>
    type: string | object | list
    description: <one line>
output_schema: <JSON Schema or "string" for free-form>
model: claude-sonnet-4-6 | claude-opus-4-7
max_tokens: <integer, optional, default 4096>
temperature: <float 0.0–1.0, optional, default 0.2>
notes: <optional free text — change log lives here>
---
```

The body of the file is the prompt template. It uses `{{ var_name }}`
Jinja2-style placeholders that are substituted from the `inputs`.

## Versioning

When you change a prompt, bump `version` and add a one-line note at the
top of the body describing the change. The loader does not enforce a
strict version protocol — it's there to make diffs and rollbacks
legible.

## Validation

On load, the framework:

1. Parses the frontmatter and validates required fields are present.
2. Confirms `kind` matches the directory it sits in.
3. Validates the input set against `inputs`.
4. After the model returns, validates the response against
   `output_schema` (JSON Schema for structured outputs). On schema
   failure, retries once.

## Conventions

- Filenames use `snake_case`. Match the `name` field exactly.
- Keep prompts under ~200 lines where possible. If a prompt grows past
  that, extract sub-prompts or move static reference data into a
  separate file the prompt cites.
- Never hardcode API keys, user identities, or environment-specific
  values into a prompt. Inputs only.
- Outputs that drive UI MUST be structured (`output_schema` is a JSON
  Schema, not `"string"`).

See [docs/Architecture.md § 5.2](../docs/Architecture.md) for the
meta-prompt / execution-prompt pattern and how the loader fits in.
