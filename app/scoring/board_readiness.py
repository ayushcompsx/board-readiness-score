"""
Deterministic Board Readiness scoring.

Per Section 10 of the brief: we do NOT ask the LLM "give this company a
score out of 100" — that produces arbitrary, unreproducible numbers.

Instead:
  1. The LLM assesses each of the 8 dimensions using a qualitative
     maturity label (strong / adequate / emerging / absent) + evidence.
  2. THIS module converts that label into a numeric score via a fixed,
     documented rubric.
  3. The overall score is a deterministic average of the 8 dimension
     scores.

This makes the score reproducible, testable, and explainable — the
same qualitative assessment always produces the same number, and you
can point to exactly why.
"""
from app.models.schemas import DimensionName, DimensionScore

# Maturity label -> numeric score. Documented and easy to tune.
MATURITY_SCORE_RUBRIC: dict[str, int] = {
    "strong": 85,
    "adequate": 60,
    "emerging": 35,
    "absent": 10,
}

VALID_MATURITY_LABELS = set(MATURITY_SCORE_RUBRIC.keys())


def score_from_maturity_label(label: str) -> int:
    """
    Converts a qualitative maturity label into a numeric score.
    Raises ValueError on an unrecognised label — we never silently
    guess a score for something the LLM didn't actually assess
    using our known vocabulary (Section 5: never silently accept
    malformed LLM output).
    """
    label_normalised = label.strip().lower()
    if label_normalised not in MATURITY_SCORE_RUBRIC:
        raise ValueError(
            f"Unrecognised maturity label '{label}'. "
            f"Expected one of {sorted(VALID_MATURITY_LABELS)}."
        )
    return MATURITY_SCORE_RUBRIC[label_normalised]


def calculate_overall_score(dimension_scores: list[DimensionScore]) -> int:
    """
    Simple equal-weighted average across all 8 dimensions, rounded to
    the nearest integer. Equal weighting is a deliberate, documented
    simplification for the demo — a production version might weight
    dimensions differently by startup stage (e.g. financial oversight
    matters more pre-Series-A than post).
    """
    if not dimension_scores:
        raise ValueError("Cannot calculate overall score with zero dimensions.")

    expected_dimensions = set(DimensionName)
    provided_dimensions = {d.name for d in dimension_scores}
    if provided_dimensions != expected_dimensions:
        missing = expected_dimensions - provided_dimensions
        raise ValueError(
            f"Missing scores for dimensions: {sorted(d.value for d in missing)}"
        )

    total = sum(d.score for d in dimension_scores)
    return round(total / len(dimension_scores))
