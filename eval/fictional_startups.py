"""
Evaluation dataset (Section 21).

Three fictional startup profiles, deliberately spanning different
maturity levels, used to manually review report quality once Ollama
is running locally. This is NOT a pass/fail test suite — scoring
"quality" and "hallucination rate" needs human judgement, not
assertions. Run this script and read the output.

Usage (requires Ollama running locally with the configured model
pulled):
    python -m eval.fictional_startups
"""
import asyncio
import json

from app.models.schemas import FounderInput
from app.orchestration.pipeline import run_assessment

EVAL_PROFILES = [
    FounderInput(
        company_name="Nimbus Data",
        stage="Pre-seed",
        industry="B2B SaaS",
        team_size=4,
        founder_background="First-time founder, previously a backend engineer",
        current_team_structure="Two co-founders, two engineers, no dedicated ops/finance",
        existing_board_or_advisors="None",
        current_strategic_challenges="Deciding whether to raise a pre-seed round or bootstrap longer",
        areas_seeking_expertise="Fundraising strategy, early GTM",
    ),
    FounderInput(
        company_name="Verdant Health",
        stage="Series A",
        industry="Healthtech",
        team_size=35,
        founder_background="Second-time founder, clinical background",
        current_team_structure="Strong engineering and clinical leadership, no dedicated commercial lead",
        existing_board_or_advisors="One investor board seat from lead Series A investor",
        current_strategic_challenges="Weak commercial traction despite strong product-market fit signals",
        areas_seeking_expertise="Commercial/GTM leadership, international expansion",
    ),
    FounderInput(
        company_name="Harborlight Finance",
        stage="Series A",
        industry="Fintech",
        team_size=28,
        founder_background="Ex-banking, strong finance background",
        current_team_structure="Formal board with 3 members, finance function led by founder",
        existing_board_or_advisors="Formal board with two independent members, strong finance oversight",
        current_strategic_challenges="Considering international expansion, limited experience in new markets",
        areas_seeking_expertise="International market entry, regulatory expertise",
    ),
]


async def run_eval():
    for profile in EVAL_PROFILES:
        print(f"\n{'=' * 70}")
        print(f"EVAL: {profile.company_name} ({profile.stage})")
        print("=" * 70)

        run = await run_assessment(profile)

        if run.status.value != "complete":
            failed_stage = next((m for m in run.run_metadata if not m.success), None)
            print(f"FAILED at stage: {failed_stage.agent_name if failed_stage else 'unknown'}")
            print(f"Error: {failed_stage.validation_errors if failed_stage else 'unknown'}")
            continue

        print(f"\nOverall Score: {run.report.overall_score}")
        print(f"Lead Score: {run.lead_score.score} ({run.lead_score.tier.value})")
        print(f"\nExecutive Summary:\n{run.report.executive_summary}")
        print(f"\nGaps identified ({len(run.report.gap_sections)}):")
        for gap in run.report.gap_sections:
            print(f"  - {gap.title}")
            print(f"    Advisor: {gap.suggested_advisor_profile}")

        # Save full output for closer review
        out_path = f"docs/eval_output_{profile.company_name.lower().replace(' ', '_')}.json"
        with open(out_path, "w") as f:
            f.write(run.model_dump_json(indent=2))
        print(f"\nFull output saved to {out_path}")


if __name__ == "__main__":
    asyncio.run(run_eval())
