"""Tarot draw engine and the REST endpoint, POST /api/tarot.

`draw_spread()` owns all validation and drawing; the MCP handler in api/mcp.py calls it
too. `handler` is the class Vercel's Python runtime serves for this file, so the class
name and the file path both matter for deployment.
"""

import hmac
import json
import os
import random
import sys
from http.server import BaseHTTPRequestHandler
from typing import Any, Literal

MAJOR_ARCANA = [
    "The Fool", "The Magician", "The High Priestess", "The Empress", "The Emperor",
    "The Hierophant", "The Lovers", "The Chariot", "Strength", "The Hermit",
    "Wheel of Fortune", "Justice", "The Hanged Man", "Death", "Temperance",
    "The Devil", "The Tower", "The Star", "The Moon", "The Sun", "Judgement", "The World",
]  # fmt: skip
SUITS = ["Wands", "Cups", "Swords", "Pentacles"]
MINOR_RANKS = ["Ace"] + [str(n) for n in range(2, 11)] + ["Page", "Knight", "Queen", "King"]

MAX_POSITIONS = 30
MAX_POSITION_LENGTH = 100
MAX_LABEL_LENGTH = 200

# Reversals come from flipping a few packets of cards before the shuffle, the way a
# reader does by hand. That makes about 26% of cards reversed, not 50%
# (tests/test_logic.py pins the range). The shuffle uses SystemRandom, so the cut that
# follows adds no randomness; it is kept to mirror a physical reading.
PACKET_FLIPS_MIN = 1
PACKET_FLIPS_MAX = 3
PACKET_SIZE_MIN = 8
PACKET_SIZE_MAX = 20

AUTH_ENV_VAR = "TAROT_API_KEY"
AUTH_HEADER = "Authorization"
AUTH_SCHEME = "Bearer"

Orientation = Literal["upright", "reversed"]
Card = tuple[str, Orientation]
Draws = dict[str, dict[str, str]]


def build_deck() -> list[Card]:
    """Build a full 78-card Rider-Waite deck, all upright."""
    minor = [f"{rank} of {suit}" for suit in SUITS for rank in MINOR_RANKS]
    return [(name, "upright") for name in MAJOR_ARCANA + minor]


def _flip_packet(deck: list[Card], start: int, size: int) -> None:
    """Toggle orientation for the cards in [start, start + size)."""
    for i in range(start, min(start + size, len(deck))):
        name, orientation = deck[i]
        deck[i] = (name, "reversed" if orientation == "upright" else "upright")


def apply_packet_flips(deck: list[Card], rng: random.Random) -> None:
    """Flip 1-3 packets of 8-20 cards each, starting at random points."""
    for _ in range(rng.randint(PACKET_FLIPS_MIN, PACKET_FLIPS_MAX)):
        size = rng.randint(PACKET_SIZE_MIN, PACKET_SIZE_MAX)
        _flip_packet(deck, rng.randrange(len(deck)), size)


def shuffle_deck(deck: list[Card], rng: random.Random) -> None:
    rng.shuffle(deck)


def cut_deck(deck: list[Card], rng: random.Random) -> None:
    """Rotate the deck at a random cut point."""
    if not deck:
        return
    cut = rng.randrange(len(deck))
    deck[:] = deck[cut:] + deck[:cut]


def draw(deck: list[Card], positions: list[str]) -> Draws:
    """Deal the top card to each named position, in order."""
    draws: Draws = {}
    for position in positions:
        name, orientation = deck.pop(0)
        draws[position] = {"card": name, "orientation": orientation}
    return draws


def _extract_bearer_token(authorization_value: str) -> str | None:
    """Return <token> from "Bearer <token>", or None."""
    scheme, _, token = authorization_value.partition(" ")
    token = token.strip()
    if scheme.strip() != AUTH_SCHEME or not token:
        return None
    return token


def is_authorized(authorization_value: str | None) -> bool:
    """True when TAROT_API_KEY is unset, or the header carries the matching Bearer token."""
    expected = os.environ.get(AUTH_ENV_VAR)
    if not expected:
        return True
    token = _extract_bearer_token(authorization_value or "")
    return token is not None and hmac.compare_digest(token, expected)


def _validate_positions(positions: Any) -> list[str]:
    if not isinstance(positions, list) or not positions:
        raise ValueError("positions must be a non-empty array of strings")
    if len(positions) > MAX_POSITIONS:
        raise ValueError(f"positions length must be <= {MAX_POSITIONS}")

    cleaned: list[str] = []
    for position in positions:
        if not isinstance(position, str):
            raise ValueError("positions must be an array of strings")
        name = position.strip()
        if not name:
            raise ValueError("positions must contain non-empty strings")
        if len(name) > MAX_POSITION_LENGTH:
            raise ValueError(f"position names must be <= {MAX_POSITION_LENGTH} chars")
        cleaned.append(name)

    if len(set(cleaned)) != len(cleaned):
        raise ValueError("positions must be unique")
    return cleaned


def _validate_label(label: Any) -> str | None:
    if label is None:
        return None
    if not isinstance(label, str):
        raise ValueError("label must be a string")
    label = label.strip()
    if len(label) > MAX_LABEL_LENGTH:
        raise ValueError(f"label too long (max {MAX_LABEL_LENGTH} chars)")
    return label or None


def draw_spread(
    *,
    positions: Any,
    label: Any = None,
    rng: random.Random | None = None,
) -> dict[str, Any]:
    """Validate a spread request and draw one card per position.

    Returns {"draws": {position: {"card", "orientation"}}, "meta": {"label"?}}.
    Raises ValueError with a client-safe message on bad input. Pass a seeded
    random.Random for deterministic tests; the default is random.SystemRandom().
    """
    cleaned = _validate_positions(positions)
    clean_label = _validate_label(label)
    rng = rng if rng is not None else random.SystemRandom()

    deck = build_deck()
    apply_packet_flips(deck, rng)
    shuffle_deck(deck, rng)
    cut_deck(deck, rng)

    meta = {"label": clean_label} if clean_label else {}
    return {"draws": draw(deck, cleaned), "meta": meta}


class handler(BaseHTTPRequestHandler):  # noqa: N801 - Vercel requires this name
    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _error(self, status: int, message: str) -> None:
        self._send_json(status, {"error": message})

    def do_POST(self) -> None:
        try:
            self._handle_post()
        except Exception as e:
            # The contract maps unexpected errors to 400. Log the detail, never send it.
            print(f"{type(e).__name__}: {e}", file=sys.stderr)
            self._error(400, "bad request")

    def _handle_post(self) -> None:
        if not is_authorized(self.headers.get(AUTH_HEADER)):
            self._error(401, "Unauthorized")
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._error(400, "invalid Content-Length header")
            return
        raw = self.rfile.read(length) if length > 0 else b""

        try:
            body = json.loads(raw.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._error(400, "invalid JSON body")
            return
        if not isinstance(body, dict):
            self._error(400, "body must be a JSON object")
            return

        try:
            payload = draw_spread(positions=body.get("positions"), label=body.get("label"))
        except ValueError as e:
            self._error(400, str(e))
            return
        self._send_json(200, payload)

    def do_GET(self) -> None:
        body = json.dumps({"error": "Method not allowed"}).encode("utf-8")
        self.send_response(405)
        self.send_header("Allow", "POST")
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
