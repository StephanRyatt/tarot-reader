"""Draw engine: validation, determinism, invariants and fairness."""

import math
import random
from collections import Counter

import pytest

from api.tarot import (
    MAX_LABEL_LENGTH,
    MAX_POSITION_LENGTH,
    MAX_POSITIONS,
    build_deck,
    draw_spread,
)

# Validation


def test_positions_missing_raises():
    with pytest.raises(ValueError, match=r"positions must be a non-empty array of strings"):
        draw_spread(positions=None)


def test_positions_not_a_list_raises():
    with pytest.raises(ValueError, match=r"positions must be a non-empty array of strings"):
        draw_spread(positions="Past")


def test_positions_empty_list_raises():
    with pytest.raises(ValueError, match=r"positions must be a non-empty array of strings"):
        draw_spread(positions=[])


def test_positions_non_string_entry_raises():
    with pytest.raises(ValueError, match=r"positions must be an array of strings"):
        draw_spread(positions=["Past", 123])


def test_positions_whitespace_entry_raises():
    with pytest.raises(ValueError, match=r"positions must contain non-empty strings"):
        draw_spread(positions=["Past", "   "])


def test_positions_duplicate_raises():
    with pytest.raises(ValueError, match=r"positions must be unique"):
        draw_spread(positions=["Past", "Past"])


def test_positions_exceeds_max_positions_raises():
    positions = [f"P{i}" for i in range(MAX_POSITIONS + 1)]
    with pytest.raises(ValueError, match=rf"positions length must be <= {MAX_POSITIONS}"):
        draw_spread(positions=positions)


def test_position_name_too_long_raises():
    with pytest.raises(ValueError, match=rf"position names must be <= {MAX_POSITION_LENGTH}"):
        draw_spread(positions=["x" * (MAX_POSITION_LENGTH + 1)])


def test_limits_are_accepted_exactly():
    positions = [f"{i:03d}".ljust(MAX_POSITION_LENGTH, "x") for i in range(MAX_POSITIONS)]
    out = draw_spread(positions=positions, label="y" * MAX_LABEL_LENGTH, rng=random.Random(1))
    assert len(out["draws"]) == MAX_POSITIONS


def test_label_not_string_raises():
    with pytest.raises(ValueError, match=r"label must be a string"):
        draw_spread(positions=["Past"], label=123)


def test_label_too_long_raises():
    with pytest.raises(ValueError, match=r"label too long"):
        draw_spread(positions=["Past"], label="x" * (MAX_LABEL_LENGTH + 1))


# Determinism


def test_seeded_rng_is_deterministic():
    rng1 = random.Random(123)
    rng2 = random.Random(123)
    out1 = draw_spread(positions=["Past", "Present", "Future"], rng=rng1)
    out2 = draw_spread(positions=["Past", "Present", "Future"], rng=rng2)
    assert out1 == out2


def test_output_shape_and_keys():
    rng = random.Random(123)
    out = draw_spread(positions=[" Past ", "Present", "Future"], label=" 3-card ", rng=rng)

    assert set(out.keys()) == {"draws", "meta"}
    assert set(out["draws"].keys()) == {"Past", "Present", "Future"}
    assert out["meta"] == {"label": "3-card"}

    for v in out["draws"].values():
        assert set(v.keys()) == {"card", "orientation"}
        assert isinstance(v["card"], str)
        assert v["card"]
        assert v["orientation"] in {"upright", "reversed"}


def test_orientation_values_are_valid():
    rng = random.Random(999)
    out = draw_spread(positions=["A", "B", "C", "D", "E"], rng=rng)
    for v in out["draws"].values():
        assert v["orientation"] in {"upright", "reversed"}


# Invariants


def test_no_duplicate_cards_in_spread():
    rng = random.Random(321)
    out = draw_spread(positions=["P1", "P2", "P3", "P4", "P5"], rng=rng)
    cards = [v["card"] for v in out["draws"].values()]
    assert len(cards) == len(set(cards))


def test_number_of_draws_matches_positions():
    rng = random.Random(321)
    positions = ["One", "Two", "Three", "Four"]
    out = draw_spread(positions=positions, rng=rng)
    assert len(out["draws"]) == len(positions)


def test_meta_empty_when_no_label():
    rng = random.Random(123)
    out = draw_spread(positions=["Past", "Present"], rng=rng)
    assert out["meta"] == {}


def test_label_omitted_when_empty_string():
    rng = random.Random(123)
    out = draw_spread(positions=["Past"], label="   ", rng=rng)
    assert out["meta"] == {}


def test_deck_has_78_unique_cards():
    deck = build_deck()
    assert len(deck) == 78
    assert len({name for name, _ in deck}) == 78


def test_max_positions_fits_in_one_deck():
    assert len(build_deck()) >= MAX_POSITIONS


# Fairness. Fixed seeds keep these deterministic; the thresholds are statistical.

DRAWS = 78 * 100


def _chi_square_critical(dof: int, z: float) -> float:
    """Wilson-Hilferty approximation of the chi-square quantile for a normal z-score."""
    k = 2 / (9 * dof)
    return dof * (1 - k + z * math.sqrt(k)) ** 3


@pytest.fixture(scope="module")
def first_cards():
    rng = random.Random(2026)
    return [draw_spread(positions=["Card"], rng=rng)["draws"]["Card"] for _ in range(DRAWS)]


def test_every_card_is_equally_likely(first_cards):
    counts = Counter(c["card"] for c in first_cards)
    assert len(counts) == 78
    expected = DRAWS / 78
    chi_square = sum((n - expected) ** 2 / expected for n in counts.values())
    # z = 3.72 is roughly p = 0.0001: a real bias fails, chance almost never does.
    assert chi_square < _chi_square_critical(77, 3.72)


def test_reversal_rate_matches_packet_flip_design(first_cards):
    """Packet flips reverse about 26% of cards; see the note in api/tarot.py."""
    rate = sum(c["orientation"] == "reversed" for c in first_cards) / DRAWS
    assert 0.20 < rate < 0.32
