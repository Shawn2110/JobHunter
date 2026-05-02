---
name: cover_letter
kind: execution
version: 1
inputs:
  - name: brief
    type: object
  - name: resume_json
    type: object
  - name: job
    type: object
  - name: contact
    type: object
output_schema:
  type: object
  properties:
    body_md: { type: string }
    word_count: { type: integer }
    reasoning_md: { type: string }
  required: [body_md, word_count, reasoning_md]
model: claude-opus-4-7
max_tokens: 2048
temperature: 0.4
notes: |
  Layer-2 execution. Hard-enforced forbidden-phrase list. Word count
  reported so the UI can flag overlong drafts.
---

Write the cover letter following the brief. Hard constraints:

- DO NOT use any phrase in brief.donts.
- Length: brief.length_target_words ± 15%.
- No fabrication — only claim what's in resume_json.
- Single voice, paragraphs (not bullets), no headers, no signature
  block (the user adds that themselves).
- Reasoning_md: 3-5 sentences explaining the choices you made (which
  experience you led with, why this opener_angle, etc.) so the user
  can sanity-check.

Return JSON only:
{
  "body_md": "<the letter as markdown — paragraphs separated by blank lines>",
  "word_count": <int>,
  "reasoning_md": "<your reasoning>"
}

BRIEF:
{{ brief }}

RESUME:
{{ resume_json }}

JOB:
{{ job }}

CONTACT:
{{ contact }}
