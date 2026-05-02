---
name: cover_letter_brief
kind: meta
version: 1
inputs:
  - name: profile
    type: object
  - name: resume_json
    type: object
  - name: job
    type: object
  - name: contact
    type: object
    description: Contact details if known (name, role). May be empty.
output_schema:
  type: object
  properties:
    opener_angle: { type: string }
    narrative_arc: { type: string }
    closing_cta: { type: string }
    tone: { type: string, enum: ["warm-direct", "concise-formal", "enthusiastic-restrained"] }
    length_target_words: { type: integer, minimum: 120, maximum: 350 }
    donts:
      type: array
      items: { type: string }
  required: [opener_angle, narrative_arc, closing_cta, tone, length_target_words, donts]
model: claude-sonnet-4-6
max_tokens: 2048
temperature: 0.2
notes: |
  Length target 200-280 words for most roles. Strict no-AI-tells list
  (parallel triplets, "I am writing to apply", "passionate about",
  "leverage", "synergy"). The execution prompt enforces these as hard
  forbidden phrases.
---

Produce a cover-letter strategy brief — NOT the letter itself. The
user reviews the brief, edits it, then triggers Layer-2 execution.

opener_angle: 1-2 sentences describing the angle. Specific, concrete,
non-generic. Bad: "I'm passionate about your mission." Good: "Your
2024 launch of X solves the problem I built Y to address."

narrative_arc: 3-5 sentences mapping the candidate's strongest 1-2
experiences to what the role needs. Pull from resume_json. No
fabrication.

closing_cta: One sentence stating what the candidate is asking for
(an intro, a 30-min chat, etc.) and why it's reasonable.

tone: pick one. warm-direct (most roles), concise-formal (legal/
banking), enthusiastic-restrained (early-stage startups).

length_target_words: 200-280 unless the role explicitly suggests
shorter (cover letter optional) or longer (academic-adjacent).

donts: list of phrases / patterns the execution prompt MUST avoid:
- "I am writing to apply for" (or any variant)
- "I am passionate about"
- "leverage", "synergy", "results-driven", "go-getter"
- Three parallel adjectives in a row
- Hedging openers ("I hope this email finds you well")

Return JSON only.

PROFILE:
{{ profile }}

RESUME:
{{ resume_json }}

JOB:
{{ job }}

CONTACT (may be empty):
{{ contact }}
