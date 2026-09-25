const API_BASE = "http://localhost:8000";

const formPanel = document.getElementById("form-panel");
const processingPanel = document.getElementById("processing-panel");
const errorPanel = document.getElementById("error-panel");
const reportPanel = document.getElementById("report-panel");

const processingMessageEl = document.getElementById("processing-message");
const progressFillEl = document.getElementById("progress-fill");

const PROCESSING_STAGES = [
  "Understanding your company…",
  "Enriching company context…",
  "Assessing board readiness…",
  "Building your report…",
];

function showOnly(panel) {
  [formPanel, processingPanel, errorPanel, reportPanel].forEach((p) => {
    p.classList.toggle("hidden", p !== panel);
  });
}

function startProcessingAnimation() {
  let stageIndex = 0;
  processingMessageEl.textContent = PROCESSING_STAGES[0];
  progressFillEl.style.width = "8%";

  // We cycle through stage messages on a timer since the backend runs
  // the full pipeline synchronously and doesn't stream progress yet.
  // This is an honest approximation, not a claim of real-time status.
  const interval = setInterval(() => {
    stageIndex = Math.min(stageIndex + 1, PROCESSING_STAGES.length - 1);
    processingMessageEl.textContent = PROCESSING_STAGES[stageIndex];
    const pct = 8 + (stageIndex / (PROCESSING_STAGES.length - 1)) * 80;
    progressFillEl.style.width = `${pct}%`;
  }, 2500);

  return () => clearInterval(interval);
}

function renderReport(assessmentRun) {
  const report = assessmentRun.report;
  const analysis = assessmentRun.board_analysis;

  document.getElementById("report-score").textContent = report.overall_score;
  document.getElementById("report-summary").textContent = report.executive_summary;

  // Full 8-dimension scorecard — shows exactly why the overall score
  // landed where it did, dimension by dimension, with the AI's evidence.
  const dimensionsEl = document.getElementById("report-dimensions");
  dimensionsEl.innerHTML = "";
  analysis.dimension_scores.forEach((dim) => {
    const div = document.createElement("div");
    div.className = "dimension-item";
    const evidenceList = dim.evidence.map((e) => `<li>${escapeHtml(e)}</li>`).join("");
    div.innerHTML = `
      <div class="dimension-header">
        <span class="dimension-name">${escapeHtml(dim.name)}</span>
        <span class="dimension-score">${dim.score}</span>
      </div>
      <div class="dimension-bar-track">
        <div class="dimension-bar-fill" style="width: ${dim.score}%"></div>
      </div>
      <ul class="dimension-evidence">${evidenceList}</ul>
    `;
    dimensionsEl.appendChild(div);
  });

  const strengthsEl = document.getElementById("report-strengths");
  strengthsEl.innerHTML = "";
  report.strengths.forEach((s) => {
    const li = document.createElement("li");
    li.textContent = s;
    strengthsEl.appendChild(li);
  });

  const gapsEl = document.getElementById("report-gaps");
  gapsEl.innerHTML = "";
  report.gap_sections.forEach((gap) => {
    const div = document.createElement("div");
    div.className = "gap-item";
    div.innerHTML = `
      <h4>${escapeHtml(gap.title)}</h4>
      <p>${escapeHtml(gap.why_it_matters)}</p>
      <p class="gap-advisor">Suggested advisor profile: ${escapeHtml(gap.suggested_advisor_profile)}</p>
    `;
    gapsEl.appendChild(div);
  });

  const govSignalsEl = document.getElementById("report-governance-signals");
  govSignalsEl.innerHTML = "";
  report.governance_current_signals.forEach((s) => {
    const li = document.createElement("li");
    li.textContent = s;
    govSignalsEl.appendChild(li);
  });

  const govImprovementsEl = document.getElementById("report-governance-improvements");
  govImprovementsEl.innerHTML = "";
  report.governance_improvements.forEach((s) => {
    const li = document.createElement("li");
    li.textContent = s;
    govImprovementsEl.appendChild(li);
  });

  const nextStepsEl = document.getElementById("report-next-steps");
  nextStepsEl.innerHTML = "";
  report.recommended_next_steps.forEach((s) => {
    const li = document.createElement("li");
    li.textContent = s;
    nextStepsEl.appendChild(li);
  });

  document.getElementById("report-cta").textContent = report.cta_text;

  showOnly(reportPanel);
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function showError(message) {
  document.getElementById("error-message").textContent = message;
  showOnly(errorPanel);
}

async function submitAssessment(formData) {
  const payload = {
    company_name: formData.get("company_name"),
    website: formData.get("website") || null,
    stage: formData.get("stage"),
    industry: formData.get("industry"),
    team_size: parseInt(formData.get("team_size"), 10),
    existing_board_or_advisors: formData.get("existing_board_or_advisors") || null,
    current_strategic_challenges: formData.get("current_strategic_challenges") || null,
    areas_seeking_expertise: formData.get("areas_seeking_expertise") || null,
  };

  const response = await fetch(`${API_BASE}/api/assessment`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`Server returned ${response.status}`);
  }

  return response.json();
}

document.getElementById("assessment-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const formData = new FormData(e.target);

  showOnly(processingPanel);
  const stopAnimation = startProcessingAnimation();

  try {
    const run = await submitAssessment(formData);
    stopAnimation();

    if (run.status === "complete" && run.report) {
      renderReport(run);
    } else {
      // Pipeline ran but a stage failed — surface a useful message,
      // not a stack trace (Section 18).
      const failedStage = run.run_metadata.find((m) => !m.success);
      const detail = failedStage
        ? `The ${failedStage.agent_name.replace("_", " ")} step failed. ` +
          `Make sure Ollama is running locally (\`ollama serve\`).`
        : "The assessment could not be completed.";
      showError(detail);
    }
  } catch (err) {
    stopAnimation();
    showError(
      `Couldn't reach the backend at ${API_BASE}. Make sure the FastAPI ` +
        `server is running (\`uvicorn app.main:app --reload\`).`
    );
  }
});

document.getElementById("error-retry").addEventListener("click", () => {
  showOnly(formPanel);
});
