"""
Lead scoring.

NOT the same thing as the Board Readiness Score (Section 13):
- Board Readiness Score = how governance-mature is this company?
- Lead Score = how valuable/relevant is this lead for Connectd's
  startup-acquisition funnel?

A company can be very governance-mature (high board readiness score)
but still be a great lead (e.g. actively looking to add specific
expertise), or governance-immature but a poor lead (e.g. too early,
no stated interest). They're independent.

This is a simple, transparent, rules-based score — deliberately NOT
a trained ML model (Section 13: "Do not build a complicated ML model
for this demo. Use transparent rules.").
"""
from app.models.schemas import BoardAnalysis, CompanyProfile, LeadScore, LeadTier

# Points awarded per signal. Documented and easy to tune — this is a
# starting rubric for the demo, not a validated production model.
STAGE_POINTS = {
    "pre-seed": 10,
    "seed": 20,
    "series a": 25,
}

HIGH_SEVERITY_GAP_POINTS = 15
MEDIUM_SEVERITY_GAP_POINTS = 8
STATED_EXPERTISE_INTEREST_POINTS = 20
LARGER_TEAM_POINTS = 10  # team_size >= 10
LOW_GOVERNANCE_MATURITY_POINTS = 15  # signals real, addressable need


def calculate_lead_score(profile: CompanyProfile, analysis: BoardAnalysis) -> LeadScore:
    score = 0
    signals: list[str] = []

    stage_key = profile.founder_input.stage.strip().lower()
    stage_points = STAGE_POINTS.get(stage_key, 5)
    score += stage_points
    signals.append(f"Stage '{profile.founder_input.stage}' (+{stage_points})")

    if profile.founder_input.team_size >= 10:
        score += LARGER_TEAM_POINTS
        signals.append(f"Team size {profile.founder_input.team_size} (+{LARGER_TEAM_POINTS})")

    high_severity_gaps = [g for g in analysis.gaps if g.severity == "high"]
    medium_severity_gaps = [g for g in analysis.gaps if g.severity == "medium"]
    if high_severity_gaps:
        pts = HIGH_SEVERITY_GAP_POINTS * len(high_severity_gaps)
        score += pts
        signals.append(f"{len(high_severity_gaps)} high-severity gap(s) (+{pts})")
    if medium_severity_gaps:
        pts = MEDIUM_SEVERITY_GAP_POINTS * len(medium_severity_gaps)
        score += pts
        signals.append(f"{len(medium_severity_gaps)} medium-severity gap(s) (+{pts})")

    if profile.founder_input.areas_seeking_expertise:
        score += STATED_EXPERTISE_INTEREST_POINTS
        signals.append(
            f"Founder explicitly stated expertise needs (+{STATED_EXPERTISE_INTEREST_POINTS})"
        )

    governance_dim = next(
        (d for d in analysis.dimension_scores if d.name.value == "Governance maturity"),
        None,
    )
    if governance_dim and governance_dim.score < 40:
        score += LOW_GOVERNANCE_MATURITY_POINTS
        signals.append(
            f"Low governance maturity score ({governance_dim.score}) indicates "
            f"addressable need (+{LOW_GOVERNANCE_MATURITY_POINTS})"
        )

    score = min(score, 100)  # cap at 100

    if score >= 70:
        tier = LeadTier.HOT
    elif score >= 40:
        tier = LeadTier.WARM
    else:
        tier = LeadTier.LOW

    return LeadScore(score=score, tier=tier, signals=signals)
