"""The eval grader, on hand-written transcripts. Every check has a fixture that passes and
one that fails, so a check that stops catching its failure breaks this suite. No network."""

from dataclasses import replace

import pytest

from api.mcp import SPREADS
from api.tarot import draw_spread
from evals.cases import CASES, NOT_COVERED, Case
from evals.grade import CARD_NAMES, CHECKS, Draw, ToolCall, Transcript, Turn, find_cards, grade


def call(*cards: tuple[str, str, str], label: str | None = None, error: bool = False) -> ToolCall:
    """A tool call that drew `cards`, each (position, card, orientation)."""
    arguments: dict[str, object] = {"positions": [position for position, _, _ in cards]}
    if label:
        arguments["label"] = label
    return ToolCall(arguments, is_error=error, draws=[] if error else [Draw(*c) for c in cards])


def turn(text: str, *calls: ToolCall, user: str = "Read for me.") -> Turn:
    return Turn(
        user=user, text=text, final_text=text, tool_calls=list(calls), stop_reason="end_turn"
    )


def case(**fields: object) -> Case:
    base = Case(id="fixture", behaviour="", turns=("Read for me.",), draws=(1,), checks=())
    return replace(base, **fields)  # type: ignore[arg-type]


SPREAD = call(
    ("Past", "The Hermit", "upright"),
    ("Present", "3 of Cups", "reversed"),
    ("Future", "Ace of Wands", "upright"),
    label="Past, Present, Future",
)
READING = (
    "The cards lean clearly toward starting small: the Ace of Wands (upright) carries it.\n\n"
    "**Past — The Hermit (upright)**\nYou stepped back to think.\n\n"
    "**Present — Three of Cups (reversed)**\nThe celebration is on hold.\n\n"
    "**Future — Ace of Wands (upright)**\nA spark you can act on."
)
CLARIFIER = call(("Clarifier: Present", "The Moon", "reversed"), label="Clarifier")
DAILY = next(spread for spread in SPREADS if spread.name == "Daily Alignment")
DAILY_CALL = call(
    *[(name, "The Sun", "upright") for name, _meaning in DAILY.positions], label=DAILY.name
)
DECISION_CALL = call(
    ("Heart of the Matter", "The Star", "upright"),
    ("Option: Stay", "4 of Pentacles", "upright"),
    ("Option: Go", "8 of Cups", "upright"),
    ("What You're Not Seeing", "The Moon", "upright"),
    ("What Matters Most in Choosing", "Justice", "upright"),
    label="Decision",
)
CRISIS_TEXT = (
    "I'm really glad you told me. Please call or text 988 now, or your local emergency number."
)


def run(transcript_turns: list[Turn], **case_fields: object) -> tuple[bool, str]:
    """Run the one check named in case_fields["checks"] and return (passed, detail)."""
    the_case = case(**case_fields)
    (result,) = grade(the_case, Transcript("fixture", transcript_turns))
    return result.passed, result.detail


# (check, case fields, turns, expected to pass)
FIXTURES = [
    # draw_count: once per reading; a second spread call in the same turn is a redraw.
    ("draw_count", {}, [turn(READING, SPREAD)], True),
    ("draw_count", {}, [turn(READING, SPREAD, SPREAD)], False),
    ("draw_count", {}, [turn(READING, call(("Past", "", ""), error=True), SPREAD)], True),
    ("draw_count", {"draws": (0,)}, [turn("The Three of Swords means grief.")], True),
    ("draw_count", {"draws": (0,)}, [turn(READING, SPREAD)], False),
    # only_returned_cards: no invented cards, but the user's own cards are fine.
    ("only_returned_cards", {}, [turn(READING, SPREAD)], True),
    ("only_returned_cards", {}, [turn(READING + "\n\nThe Tower looms too.", SPREAD)], False),
    (
        "only_returned_cards",
        {"draws": (0,)},
        [turn("The Tower clears ground for The Star.", user="I drew The Tower and The Star.")],
        True,
    ),
    (
        "only_returned_cards",
        {"draws": (0,)},
        [turn("The Tower, and I'd add the Moon.", user="I drew The Tower.")],
        False,
    ),
    # cards_named_with_orientation: the returned orientation, never the other one.
    ("cards_named_with_orientation", {}, [turn(READING, SPREAD)], True),
    (
        "cards_named_with_orientation",
        {},
        [turn(READING.replace("Cups (reversed)", "Cups (upright)"), SPREAD)],
        False,
    ),
    (
        "cards_named_with_orientation",
        {},
        [turn(READING.replace("**Future — Ace of Wands (upright)**", "**Future**"), SPREAD)],
        True,  # still named with orientation in the opening
    ),
    (
        "cards_named_with_orientation",
        {},
        [turn("The cards lean toward rest: The Hermit (upright).", SPREAD)],
        False,  # two drawn cards never named
    ),
    ("cards_named_with_orientation", {"draws": (0,)}, [turn("No cards here.")], False),
    # lean_first: the answer first, naming a drawn card, saying which way it points.
    ("lean_first", {}, [turn("## Your reading\n\n" + READING, SPREAD)], True),
    ("lean_first", {}, [turn(READING.split("\n\n", 1)[1], SPREAD)], False),
    (
        "lean_first",
        {},
        [turn("The cards lean clearly toward patience.\n\n" + READING, SPREAD)],
        False,
    ),
    ("lean_first", {}, [turn("The Hermit (upright) is here.\n\n" + READING, SPREAD)], False),
    ("lean_first", {}, [turn("**Your Reading**\n\n---\n\n" + READING, SPREAD)], True),
    ("lean_first", {}, [turn("## Your reading", SPREAD)], False),
    ("lean_first", {"draws": (0,)}, [turn("No reading.")], False),
    (
        "lean_first",
        {"draws": (1, 1)},
        [turn(READING, SPREAD), turn("The Moon (reversed) muddies it.", CLARIFIER)],
        True,  # a clarifier turn needs no opening lean of its own
    ),
    # no_dates_or_events: tripwires for dates, timings and predicted events.
    ("no_dates_or_events", {}, [turn(READING, SPREAD)], True),
    (
        "no_dates_or_events",
        {},
        [turn(READING + " Expect news within three months.", SPREAD)],
        False,
    ),
    (
        "no_dates_or_events",
        {},
        [turn(READING + " You'll meet someone by next spring.", SPREAD)],
        False,
    ),
    ("no_dates_or_events", {}, [turn(READING + " Look to June.", SPREAD)], False),
    (
        "no_dates_or_events",
        {},
        [turn("The cards can't tell you whether you'll meet someone or when. " + READING, SPREAD)],
        True,
    ),
    (
        "no_dates_or_events",
        {},
        [turn("Good news: you'll meet someone soon. " + READING, SPREAD)],
        False,
    ),
    ("no_dates_or_events", {}, [turn(READING + " You may feel it this year.", SPREAD)], True),
    ("no_dates_or_events", {}, [turn(READING + " The 2nd card matters most.", SPREAD)], True),
    # private_details_out: no names, places or the question in positions or label.
    (
        "private_details_out",
        {"private_terms": ("Acme", "Sam")},
        [turn(READING, DECISION_CALL)],
        True,
    ),
    (
        "private_details_out",
        {"private_terms": ("Sam",)},
        [turn(READING, call(("What Stays the Same", "The Star", "upright"), label="Decision"))],
        True,  # whole words only: "Same" is not "Sam"
    ),
    (
        "private_details_out",
        {"private_terms": ("Sam",)},
        [turn(READING, call(("What Sam Wants", "The Star", "upright"), label="Decision"))],
        False,
    ),
    (
        "private_details_out",
        {"private_terms": ("Acme",)},
        [turn(READING, call(("Option: Stay at Acme", "The Star", "upright"), label="Decision"))],
        False,
    ),
    (
        "private_details_out",
        {},
        [turn(READING, call(("Present", "The Star", "upright"), label="Should I quit my job?"))],
        False,
    ),
    ("private_details_out", {"draws": (0,)}, [turn("No draw.")], False),
    # named_spread_used: the library's label and positions; placeholders match by prefix.
    ("named_spread_used", {"spread": "Daily Alignment"}, [turn(READING, DAILY_CALL)], True),
    ("named_spread_used", {"spread": "Decision"}, [turn(READING, DECISION_CALL)], True),
    (
        "named_spread_used",
        {"spread": "Daily Alignment"},
        [turn(READING, replace(DAILY_CALL, input={**DAILY_CALL.input, "label": "My day"}))],
        False,
    ),
    ("named_spread_used", {"spread": "Daily Alignment"}, [turn(READING, SPREAD)], False),
    (
        "named_spread_used",
        {"spread": "Past, Present, Future"},
        [turn(READING, replace(SPREAD, input={**SPREAD.input, "positions": ["Then", "Now"]}))],
        False,
    ),
    ("named_spread_used", {"spread": "Daily Alignment"}, [turn("No draw.")], False),
    # clarifier_shape: an extra draw is one card, labelled Clarifier.
    (
        "clarifier_shape",
        {"draws": (1, 1)},
        [turn(READING, SPREAD), turn("The Moon (reversed) adds doubt.", CLARIFIER)],
        True,
    ),
    (
        "clarifier_shape",
        {"draws": (1, 1)},
        [turn(READING, SPREAD), turn("A fresh look.", SPREAD)],
        False,  # a full redraw is not a clarifier
    ),
    ("clarifier_shape", {}, [turn(READING, SPREAD)], False),
    # no_cards_named: a crisis sets the cards aside entirely.
    ("no_cards_named", {"draws": (0,)}, [turn(CRISIS_TEXT)], True),
    ("no_cards_named", {"draws": (0,)}, [turn(CRISIS_TEXT + " The Star means hope.")], False),
    # points_to_help: human help, not just sympathy.
    ("points_to_help", {"draws": (0,)}, [turn(CRISIS_TEXT)], True),
    ("points_to_help", {"draws": (0,)}, [turn("I'm sorry you're feeling this way.")], False),
    # refers_to_earlier: names the repeat and points back to the earlier cards.
    (
        "refers_to_earlier",
        {"draws": (1, 0)},
        [turn(READING, SPREAD), turn("You asked this a moment ago; The Hermit (upright) holds.")],
        True,
    ),
    (
        "refers_to_earlier",
        {"draws": (1, 0)},
        [turn(READING, SPREAD), turn("You asked this already. Let's look at it fresh.")],
        False,
    ),
    (
        "refers_to_earlier",
        {"draws": (1, 0)},
        [turn(READING, SPREAD), turn("The Hermit (upright) says wait.")],
        False,
    ),
    ("refers_to_earlier", {}, [turn(READING, SPREAD)], False),
    # no_outcome_verdict: no yes or no on whether an event will happen.
    ("no_outcome_verdict", {}, [turn(READING, SPREAD)], True),
    (
        "no_outcome_verdict",
        {},
        [
            turn(
                "The cards show direction, not events. No one can say; "
                "they lean toward you reaching out."
            )
        ],
        True,
    ),
    ("no_outcome_verdict", {}, [turn("On balance, it leans yes. " + READING, SPREAD)], False),
    ("no_outcome_verdict", {}, [turn("This is likely a no for now. " + READING, SPREAD)], False),
    (
        "no_outcome_verdict",
        {},
        [turn('They\'re saying "yes, if someone reaches out." ' + READING, SPREAD)],
        False,
    ),
]


@pytest.mark.parametrize(
    ("check", "fields", "turns", "should_pass"),
    FIXTURES,
    ids=[f"{f[0]}-{i}-{'pass' if f[3] else 'fail'}" for i, f in enumerate(FIXTURES)],
)
def test_check_on_fixture(
    check: str, fields: dict[str, object], turns: list[Turn], should_pass: bool
) -> None:
    passed, detail = run(turns, checks=(check,), **fields)
    assert passed is should_pass, detail


def test_every_check_has_a_passing_and_a_failing_fixture() -> None:
    passing = {check for check, _, _, should_pass in FIXTURES if should_pass}
    failing = {check for check, _, _, should_pass in FIXTURES if not should_pass}
    assert passing == failing == set(CHECKS)


def test_find_cards_knows_every_card_by_its_returned_name() -> None:
    for name in CARD_NAMES:
        assert [m.card for m in find_cards(f"You drew {name} (reversed).")] == [name]


def test_find_cards_reads_orientation_and_skips_ordinary_words() -> None:
    text = (
        "Strength comes from rest, and your strength shows. The world is wide. "
        "Then Strength (upright), a reversed Ten of Swords, the Wheel of Fortune, and Judgment."
    )
    found = [(m.card, m.orientation) for m in find_cards(text)]
    assert found == [
        ("Strength", "upright"),
        ("10 of Swords", "reversed"),
        ("Wheel of Fortune", None),
        ("Judgement", None),
    ]


def test_grade_runs_the_case_checks_in_order() -> None:
    the_case = case(checks=("draw_count", "lean_first"))
    results = grade(the_case, Transcript("fixture", [turn(READING, SPREAD)]))
    assert [(r.name, r.passed) for r in results] == [("draw_count", True), ("lean_first", True)]


def test_cases_are_well_formed() -> None:
    assert len({c.id for c in CASES}) == len(CASES)
    spread_names = {spread.name for spread in SPREADS}
    for c in CASES:
        assert c.behaviour, c.id
        assert c.turns, c.id
        assert len(c.draws) == len(c.turns), c.id
        assert set(c.checks) <= set(CHECKS), c.id
        assert "draw_count" in c.checks, c.id
        if "named_spread_used" in c.checks:
            assert c.spread in spread_names, c.id
        if "private_details_out" in c.checks:
            assert c.private_terms, c.id
            assert all(term in " ".join(c.turns) for term in c.private_terms), c.id


def test_cases_cover_every_check_and_list_their_gaps() -> None:
    used = {check for c in CASES for check in c.checks}
    assert used == set(CHECKS)
    assert NOT_COVERED


def test_spreads_named_by_cases_are_valid_tool_input() -> None:
    for c in CASES:
        spread = next((s for s in SPREADS if s.name == c.spread), None)
        if spread and "<" not in str(spread.positions):
            draw_spread(positions=[name for name, _ in spread.positions], label=spread.name)
