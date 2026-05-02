---
name: humanize
kind: execution
version: 1
inputs:
  - name: text
    type: string
    description: A draft to be passed through an AI-tells-removal pass.
output_schema:
  type: object
  properties:
    humanized_text: { type: string }
    changes: { type: array, items: { type: string } }
  required: [humanized_text, changes]
model: claude-sonnet-4-6
max_tokens: 1024
temperature: 0.4
notes: |
  Optional second pass per Plan.md P7-T4. Targets the things humans
  consistently flag in AI-written text:
  - Triplets ("efficient, effective, and elegant").
  - Hedging openers ("It's worth noting that…").
  - Over-formal transitions ("Furthermore", "Moreover").
  - Adjective stacks ("seamless, scalable, robust solution").
  Should preserve every concrete claim — never delete numbers, names,
  or asks.
---

Rewrite the text below in a more human voice. Remove AI-tells; keep
all concrete content (numbers, names, dates, the ask).

Specifically target and rewrite:
- Three-item parallel lists ("X, Y, and Z" where the items are
  adjectives or vague nouns).
- Hedging openers ("I hope this finds you well", "Just wanted to",
  "It's worth noting that").
- Over-formal transitions ("Furthermore", "Moreover", "In addition,").
- Adjective stacks (more than two qualifiers in a row).
- "Leverage", "synergy", "passionate", "results-driven",
  "best-in-class".

Output JSON:
{
  "humanized_text": "<rewritten text>",
  "changes": ["one short string per material edit"]
}

TEXT:
---
{{ text }}
---
