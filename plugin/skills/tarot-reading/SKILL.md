---
name: tarot-reading
description: Give tarot readings grounded in real random draws. Use when the user asks for a tarot reading, a card pull, or a named spread (single card, three-card, Celtic Cross). Always draw with the draw_tarot_spread tool first; never invent cards. Do not call draw_tarot_spread when the user names cards they already drew or asks what a named card means.
---

# Tarot reading

## Required workflow

1. Choose a spread and its position names. If the user does not name a spread, default to a three-card Past/Present/Future.
2. Call `draw_tarot_spread` for **exactly one successful draw per reading** with `positions` (and an optional `label`) **before** saying anything about cards. Do not call it when the user names cards they already drew or asks what a named card means.
3. If the result has `isError: true`, fix the arguments using the error text and retry once.
4. If the tool is unavailable or still failing, tell the user you couldn't draw cards and offer to try again. **Never simulate, guess or "imagine" a draw.**

## Spreads

Use these literal `positions` arrays unless the user specifies their own:

- Single card: `["Card of the Day"]`
- Three-card: `["Past","Present","Future"]`
- Situation / Action / Outcome: `["Situation","Action","Outcome"]`
- Celtic Cross: `["Present","Challenge","Foundation","Recent Past","Crown","Near Future","Self","Environment","Hopes and Fears","Outcome"]`

Custom spreads use the user's own position names. Maximum 30, and names must be unique.

## Interpreting

- Use only the returned cards, in returned order, with each card's orientation.
- Name each card and orientation exactly as returned.
- Give the position meaning, then the card meaning (reversed when it's reversed), then how it relates to the user's question.
- End with a short synthesis.

## Boundaries

Readings are for reflection and entertainment. Don't make medical, legal or financial predictions or give that kind of advice. Don't claim fixed fate. Handle distressing topics gently, and suggest real-world support where appropriate.

## Redraws

Draw again only if the user explicitly asks for a new reading, and never to "improve" a result.

## Output format

Use a short heading with the spread name, one block per position (`**Position — Card (orientation)**` plus 2–4 sentences), then a "Summary" paragraph.
