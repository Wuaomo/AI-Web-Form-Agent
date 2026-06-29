import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";

import { api, API_BASE_URL } from "../api";
import {
  buildAgentTimeline,
  fieldDisplayName,
  isFillableField,
} from "../agentTimeline";
import LlmMappingControls from "../components/LlmMappingControls";
import {
  getSavedLlmProvider,
  saveLlmProvider,
} from "../llmProviderPreference";
import Message from "../components/Message";

function needsRequiredInput(field) {
  return field.required && isFillableField(field) && !field.mapped_value;
}

function TaskDetail() {
  const { taskId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const [task, setTask] = useState(null);
  const [logs, setLogs] = useState([]);
  const [screenshots, setScreenshots] = useState([]);
  const [profiles, setProfiles] = useState([]);
  const [llmProviders, setLlmProviders] = useState([]);
  const [mappingMode, setMappingMode] = useState("llm");
  const [selectedLlmProvider, setSelectedLlmProvider] = useState("");
  const [loading, setLoading] = useState(true);
  const [busyAction, setBusyAction] = useState("");
  const [error, setError] = useState(location.state?.error || "");
  const [notice, setNotice] = useState(location.state?.notice || "");

  useEffect(() => {
    if (location.state?.notice) {
      setNotice(location.state.notice);
      navigate(location.pathname, { replace: true, state: null });
    }
  }, [location.pathname, location.state, navigate]);

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
        setSelectedLlmProvider(getSavedLlmProvider(providerItems));
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

  function getMappingOptions() {
    return {
      mode: mappingMode,
      provider: mappingMode === "llm" ? selectedLlmProvider : undefined,
    };
  }

  async function analyzeAndReview() {
    setBusyAction("analyze");
    setError("");
    setNotice("");
    try {
      await api.analyzeTask(taskId);
      await api.mapTaskFields(taskId, getMappingOptions());
      await refreshTaskHistory();
      navigate(`/tasks/${taskId}/review-mapping`);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusyAction("");
    }
  }

  async function loginAnalyzeAndMap() {
    setBusyAction("login");
    setError("");
    setNotice("");
    try {
      const analyzedTask = await api.loginAndAnalyzeTask(taskId);
      await refreshTaskHistory(analyzedTask);
      if (!llmUnavailable && selectedLlmProvider) {
        await api.mapTaskFields(taskId, {
          mode: mappingMode,
          provider: selectedLlmProvider,
        });
        navigate(`/tasks/${taskId}/review-mapping`);
        return;
      }
      setNotice("Login complete. Choose a model provider, then map fields.");
    } catch (requestError) {
      setError(requestError.message);
      await refreshTaskHistory();
    } finally {
      setBusyAction("");
    }
  }

  function updateSelectedLlmProvider(provider) {
    setSelectedLlmProvider(provider);
    saveLlmProvider(provider);
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
  const agentTimeline = buildAgentTimeline(logs, task?.form_fields || []);

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

          {task.status === "LOGIN_REQUIRED" && (
            <div className="message message-warning">
              This site requires login before the form can be extracted. Log in
              in the browser window, then close it to continue.
            </div>
          )}

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
              onProviderChange={updateSelectedLlmProvider}
              providers={llmProviders}
              disabled={isBusy}
            />
            <div className="button-row">
              {task.status === "LOGIN_REQUIRED" && (
                <button
                  className="button"
                  type="button"
                  onClick={loginAnalyzeAndMap}
                  disabled={isBusy}
                >
                  {busyAction === "login" ? "Waiting for login..." : "Login and Continue"}
                </button>
              )}
              <button
                className="button"
                type="button"
                onClick={analyzeAndReview}
                disabled={isBusy || llmUnavailable || task.status === "LOGIN_REQUIRED"}
              >
                {busyAction === "analyze" ? "Analyzing..." : "Analyze & Review"}
              </button>
              <Link className="button button-secondary" to={`/tasks/${task.id}/review-mapping`}>
                Review Mapping
              </Link>
              <button
                className="button"
                type="button"
                onClick={() =>
                  runAction(
                    "fill",
                    () => api.fillTask(taskId),
                    "Form filled. Review the screenshot before final submission.",
                  )
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
                      "Form submitted after your approval.",
                    )
                  }
                  disabled={isBusy}
                >
                  {busyAction === "confirm" ? "Submitting..." : "Submit Form"}
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
              <div className="agent-log-list">
                {agentTimeline.map((entry) => (
                  <article className="agent-log-entry" key={entry.id}>
                    <div className="agent-log-marker" aria-hidden="true" />
                    <div className="agent-log-body">
                      <div className="agent-log-main">
                        <div>
                          <p className="agent-log-title">{entry.title}</p>
                          <time className="agent-log-time" dateTime={entry.createdAt}>
                            {new Date(entry.createdAt).toLocaleString()}
                          </time>
                        </div>
                        <span className="badge">{entry.status}</span>
                      </div>
                      {entry.details.length > 0 && (
                        <details className="agent-log-details">
                          <summary>Technical details</summary>
                          <dl>
                            {entry.details.map((detail, index) => (
                              <div key={`${detail.label}-${index}`}>
                                <dt>{detail.label}</dt>
                                <dd>{detail.value}</dd>
                              </div>
                            ))}
                          </dl>
                        </details>
                      )}
                    </div>
                  </article>
                ))}
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
