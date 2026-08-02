import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { api } from "../api";
import Message from "../components/Message";
import {
  confidenceLabel,
  riskLabel,
  workflowLabel,
} from "../pageIntakePresentation";
import { mappingModeForWorkflow } from "../workflowTemplatePresentation";

function AnalyzePage() {
  const navigate = useNavigate();
  const [profiles, setProfiles] = useState([]);
  const [form, setForm] = useState({
    url: "",
    user_goal: "",
    profile_id: "",
  });
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState("");
  const [intake, setIntake] = useState(null);

  useEffect(() => {
    api
      .listProfiles()
      .then((profileItems) => {
        setProfiles(profileItems);
        if (profileItems.length) {
          setForm((current) => ({
            ...current,
            profile_id: String(profileItems[0].id),
          }));
        }
      })
      .catch((requestError) => setError(requestError.message))
      .finally(() => setLoading(false));
  }, []);

  async function analyzePage(event) {
    event.preventDefault();
    setAnalyzing(true);
    setError("");
    try {
      const result = await api.analyzePageIntake({
        url: form.url,
        profile_id: Number(form.profile_id),
        user_goal: form.user_goal,
      });
      setIntake(result);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setAnalyzing(false);
    }
  }

  function updateForm(patch) {
    setForm((current) => ({ ...current, ...patch }));
    setIntake(null);
  }

  async function startWorkflow() {
    if (!intake) {
      return;
    }
    setStarting(true);
    setError("");
    let task = null;
    try {
      task = await api.createTask({
        url: form.url,
        profile_id: Number(form.profile_id),
        description: form.user_goal || null,
        workflow_type: intake.recommended_workflow,
      });

      const persistedIntake = await api.analyzePageIntake({
        url: form.url,
        profile_id: Number(form.profile_id),
        user_goal: form.user_goal,
        task_id: task.id,
      });

      const workflowType = persistedIntake.recommended_workflow;

      if (workflowType === "web_data_extract") {
        await api.extractTaskPage(task.id);
        navigate(`/tasks/${task.id}`);
        return;
      }

      if (workflowType === "job_research_summary") {
        await api.generateJobSummary(task.id);
        navigate(`/tasks/${task.id}`);
        return;
      }

      const analyzedTask = await api.analyzeTask(task.id);
      if (analyzedTask.status === "LOGIN_REQUIRED") {
        navigate(`/tasks/${task.id}`, {
          state: {
            notice: "This form requires login before fields can be extracted.",
          },
        });
        return;
      }

      const mappingMode =
        workflowType === "form_fill"
          ? "rules"
          : mappingModeForWorkflow(workflowType);
      await api.mapTaskFields(task.id, { mode: mappingMode });
      navigate(`/tasks/${task.id}/review-mapping`);
    } catch (requestError) {
      if (task?.id) {
        navigate(`/tasks/${task.id}`, {
          state: { error: requestError.message },
        });
        return;
      }
      setError(requestError.message);
      setStarting(false);
    }
  }

  return (
    <section className="narrow-page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">Page intake</p>
          <h2>Analyze Page</h2>
          <p>
            Understand a page before committing to a workflow. Detects page type,
            risks, and the best automation approach.
          </p>
        </div>
      </div>

      <Message type="error">{error}</Message>

      <form className="card form-card" onSubmit={analyzePage}>
        <label>
          Form URL
          <input
            type="url"
            value={form.url}
            onChange={(event) => updateForm({ url: event.target.value })}
            placeholder="https://example.com/application"
            required
          />
        </label>

        <label>
          Profile
          <select
            value={form.profile_id}
            onChange={(event) => updateForm({ profile_id: event.target.value })}
            required
            disabled={loading || profiles.length === 0}
          >
            {profiles.length === 0 && <option value="">No profiles available</option>}
            {profiles.map((profile) => (
              <option key={profile.id} value={profile.id}>
                {profile.profile_name}
              </option>
            ))}
          </select>
        </label>

        <label>
          User goal
          <textarea
            rows="3"
            value={form.user_goal}
            onChange={(event) => updateForm({ user_goal: event.target.value })}
            placeholder="What do you want to achieve on this page?"
          />
        </label>

        <button
          className="button"
          type="submit"
          disabled={analyzing || loading || profiles.length === 0}
        >
          {analyzing ? "Analyzing page..." : "Analyze Page"}
        </button>
      </form>

      {intake && (
        <section className="page-overview">
          <div className="card page-overview-card">
            <div className="page-overview-grid">
              <div>
                <dt>Page type</dt>
                <dd>{intake.page_type}</dd>
              </div>
              <div>
                <dt>Recommended workflow</dt>
                <dd>{workflowLabel(intake.recommended_workflow)}</dd>
              </div>
              <div>
                <dt>Confidence</dt>
                <dd>
                  <span className="badge">{confidenceLabel(intake.confidence)}</span>
                  <span className="muted"> ({intake.confidence.toFixed(2)})</span>
                </dd>
              </div>
            </div>

            <p>{intake.summary}</p>

            {intake.risk_flags?.length > 0 && (
              <div>
                <h3>Risk flags</h3>
                <div className="risk-list">
                  {intake.risk_flags.map((flag) => (
                    <span key={flag} className="badge badge-warning">
                      {riskLabel(flag)}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {intake.blocked_reasons?.length > 0 && (
              <div>
                <h3>Blocked reasons</h3>
                <ul className="blocked-reasons">
                  {intake.blocked_reasons.map((reason, index) => (
                    <li key={index}>{reason}</li>
                  ))}
                </ul>
              </div>
            )}

            {intake.detected_fields?.length > 0 && (
              <div>
                <h3>Detected fields</h3>
                <table className="data-table detected-field-list">
                  <thead>
                    <tr>
                      <th>Label</th>
                      <th>Type</th>
                      <th>Required</th>
                      <th>Selector</th>
                    </tr>
                  </thead>
                  <tbody>
                    {intake.detected_fields.map((field, index) => (
                      <tr key={index}>
                        <td>{field.label || <span className="muted">—</span>}</td>
                        <td>{field.field_type}</td>
                        <td>{field.required ? "Yes" : "No"}</td>
                        <td className="field-ref">{field.selector}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {intake.evidence?.length > 0 && (
              <div>
                <h3>Evidence</h3>
                <div className="evidence-list">
                  {intake.evidence.map((item, index) => (
                    <div key={index} className="evidence-item">
                      <span className="badge">{item.source}</span>
                      <p className="muted">{item.text}</p>
                      <p>{item.reason}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="button-row">
              <button
                className="button"
                type="button"
                onClick={startWorkflow}
                disabled={starting}
              >
                {starting
                  ? "Starting workflow..."
                  : `Start ${workflowLabel(intake.recommended_workflow)}`}
              </button>
            </div>
          </div>
        </section>
      )}
    </section>
  );
}

export default AnalyzePage;
