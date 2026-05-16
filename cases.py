"""The five PRD cases the eval scores against.

Chosen to span the interesting cells with minimum count:

    Case | Input                                | Tests
    -----+--------------------------------------+----------------------------------
    E1   | buy milk                             | errand kind + date default + title-lift
    E3   | every Monday standup                 | template + RRULE generation
    E5   | what can I do with this ... GitHub … | URL + verb → reading+task pair
    E14  | remind me about taxes                | vagueness → low-confidence + reason
    E18  | twice a week jog                     | cadence outside RRULE table → low-confidence
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Held constant across the eval so date-default logic (E1) is reproducible.
# Pick the day Kate wrote the plan; a Friday so the day-name math is unambiguous.
TODAY = "2026-05-16"


@dataclass(frozen=True)
class Case:
    """A single eval row.

    The expected fields drive the reward function, not strict equality. Per
    the plan, dates and RRULEs are exact-match, titles use an LLM judge,
    URLs are exact, and confidence is binary against the 0.9 threshold.
    """

    case_id: str
    raw_input: str
    today: str
    # List of (type, kind-or-None) — e.g. [("workitem", "errand")] or
    # [("reading", None), ("workitem", "task")]. Ordering matches the
    # expected output; the reward compares as a sorted multiset so the
    # classifier isn't penalised for ordering differences.
    expected_entities: list[tuple[str, str | None]]
    # Per-entity expected fields, keyed by an entity index that matches
    # ``expected_entities``. Only fields present here are scored; everything
    # else is ignored. Use ``None`` for fields that must NOT appear (e.g.
    # E14's "scheduled_date").
    expected_fields: list[dict[str, Any]]
    # ``True``  → expect confidence ≥ 0.9 ("the model should be sure").
    # ``False`` → expect confidence  < 0.9 ("the model should be uncertain").
    expected_high_confidence: bool
    # When ``expected_high_confidence`` is False, the model must ALSO emit
    # a non-empty ``confidence_reason``. Tracked separately for the reward
    # function's "reason presence" component.
    expects_confidence_reason: bool
    notes: str = field(default="")


CASES: list[Case] = [
    Case(
        case_id="E1",
        raw_input="buy milk",
        today=TODAY,
        expected_entities=[("workitem", "errand")],
        expected_fields=[
            {
                "title": "Go to grocery",
                "scheduled_date": TODAY,
            }
        ],
        expected_high_confidence=True,
        expects_confidence_reason=False,
        notes="Tests errand kind, today-default for errand date, title-lift to grocery.",
    ),
    Case(
        case_id="E3",
        raw_input="every Monday standup",
        today=TODAY,
        expected_entities=[("template", None)],
        expected_fields=[
            {
                "title": "Standup",
                "cadence": "FREQ=WEEKLY;BYDAY=MO",
            }
        ],
        expected_high_confidence=True,
        expects_confidence_reason=False,
        notes="Tests template kind and RRULE generation for a common cadence.",
    ),
    Case(
        case_id="E5",
        raw_input="what can I do with this ai-hedge-fund GitHub repo https://github.com/virattt/ai-hedge-fund",
        today=TODAY,
        expected_entities=[("reading", None), ("workitem", "task")],
        expected_fields=[
            {
                "url": "https://github.com/virattt/ai-hedge-fund",
                "title": "ai-hedge-fund",
                "is_operational": False,
            },
            {
                "title": "Decide what to do with ai-hedge-fund",
                # The task should link back to the reading via related_temp_ids;
                # the reward checks for at least one related_temp_id resolving to
                # a reading in the same bundle, not the literal id string.
                "_related_temp_ids_to_type": "reading",
            },
        ],
        expected_high_confidence=True,
        expects_confidence_reason=False,
        notes="Tests URL → Reading + Task pair, related_temp_ids cross-reference.",
    ),
    Case(
        case_id="E14",
        raw_input="remind me about taxes",
        today=TODAY,
        expected_entities=[("workitem", "task")],
        expected_fields=[
            {
                "title": "Taxes",
            }
        ],
        expected_high_confidence=False,
        expects_confidence_reason=True,
        notes="Tests vagueness honesty — confidence must drop below 0.9 with a reason.",
    ),
    Case(
        case_id="E18",
        raw_input="twice a week jog",
        today=TODAY,
        expected_entities=[("template", None)],
        expected_fields=[
            {
                "title": "Jog",
            }
        ],
        expected_high_confidence=False,
        expects_confidence_reason=True,
        notes="Tests cadence outside the RRULE table — model must signal uncertainty.",
    ),
]


def case_by_id(case_id: str) -> Case:
    for c in CASES:
        if c.case_id == case_id:
            return c
    raise KeyError(case_id)
