---
name: echo
kind: static
version: 1
inputs:
  - name: message
    type: string
    description: The message to echo back verbatim
output_schema: string
model: claude-sonnet-4-6
max_tokens: 256
temperature: 0.0
notes: |
  Smoke-test prompt used by the loader's self-validation. Keep it
  simple — any change here ripples into test_prompt_loader.py
  expectations. Not used in production flows.
---

Repeat the following message back to me, character-for-character, with
no commentary, formatting, quoting, or explanation.

Message:
{{ message }}
