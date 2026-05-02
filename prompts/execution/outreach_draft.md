---
name: outreach_draft
kind: execution
version: 1
inputs:
  - name: brief
    type: object
  - name: profile
    type: object
  - name: contact
    type: object
  - name: job
    type: object
  - name: intent
    type: string
output_schema:
  type: object
  properties:
    draft_text: { type: string }
    word_count: { type: integer }
    reasoning_text: { type: string }
  required: [draft_text, word_count, reasoning_text]
model: claude-opus-4-7
max_tokens: 1024
temperature: 0.5
notes: |
  Output is the actual message body — no greeting line ("Hi Name,"
  is added automatically by the UI), no signature. word_count
  reported so the UI can flag overlong drafts.
---

Write the outreach message following the brief. Hard constraints:

- DO NOT use any phrase in brief.donts.
- DO NOT include "Hi Name," or any greeting — the UI adds the
  greeting separately.
- DO NOT include a signature — the user adds it themselves.
- Length: brief.length_target_words ± 20%.
- Single paragraph for cold_intro / referral. Up to 2 short
  paragraphs for application_support.
- Sound like a person, not a template. Avoid AI-tells: no "I hope
  this finds you well", no over-formal hedging, no triplets.
- Mirror the tone in brief.tone.

reasoning_text: 2-4 sentences explaining the choices you made (why
this hook, why this ask), so the user can sanity-check.

Return JSON only:
{
  "draft_text": "<the message body — no greeting, no signature>",
  "word_count": <int>,
  "reasoning_text": "<your reasoning>"
}

BRIEF: {{ brief }}
PROFILE: {{ profile }}
CONTACT: {{ contact }}
JOB: {{ job }}
INTENT: {{ intent }}
