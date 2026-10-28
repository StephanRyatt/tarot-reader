# Privacy policy

**Effective:** 27 October 2026

This policy covers the public Tarot Reader server at `https://tarot-reader-omega.vercel.app/mcp` and the Tarot Reader
plugin for Claude and ChatGPT.

## What the server receives

When your AI assistant draws cards, it sends the server:

* **Spread position names**, such as "Past", "Present" and "Future". For a custom spread these are short names
  written for your situation, such as "What staying costs", and a decision spread names the options.
* **The spread's name**, such as "Daily Alignment".
* **Standard request data** that every web request carries: the time, HTTP headers, and the IP address of whatever
  makes the request. That is your assistant provider's servers for claude.ai, Claude Desktop and ChatGPT, and your
  own computer for Claude Code and Codex.

The plugin's instructions tell the assistant to keep your question, names, places and other private details out of
what it sends. The server can't enforce that; it depends on the assistant following its instructions. The server
never receives your conversation.

## What the server keeps

Nothing. The server has no database, no accounts and no cookies. Each request is handled and forgotten.

The server runs on [Vercel](https://vercel.com). Vercel keeps request logs (time, path, status code and IP address)
and uses the IP address for rate limiting, under [Vercel's privacy policy](https://vercel.com/legal/privacy-policy).

## Your assistant

Your conversation, including your question and the reading, is handled by your AI assistant (Claude, ChatGPT or
another client) under that provider's privacy policy, not this one.

## Changes

Changes to this policy are made in this file, and its history is public in the repository.
