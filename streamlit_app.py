"""
Board Readiness Score — Streamlit version.

This is a second front door onto the exact same agent pipeline used by
the main HTML/FastAPI frontend (app/, mcp_server/). Nothing about the
agents, scoring, or MCP tool changes here — this file only adds a UI
layer that Streamlit Community Cloud can host for free at a public URL,
so people other than the person running it locally can actually try it.

Deployment note: on Streamlit Community Cloud there is no .env file,
so secrets are set via Streamlit's own Secrets manager instead. The
block below bridges those secrets into environment variables BEFORE
any app.* module is imported, since app.config.settings reads them at
import time.
"""
import asyncio

import streamlit as st

# --- Bridge Streamlit secrets into env vars, before importing app.* ---
try:
    import os

    for key in ("MODEL_PROVIDER", "GROQ_API_KEY", "GROQ_MODEL", "OLLAMA_BASE_URL", "OLLAMA_MODEL"):
        if key in st.secrets:
            os.environ[key] = st.secrets[key]
except Exception:
    # No secrets.toml present (e.g. running locally with a .env file
    # instead) — that's fine, app.config.settings will read .env.
    pass

from app.models.schemas import FounderInput
from app.orchestration.pipeline import run_assessment

st.set_page_config(
    page_title="Board Readiness Score — Connectd",
    page_icon="📋",
    layout="centered",
)

# Light custom styling on top of the theme config, for the bits
# Streamlit's theme system doesn't cover (fonts, score display).
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Fraunces:wght@500;600&family=Inter:wght@400;500&display=swap');
    h1, h2, h3 { font-family: 'Fraunces', Georgia, serif !important; }
    .score-number {
        font-family: 'Fraunces', Georgia, serif;
        font-size: 64px;
        color: #B08D57;
        line-height: 1;
        margin-bottom: 0;
    }
    .score-label { color: #55584F; font-size: 14px; }
    .advisor-tag { color: #2B4C3F; font-size: 13px; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown("**Connectd**")
st.title("Board Readiness Score")
st.write(
    "A short, free assessment of your startup's board and advisory "
    "readiness — where you're strong, where a senior advisor could "
    "genuinely help, and what to do about it."
)

if "result" not in st.session_state:
    st.session_state.result = None

# ---------------- Form ----------------
if st.session_state.result is None:
    with st.form("assessment_form"):
        company_name = st.text_input("Company name", placeholder="Acme Robotics")
        website = st.text_input("Website (optional)", placeholder="acme.com")

        col1, col2 = st.columns(2)
        with col1:
            stage = st.selectbox("Stage", ["", "Pre-seed", "Seed", "Series A"])
        with col2:
            industry = st.text_input("Industry", placeholder="Fintech")

        team_size = st.number_input("Team size", min_value=1, step=1, value=None, placeholder="12")

        existing_board = st.text_area(
            "Existing board or advisors (optional)",
            placeholder="e.g. one investor board seat, no independent advisors",
        )
        challenges = st.text_area(
            "Current strategic challenges (optional)",
            placeholder="e.g. preparing for a Series A raise",
        )
        expertise_needs = st.text_area(
            "Where do you feel you need senior expertise? (optional)",
            placeholder="e.g. financial governance, go-to-market strategy",
        )

        submitted = st.form_submit_button("Get your Board Readiness Score")

    if submitted:
        if not company_name or not stage or not industry or not team_size:
            st.error("Please fill in company name, stage, industry, and team size.")
        else:
            founder_input = FounderInput(
                company_name=company_name,
                website=website or None,
                stage=stage,
                industry=industry,
                team_size=int(team_size),
                existing_board_or_advisors=existing_board or None,
                current_strategic_challenges=challenges or None,
                areas_seeking_expertise=expertise_needs or None,
            )
            with st.spinner("Running the assessment — this takes a few seconds..."):
                run = asyncio.run(run_assessment(founder_input))
            st.session_state.result = run
            st.rerun()

# ---------------- Report ----------------
else:
    run = st.session_state.result

    if run.status.value != "complete":
        failed = next((m for m in run.run_metadata if not m.success), None)
        st.error(
            f"The {failed.agent_name.replace('_', ' ') if failed else 'assessment'} "
            f"step failed. Please try again."
        )
        if st.button("Try again"):
            st.session_state.result = None
            st.rerun()
    else:
        report = run.report
        analysis = run.board_analysis

        st.markdown(f'<p class="score-number">{report.overall_score}</p>', unsafe_allow_html=True)
        st.markdown('<p class="score-label">Board Readiness Score</p>', unsafe_allow_html=True)
        st.divider()

        st.write(report.executive_summary)

        st.subheader("Full scorecard")
        st.caption("All 8 dimensions, with the AI's evidence for each rating")
        for dim in analysis.dimension_scores:
            st.markdown(f"**{dim.name.value}** — {dim.score}")
            st.progress(dim.score / 100)
            for e in dim.evidence:
                st.caption(f"• {e}")

        st.subheader("Where you're strong")
        for s in report.strengths:
            st.markdown(f"- {s}")

        st.subheader("Where you may need senior expertise")
        for gap in report.gap_sections:
            with st.expander(gap.title):
                st.write(gap.why_it_matters)
                st.markdown(f'<p class="advisor-tag">Suggested advisor: {gap.suggested_advisor_profile}</p>', unsafe_allow_html=True)

        st.subheader("Governance readiness")
        st.caption("Current signals")
        for s in report.governance_current_signals:
            st.markdown(f"- {s}")
        st.caption("Potential improvements")
        for s in report.governance_improvements:
            st.markdown(f"- {s}")

        st.subheader("Recommended next steps")
        for i, step in enumerate(report.recommended_next_steps, 1):
            st.markdown(f"{i}. {step}")

        st.divider()
        st.info(report.cta_text)
        st.link_button("Get matched with Connectd advisors", "https://connectd.co")

        if st.button("Start a new assessment"):
            st.session_state.result = None
            st.rerun()
