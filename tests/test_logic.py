# File: tests/test_logic.py

import random
import pytest

from api.tarot import draw_spread, MAX_POSITIONS


# -------------------------
# A) Validation tests
# -------------------------

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
        

def test_label_not_string_raises():
    with pytest.raises(ValueError, match=r"label must be a string"):
        draw_spread(positions=["Past"], label=123)


def test_label_too_long_raises():
    with pytest.raises(ValueError, match=r"label too long"):
        draw_spread(positions=["Past"], label="x" * 201)


# -------------------------
# B) Deterministic behavior
# -------------------------

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
        assert isinstance(v["card"], str) and v["card"]
        assert v["orientation"] in {"upright", "reversed"}


def test_orientation_values_are_valid():
    rng = random.Random(999)
    out = draw_spread(positions=["A", "B", "C", "D", "E"], rng=rng)
    for v in out["draws"].values():
        assert v["orientation"] in {"upright", "reversed"}


# -------------------------
# C) Invariants
# -------------------------

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
