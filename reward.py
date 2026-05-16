"""Compositional reward function for the classifier eval.

Per the plan, reward is the sum of five components, clamped to [0, 1]:

  * Structural gate (0/1 multiplier) — output parses as ``ClassifierOutput``.
    If not, the whole reward is 0 and the rest is skipped.
  * Entity count + types          (0.2) — exact match of the (type, kind) multiset.
  * Field comparison              (0.4) — per-entity field compare. Dates and
    RRULE strings are exact-match; titles use an LLM-as-judge call; URLs and
    booleans are exact. ``related_temp_ids`` are checked by resolved target type,
    not by literal id.
  * Confidence calibration        (0.2) — did the model land on the correct
    side of the 0.9 threshold? (Binary, not exact value.)
  * confidence_reason presence    (0.2) — when expected confidence < 0.9, did
    the model emit a non-empty ``confidence_reason``?
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from typing import Any

from openai import OpenAI
from pydantic import ValidationError

from cases import Case
from schemas import ClassifierOutput

JUDGE_MODEL = "deepseek-v3.1-terminus"

_JUDGE_SYSTEM = (
    "You are a strict equivalence judge. You receive two short task or "
    "reading titles. Reply with exactly one token: YES if they are "
    "semantically equivalent (same action and same object, ignoring "
    "case, punctuation, and minor rephrasing); NO otherwise."
)


@dataclass(frozen=True)
class RewardBreakdown:
    structural: float           # 0 or 1 — multiplier
    entity_counts: float        # 0.0 or 0.2
    field_compare: float        # 0.0..0.4 — average across entities, scaled
    confidence_calibration: float  # 0.0 or 0.2
    reason_presence: float      # 0.0 or 0.2
    total: float                # clamped 0..1
    notes: list[str]            # human-readable per-component explanation


def judge_titles_equivalent(client: OpenAI, a: str, b: str) -> bool:
    """LLM-as-judge — two titles count as equivalent if the judge says YES."""
    if a.strip().lower() == b.strip().lower():
        return True
    resp = client.chat.completions.create(
        model=JUDGE_MODEL,
        messages=[
            {"role": "system", "content": _JUDGE_SYSTEM},
            {"role": "user", "content": f"A: {a}\nB: {b}"},
        ],
        temperature=0,
        max_tokens=4,
    )
    reply = (resp.choices[0].message.content or "").strip().upper()
    return reply.startswith("YES")


def _entity_key(entity: dict[str, Any]) -> tuple[str, str | None]:
    """The (type, kind) signature used for the entity-counts gate."""
    return (entity["type"], entity.get("kind"))


def _score_field(
    field_name: str,
    expected: Any,
    entity: dict[str, Any],
    bundle: dict[str, Any],
    client: OpenAI,
    notes: list[str],
) -> float:
    """Return 0.0–1.0 for a single field. Helpers escalate via ``notes``."""

    actual = entity.get(field_name)

    # Special sentinel — checks the linked entity type, not the literal temp_id.
    if field_name == "_related_temp_ids_to_type":
        refs = entity.get("related_temp_ids") or []
        if not refs:
            notes.append("  - related_temp_ids missing or empty")
            return 0.0
        type_by_temp_id = {e.get("temp_id"): e.get("type") for e in bundle.get("entities", [])}
        for ref in refs:
            if type_by_temp_id.get(ref) == expected:
                return 1.0
        notes.append(f"  - related_temp_ids do not resolve to a {expected!r} entity")
        return 0.0

    # Field-must-be-absent assertion (expected is None).
    if expected is None:
        if actual is None:
            return 1.0
        notes.append(f"  - {field_name}: expected ABSENT, got {actual!r}")
        return 0.0

    if actual is None:
        notes.append(f"  - {field_name}: expected {expected!r}, got MISSING")
        return 0.0

    # Title fields use the LLM judge.
    if field_name == "title":
        if judge_titles_equivalent(client, str(expected), str(actual)):
            return 1.0
        notes.append(f"  - title: judge said NO  ({expected!r} vs {actual!r})")
        return 0.0

    # Everything else is exact-match (URLs, dates, RRULEs, booleans).
    if expected == actual:
        return 1.0
    # Be lenient on URL trailing slashes — common normalization artifact.
    if field_name == "url" and str(expected).rstrip("/") == str(actual).rstrip("/"):
        return 1.0
    notes.append(f"  - {field_name}: expected {expected!r}, got {actual!r}")
    return 0.0


def compute_reward(
    raw_output: str,
    case: Case,
    judge_client: OpenAI,
) -> RewardBreakdown:
    """Score one model response against the expected case."""

    notes: list[str] = []

    # 1. Structural gate.
    try:
        parsed = ClassifierOutput.model_validate_json(raw_output)
    except (ValidationError, ValueError) as e:
        notes.append(f"structural gate FAILED — {type(e).__name__}: {e}")
        return RewardBreakdown(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, notes)
    bundle = json.loads(parsed.model_dump_json(exclude_none=True))
    notes.append("structural gate OK")

    # 2. Entity counts + types.
    actual_counter = Counter(_entity_key(e) for e in bundle["entities"])
    expected_counter = Counter(case.expected_entities)
    if actual_counter == expected_counter:
        entity_counts_score = 0.2
        notes.append(f"entity counts OK ({dict(actual_counter)})")
    else:
        entity_counts_score = 0.0
        notes.append(
            "entity counts MISMATCH "
            f"expected {dict(expected_counter)} got {dict(actual_counter)}"
        )

    # 3. Field comparison. Align expected and actual by (type, kind) ordering;
    #    if counts mismatch we still score the entities we can match in order.
    field_score = 0.0
    if case.expected_fields:
        expected_sigs = case.expected_entities
        # Build a list of actual entities matching the expected signature order.
        remaining = list(bundle["entities"])
        per_entity_scores: list[float] = []
        for sig, expected_block in zip(expected_sigs, case.expected_fields):
            match = next(
                (e for e in remaining if _entity_key(e) == sig),
                None,
            )
            if match is None:
                notes.append(f"field compare: no actual entity for sig {sig}")
                per_entity_scores.append(0.0)
                continue
            remaining.remove(match)

            inner_scores = [
                _score_field(fname, expected, match, bundle, judge_client, notes)
                for fname, expected in expected_block.items()
            ]
            per_entity_scores.append(
                sum(inner_scores) / len(inner_scores) if inner_scores else 1.0
            )
        if per_entity_scores:
            field_score = 0.4 * (sum(per_entity_scores) / len(per_entity_scores))
        notes.append(f"field score: {field_score:.3f}")

    # 4. Confidence calibration.
    actual_conf = bundle["confidence"]
    actual_high = actual_conf >= 0.9
    if actual_high == case.expected_high_confidence:
        conf_score = 0.2
        notes.append(
            f"confidence calibration OK (actual={actual_conf}, "
            f"expected_high={case.expected_high_confidence})"
        )
    else:
        conf_score = 0.0
        notes.append(
            f"confidence calibration MISS (actual={actual_conf}, "
            f"expected_high={case.expected_high_confidence})"
        )

    # 5. confidence_reason presence (only graded when expected low).
    reason_score = 0.0
    if case.expects_confidence_reason:
        reason = bundle.get("confidence_reason") or ""
        if reason.strip():
            reason_score = 0.2
            notes.append(f"confidence_reason present: {reason!r}")
        else:
            notes.append("confidence_reason MISSING (expected one)")
    else:
        # When NOT expected, full marks on this component — it's a no-op gate
        # that exists to keep totals comparable across cases.
        reason_score = 0.2
        if (bundle.get("confidence_reason") or "").strip():
            notes.append(
                "note: confidence_reason emitted but not required "
                "(expected high confidence)"
            )

    total = min(1.0, entity_counts_score + field_score + conf_score + reason_score)
    return RewardBreakdown(
        structural=1.0,
        entity_counts=entity_counts_score,
        field_compare=field_score,
        confidence_calibration=conf_score,
        reason_presence=reason_score,
        total=total,
        notes=notes,
    )
