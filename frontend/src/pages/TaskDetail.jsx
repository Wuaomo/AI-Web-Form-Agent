import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { api, API_BASE_URL } from "../api";
import LlmMappingControls from "../components/LlmMappingControls";
import Message from "../components/Message";

const nonFillableFieldTypes = new Set(["button", "submit", "reset", "image"]);

function isFillableField(field) {
  return !nonFillableFieldTypes.has((field.field_type || "").toLowerCase());
}

function fieldDisplayName(field) {
  return field.label || field.name || field.placeholder || field.selector;
}

function needsRequiredInput(field) {
  return field.required && isFillableField(field) && !field.mapped_value;
}

function TaskDetail() {
  const { taskId } = useParams();
  const navigate = useNavigate();
  const [task, setTask] = useState(null);
  const [logs, setLogs] = useState([]);
  const [screenshots, setScreenshots] = useState([]);
  const [profiles, setProfiles] = useState([]);
  const [llmProviders, setLlmProviders] = useState([]);
  const [mappingMode, setMappingMode] = useState("llm");
  const [selectedLlmProvider, setSelectedLlmProvider] = useState("");
  const [loading, setLoading] = useState(true);
  const [busyAction, setBusyAction] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    Promise.all([
      api.getTask(taskId),
      api.listTaskLogs(taskId),
      api.listTaskScreenshots(taskId),
      api.listProfiles(),
      api.listLlmProviders(),
    ])
      .then(([taskResult, logItems, screenshotItems, profileItems, providerItems]) => {
        setTask(taskResult);
        setLogs(logItems);
        setScreenshots(screenshotItems);
        setProfiles(profileItems);
        setLlmProviders(providerItems);
        setSelectedLlmProvider(
          providerItems.find((provider) => provider.selected)?.id ||
            providerItems.find((provider) => provider.configured)?.id ||
            providerItems[0]?.id ||
            "",
        );
      })
      .catch((requestError) => setError(requestError.message))
      .finally(() => setLoading(false));
  }, [taskId]);

  async function refreshTaskHistory(nextTask = null) {
    const [taskResult, logItems, screenshotItems] = await Promise.all([
      nextTask ? Promise.resolve(nextTask) : api.getTask(taskId),
      api.listTaskLogs(taskId),
      api.listTaskScreenshots(taskId),
    ]);
    setTask(taskResult);
    setLogs(logItems);
    setScreenshots(screenshotItems);
  }

  async function runAction(actionName, request, successMessage) {
    setBusyAction(actionName);
    setError("");
    setNotice("");
    try {
      const result = await request();
      await refreshTaskHistory(result?.id ? result : null);
      setNotice(successMessage);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusyAction("");
    }
  }

  async function mapFieldsAndReview() {
    setBusyAction("map");
    setError("");
    setNotice("");
    try {
      await api.mapTaskFields(taskId, {
        mode: mappingMode,
        provider: mappingMode === "llm" ? selectedLlmProvider : undefined,
      });
      await refreshTaskHistory();
      navigate(`/tasks/${taskId}/review-mapping`);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusyAction("");
    }
  }

  if (loading) {
    return <p>Loading task...</p>;
  }

  const profileName =
    profiles.find((profile) => profile.id === task?.profile_id)?.profile_name ||
    (task ? `Profile #${task.profile_id}` : "—");
  const isBusy = Boolean(busyAction);
  const hasMappedFields = task?.form_fields.some((field) => field.mapped_value);
  const selectedProvider = llmProviders.find(
    (provider) => provider.id === selectedLlmProvider,
  );
  const llmUnavailable = mappingMode === "llm" && !selectedProvider?.configured;
  const missingRequiredFields = task?.form_fields.filter(needsRequiredInput) || [];
  const canFill = hasMappedFields && missingRequiredFields.length === 0;

  return (
    <section>
      <Message type="error">{error}</Message>
      <Message type="success">{notice}</Message>
      {task && (
        <>
          <div className="page-heading">
            <div>
              <p className="eyebrow">Task #{task.id}</p>
              <h2>Task Detail</h2>
              <p className="break-word">{task.url}</p>
            </div>
            <span className="badge badge-large">{task.status}</span>
          </div>

          <article className="card">
            <dl className="detail-list">
              <div>
                <dt>Status</dt>
                <dd>{task.status}</dd>
              </div>
              <div>
                <dt>URL</dt>
                <dd>
                  <a className="break-word" href={task.url} target="_blank" rel="noreferrer">
                    {task.url}
                  </a>
                </dd>
              </div>
              <div>
                <dt>Profile</dt>
                <dd>{profileName}</dd>
              </div>
              <div>
                <dt>Description</dt>
                <dd>{task.description || "—"}</dd>
              </div>
              <div>
                <dt>Extracted fields</dt>
                <dd>{task.form_fields.length}</dd>
              </div>
              <div>
                <dt>Required missing</dt>
                <dd>
                  {missingRequiredFields.length === 0
                    ? "None"
                    : missingRequiredFields.map(fieldDisplayName).join(", ")}
                </dd>
              </div>
            </dl>
            <LlmMappingControls
              mode={mappingMode}
              onModeChange={setMappingMode}
              provider={selectedLlmProvider}
              onProviderChange={setSelectedLlmProvider}
              providers={llmProviders}
              disabled={isBusy}
            />
            <div className="button-row">
              <button
                className="button"
                type="button"
                onClick={() =>
                  runAction("analyze", () => api.analyzeTask(taskId), "Analysis complete.")
                }
                disabled={isBusy}
              >
                {busyAction === "analyze" ? "Analyzing..." : "Analyze"}
              </button>
              <button
                className="button button-secondary"
                type="button"
                onClick={mapFieldsAndReview}
                disabled={isBusy || task.form_fields.length === 0 || llmUnavailable}
              >
                {busyAction === "map" ? "Mapping..." : "Map Fields"}
              </button>
              <Link className="button button-secondary" to={`/tasks/${task.id}/review-mapping`}>
                Review Mapping
              </Link>
              <button
                className="button"
                type="button"
                onClick={() =>
                  runAction("fill", () => api.fillTask(taskId), "Form filled. Review before submit.")
                }
                disabled={isBusy || !canFill}
              >
                {busyAction === "fill" ? "Filling..." : "Fill Form"}
              </button>
              {task.status === "WAITING_APPROVAL" && (
                <button
                  className="button button-secondary"
                  type="button"
                  onClick={() =>
                    runAction(
                      "confirm",
                      () => api.confirmSubmit(taskId),
                      "Submission approval recorded.",
                    )
                  }
                  disabled={isBusy}
                >
                  {busyAction === "confirm" ? "Confirming..." : "Confirm Submit"}
                </button>
              )}
            </div>
          </article>

          <section className="section-block">
            <div className="section-heading">
              <h3>Action Logs</h3>
            </div>
            {logs.length === 0 ? (
              <div className="card empty-state">
                <p>No action logs yet.</p>
              </div>
            ) : (
              <div className="table-wrapper card">
                <table>
                  <thead>
                    <tr>
                      <th>Step</th>
                      <th>Action</th>
                      <th>Status</th>
                      <th>Message</th>
                      <th>Time</th>
                    </tr>
                  </thead>
                  <tbody>
                    {logs.map((log) => (
                      <tr key={log.id}>
                        <td>{log.step}</td>
                        <td>{log.action}</td>
                        <td>
                          <span className="badge">{log.status}</span>
                        </td>
                        <td>{log.message || "—"}</td>
                        <td>{new Date(log.created_at).toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="section-block">
            <div className="section-heading">
              <h3>Screenshots</h3>
            </div>
            {screenshots.length === 0 ? (
              <div className="card empty-state">
                <p>No screenshots captured yet.</p>
              </div>
            ) : (
              <div className="screenshot-grid">
                {screenshots.map((screenshot) => (
                  <article className="card screenshot-card" key={screenshot.id}>
                    <a
                      href={new URL(screenshot.file_path, `${API_BASE_URL}/`).toString()}
                      target="_blank"
                      rel="noreferrer"
                    >
                      <img
                        src={new URL(screenshot.file_path, `${API_BASE_URL}/`).toString()}
                        alt={`${screenshot.stage} screenshot`}
                      />
                    </a>
                    <p>
                      <strong>{screenshot.stage}</strong>
                      <span>{new Date(screenshot.created_at).toLocaleString()}</span>
                    </p>
                  </article>
                ))}
              </div>
            )}
          </section>
        </>
      )}
    </section>
  );
}

export default TaskDetail;
