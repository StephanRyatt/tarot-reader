import json
import random
from typing import List, Dict, Tuple, Any
from http.server import BaseHTTPRequestHandler

# ---- Tarot constants ----

MAJOR_ARCANA = [
    "The Fool", "The Magician", "The High Priestess", "The Empress", "The Emperor",
    "The Hierophant", "The Lovers", "The Chariot", "Strength", "The Hermit",
    "Wheel of Fortune", "Justice", "The Hanged Man", "Death", "Temperance",
    "The Devil", "The Tower", "The Star", "The Moon", "The Sun", "Judgement", "The World"
]
SUITS = ["Wands", "Cups", "Swords", "Pentacles"]
MINOR_RANKS = ["Ace"] + [str(n) for n in range(2, 11)] + ["Page", "Knight", "Queen", "King"]

MAX_POSITIONS = 30  # guardrail for spread size

# Packet-flip realism knobs
PACKET_FLIPS_MIN = 1
PACKET_FLIPS_MAX = 3
PACKET_SIZE_MIN = 8
PACKET_SIZE_MAX = 20

Orientation = str  # "upright" | "reversed"
Card = Tuple[str, Orientation]


def build_deck() -> List[Card]:
    """Build a full 78-card Rider–Waite deck, all upright."""
    minor = [f"{rank} of {suit}" for suit in SUITS for rank in MINOR_RANKS]
    names = MAJOR_ARCANA + minor
    return [(name, "upright") for name in names]


def _flip_packet(deck: List[Card], start: int, size: int) -> None:
    """Flip orientation for cards in [start, start+size)."""
    end = min(start + size, len(deck))
    for i in range(start, end):
        name, orient = deck[i]
        deck[i] = (name, "reversed" if orient == "upright" else "upright")


def apply_packet_flips(deck: List[Card], rng: random.Random) -> None:
    """
    Simulate real-world packet flipping:
    - choose 1–3 packets
    - each packet is 8–20 cards
    - flip (rotate) the packet: toggles orientation for those cards
    """
    flips = rng.randint(PACKET_FLIPS_MIN, PACKET_FLIPS_MAX)
    n = len(deck)
    for _ in range(flips):
        size = rng.randint(PACKET_SIZE_MIN, PACKET_SIZE_MAX)
        start = rng.randrange(0, n)
        _flip_packet(deck, start, size)


def shuffle_deck(deck: List[Card], rng: random.Random) -> None:
    rng.shuffle(deck)


def cut_deck(deck: List[Card], rng: random.Random) -> None:
    """Rotate deck by a random cut index."""
    if not deck:
        return
    cut = rng.randrange(0, len(deck))
    deck[:] = deck[cut:] + deck[:cut]


def draw(deck: List[Card], positions: List[str]) -> Dict[str, Dict[str, str]]:
    """Draw top cards for each named position."""
    draws: Dict[str, Dict[str, str]] = {}
    for pos in positions:
        name, orient = deck.pop(0)
        draws[pos] = {"card": name, "orientation": orient}
    return draws


def _bad_request(msg: str) -> Dict[str, Any]:
    return {"error": msg}


class handler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length > 0 else b"{}"

            try:
                body = json.loads(raw.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                return self._send_json(400, _bad_request("invalid JSON body"))

            if not isinstance(body, dict):
                return self._send_json(400, _bad_request("body must be a JSON object"))

            positions = body.get("positions")
            if not isinstance(positions, list) or len(positions) < 1:
                return self._send_json(400, _bad_request("positions must be a non-empty array of strings"))

            cleaned: List[str] = []
            for p in positions:
                if not isinstance(p, str):
                    return self._send_json(400, _bad_request("positions must be an array of strings"))
                s = p.strip()
                if not s:
                    return self._send_json(400, _bad_request("positions must contain non-empty strings"))
                cleaned.append(s)

            if len(set(cleaned)) != len(cleaned):
                return self._send_json(400, _bad_request("positions must be unique"))
            if len(cleaned) > MAX_POSITIONS:
                return self._send_json(400, _bad_request(f"positions length must be <= {MAX_POSITIONS}"))
            if len(cleaned) > 78:
                return self._send_json(400, _bad_request("positions length must be <= 78"))

            label = body.get("label")
            if label is not None:
                if not isinstance(label, str):
                    return self._send_json(400, _bad_request("label must be a string"))
                label = label.strip()
                if len(label) > 200:
                    return self._send_json(400, _bad_request("label too long (max 200 chars)"))
                if label == "":
                    label = None

            rng = random.SystemRandom()
            deck = build_deck()
            apply_packet_flips(deck, rng)
            shuffle_deck(deck, rng)
            cut_deck(deck, rng)
            draws = draw(deck, cleaned)

            meta: Dict[str, str] = {}
            if label:
                meta["label"] = label

            return self._send_json(200, {"draws": draws, "meta": meta})

        except Exception as e:
            return self._send_json(400, {"error": str(e)})

    def do_GET(self):
        self.send_response(405)
        self.send_header("Allow", "POST")
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"error": "Method not allowed"}).encode("utf-8"))
