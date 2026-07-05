import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";

import { api, API_BASE_URL } from "../api";
import { getWorkflowTimeline, shouldShowWorkflowTimeline } from "../agentTimeline";
import { generateDebugReport } from "../debugReport";
import LlmMappingControls from "../components/LlmMappingControls";
import { formatChinaTime } from "../dateTime";
import {
  getSavedLlmProvider,
  saveLlmProvider,
} from "../llmProviderPreference";
import {
  formatLatency,
  formatEstimatedCost,
  formatCacheHitRate,
} from "../llmUsagePresentation";
import Message from "../components/Message";
import {
  getTaskRunState,
  getVisibleRunSummaryItems,
} from "../taskRunState";
import { fieldDisplayName, needsRequiredInput } from "../reviewMappingPresentation";
import {
  summarizeJob,
  getNewestJob,
  newestJobStatusLine,
} from "../jobPresentation";
import {
  summarizeVerificationResults,
  verificationReasonLabel,
} from "../verificationPresentation";
import {
  decisionLabel,
  roleLabel,
  getLatestReview,
  summarizeReviewItems,
  groupReviewsByRole,
} from "../agentReviewPresentation";
import {
  phaseLabel,
  sortSpans,
  spanStatusLabel,
  summarizeSpan,
} from "../workflowTracePresentation";

function TaskDetail() {
  const { taskId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const [task, setTask] = useState(null);
  const [screenshots, setScreenshots] = useState([]);
  const [profiles, setProfiles] = useState([]);
  const [llmProviders, setLlmProviders] = useState([]);
  const [mappingMode, setMappingMode] = useState("llm");
  const [selectedLlmProvider, setSelectedLlmProvider] = useState("");
  const [loading, setLoading] = useState(true);
  const [busyAction, setBusyAction] = useState("");
  const [error, setError] = useState(location.state?.error || "");
  const [notice, setNotice] = useState(location.state?.notice || "");
  const [profileUpdates, setProfileUpdates] = useState(
    location.state?.profileUpdates || [],
  );
  const [llmUsage, setLlmUsage] = useState(null);
  const [taskLogs, setTaskLogs] = useState([]);
  const [taskCheckpoints, setTaskCheckpoints] = useState([]);
  const [taskJobs, setTaskJobs] = useState([]);
  const [verificationResults, setVerificationResults] = useState([]);
  const [agentReviews, setAgentReviews] = useState([]);
  const [workflowTrace, setWorkflowTrace] = useState([]);
  const [approvalRequests, setApprovalRequests] = useState([]);
  const [runningReview, setRunningReview] = useState(null);
  const agentReviewInFlight = useRef(false);

  useEffect(() => {
    if (
      location.state?.notice ||
      location.state?.profileUpdates
    ) {
      if (location.state?.notice) {
        setNotice(location.state.notice);
      }
      if (location.state?.profileUpdates) {
        setProfileUpdates(location.state.profileUpdates);
      }
      navigate(location.pathname, { replace: true, state: null });
    }
  }, [location.pathname, location.state, navigate]);

  useEffect(() => {
    Promise.all([
      api.getTask(taskId),
      api.listTaskScreenshots(taskId),
      api.listProfiles(),
      api.listLlmProviders(),
      api.listTaskLogs(taskId),
      api.getTaskLlmUsage(taskId).catch(() => null),
      api.listTaskCheckpoints(taskId).catch(() => []),
      api.listTaskJobs(taskId).catch(() => []),
      api.getTaskVerificationResults(taskId).catch(() => []),
      api.getTaskAgentReviews(taskId).catch(() => []),
      api.getTaskTrace(taskId).catch(() => []),
      api.listApprovals({ taskId }).catch(() => []),
    ])
      .then(([taskResult, screenshotItems, profileItems, providerItems, logItems, usageResult, checkpointItems, jobItems, verificationItems, reviewItems, traceItems, approvalItems]) => {
        setTask(taskResult);
        setScreenshots(screenshotItems);
        setProfiles(profileItems);
        setLlmProviders(providerItems);
        setTaskLogs(logItems);
        setLlmUsage(usageResult);
        setTaskCheckpoints(checkpointItems);
        setTaskJobs(jobItems);
        setVerificationResults(verificationItems);
        setAgentReviews(reviewItems);
        setWorkflowTrace(traceItems);
        setApprovalRequests(approvalItems);
        setSelectedLlmProvider(getSavedLlmProvider(providerItems));
      })
      .catch((requestError) => setError(requestError.message))
      .finally(() => setLoading(false));
  }, [taskId]);

  async function refreshTaskData(nextTask = null) {
    const [taskResult, screenshotItems, logItems, usageResult, checkpointItems, jobItems, verificationItems, reviewItems, traceItems] = await Promise.all([
      nextTask ? Promise.resolve(nextTask) : api.getTask(taskId),
      api.listTaskScreenshots(taskId),
      api.listTaskLogs(taskId),
      api.getTaskLlmUsage(taskId).catch(() => null),
      api.listTaskCheckpoints(taskId).catch(() => []),
      api.listTaskJobs(taskId).catch(() => []),
      api.getTaskVerificationResults(taskId).catch(() => []),
      api.getTaskAgentReviews(taskId).catch(() => []),
      api.getTaskTrace(taskId).catch(() => []),
      api.listApprovals({ taskId }).catch(() => []),
    ]);
    setTask(taskResult);
    setScreenshots(screenshotItems);
    setTaskLogs(logItems);
    setLlmUsage(usageResult);
    setTaskCheckpoints(checkpointItems);
    setTaskJobs(jobItems);
    setVerificationResults(verificationItems);
    setAgentReviews(reviewItems);
    setWorkflowTrace(traceItems);
    setApprovalRequests(approvalItems);
  }

  async function runAgentReview(role) {
    if (agentReviewInFlight.current) return;
    agentReviewInFlight.current = true;
    setRunningReview(role);
    setError("");
    try {
      const results = await api.runTaskAgentReviews(taskId, [role]);
      setAgentReviews(results);
      setNotice(`${roleLabel(role)} completed.`);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      agentReviewInFlight.current = false;
      setRunningReview(null);
    }
  }

  async function runAction(actionName, request, successMessage) {
    setBusyAction(actionName);
    setError("");
    setNotice("");
    try {
      const result = await request();
      await refreshTaskData(result?.id ? result : null);
      setNotice(successMessage);
    } catch (requestError) {
      setError(requestError.message);
      await refreshTaskData();
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
      const analyzedTask = await api.analyzeTask(taskId);
      await refreshTaskData(analyzedTask);
      if (analyzedTask.status === "LOGIN_REQUIRED") {
        setNotice("Login is required before the form can be prepared.");
        return;
      }
      await api.mapTaskFields(taskId, getMappingOptions());
      await refreshTaskData();
      navigate(`/tasks/${taskId}/review-mapping`);
    } catch (requestError) {
      setError(requestError.message);
      await refreshTaskData();
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
      await refreshTaskData(analyzedTask);
      if (mappingMode === "rules" || (!llmUnavailable && selectedLlmProvider)) {
        await api.mapTaskFields(taskId, getMappingOptions());
        await refreshTaskData();
        navigate(`/tasks/${taskId}/review-mapping`);
        return;
      }
      setNotice("Login complete. Choose a model provider, then map fields.");
    } catch (requestError) {
      setError(requestError.message);
      await refreshTaskData();
    } finally {
      setBusyAction("");
    }
  }

  async function copyDebugReport() {
    const report = generateDebugReport(task, profiles, screenshots, llmUsage, taskLogs, taskCheckpoints, verificationResults);
    try {
      await navigator.clipboard.writeText(report);
      setNotice("Debug report copied to clipboard.");
    } catch {
      const textArea = document.createElement("textarea");
      textArea.value = report;
      textArea.style.position = "fixed";
      textArea.style.left = "-9999px";
      document.body.appendChild(textArea);
      textArea.select();
      try {
        document.execCommand("copy");
        setNotice("Debug report copied to clipboard.");
      } catch {
        setError("Failed to copy debug report. Please select and copy the report below.");
        textArea.style.position = "static";
        textArea.style.left = "auto";
        textArea.style.width = "100%";
        textArea.style.height = "200px";
        textArea.readOnly = true;
        const container = document.createElement("div");
        container.className = "card";
        container.appendChild(textArea);
        document.querySelector("section").appendChild(container);
      }
      if (textArea.style.position === "fixed") {
        document.body.removeChild(textArea);
      }
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
  const selectedProvider = llmProviders.find(
    (provider) => provider.id === selectedLlmProvider,
  );
  const llmUnavailable = mappingMode === "llm" && !selectedProvider?.configured;
  const missingRequiredFields = task?.form_fields.filter(needsRequiredInput) || [];
  const runState = getTaskRunState(task, taskCheckpoints);
  const runSummaryItems = getVisibleRunSummaryItems(task);
  const newestJob = getNewestJob(taskJobs);
  const newestJobSummary = newestJob ? summarizeJob(newestJob) : null;
  const jobStatusText = newestJobStatusLine(taskJobs);
  const showWorkflowTimeline = shouldShowWorkflowTimeline();
  const workflowNodes = showWorkflowTimeline && task ? getWorkflowTimeline(task, taskLogs) : [];
  const verificationSummary = summarizeVerificationResults(verificationResults);
  const orderedTrace = sortSpans(workflowTrace);
  const pendingApprovals = approvalRequests.filter((item) => item.status === "PENDING");

  async function resolveApproval(approvalId, action) {
    setBusyAction(`${action}-approval`);
    setError("");
    setNotice("");
    try {
      if (action === "approve") {
        await api.approveApproval(approvalId);
        setNotice("Approval granted.");
      } else {
        await api.rejectApproval(approvalId);
        setNotice("Approval rejected.");
      }
      await refreshTaskData();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusyAction("");
    }
  }
  const primaryDisabled =
    isBusy ||
    !runState.primaryAction ||
    (runState.primaryAction === "prepare" && llmUnavailable) ||
    (runState.primaryAction === "map" && llmUnavailable);
  const primaryLabelByBusyAction = {
    prepare: "Preparing...",
    login: "Waiting for login...",
    map: "Mapping...",
    fill: "Filling...",
    approve: "Submitting...",
  };
  const primaryLabel =
    isBusy && primaryLabelByBusyAction[runState.primaryAction]
      ? primaryLabelByBusyAction[runState.primaryAction]
      : runState.primaryLabel;

  function runPrimaryAction() {
    if (runState.primaryAction === "prepare") {
      analyzeAndReview();
      return;
    }
    if (runState.primaryAction === "login") {
      loginAnalyzeAndMap();
      return;
    }
    if (runState.primaryAction === "review") {
      navigate(`/tasks/${taskId}/review-mapping`);
      return;
    }
    if (runState.primaryAction === "map") {
      setBusyAction("map");
      setError("");
      setNotice("");
      api.mapTaskFields(taskId, getMappingOptions())
        .then(() => {
          refreshTaskData();
          navigate(`/tasks/${taskId}/review-mapping`);
        })
        .catch((requestError) => {
          setError(requestError.message);
          refreshTaskData();
        })
        .finally(() => setBusyAction(""));
      return;
    }
    if (runState.primaryAction === "fill") {
      runAction(
        "fill",
        () => api.fillTask(taskId),
        "Form filled. Review the screenshot before final submission.",
      );
      return;
    }
    if (runState.primaryAction === "approve") {
      runAction(
        "confirm",
        () => api.confirmSubmit(taskId),
        "Form submitted after your approval.",
      );
    }
  }

  return (
    <section>
      <Message type="error">{error}</Message>
      <Message type="success">{notice}</Message>
      {profileUpdates.length > 0 && (
        <div className="card">
          <h3>Profile updates</h3>
          <ul>
            {profileUpdates.map((item) => (
              <li key={`${item.field_id}-${item.profile_key}`}>
                <strong>{item.profile_key}</strong>:{" "}
                {item.previous_value ?? "(empty)"} → {item.new_value}
              </li>
            ))}
          </ul>
        </div>
      )}
      {task && (
        <>
          {showWorkflowTimeline && (
            <div className="card workflow-timeline">
              <h3>Workflow</h3>
              <div className="timeline">
                {workflowNodes.map((node, index) => (
                  <div key={node.id} className="timeline-item">
                    <div className={`timeline-node ${node.state}`}>
                      <span className="timeline-label">{node.label}</span>
                      {node.state === "active" && (
                        <span className="timeline-indicator" />
                      )}
                    </div>
                    {index < workflowNodes.length - 1 && (
                      <div className={`timeline-connector ${node.state === "success" ? "completed" : ""}`} />
                    )}
                    {node.helpText && (
                      <p className="timeline-help">{node.helpText}</p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="card">
              <h3>LLM Usage</h3>
              {llmUsage?.summary ? (
                llmUsage.summary.request_count > 0 ? (
                  <div className="llm-usage-grid">
                    <div className="llm-usage-card">
                      <span>Requests</span>
                      <strong>{llmUsage.summary.request_count}</strong>
                    </div>
                    <div className="llm-usage-card">
                      <span>Total tokens</span>
                      <strong>{llmUsage.summary.total_tokens?.toLocaleString()}</strong>
                    </div>
                    <div className="llm-usage-card">
                      <span>Prompt cache hit rate</span>
                      <strong>{formatCacheHitRate(llmUsage.summary.cache_hit_rate)}</strong>
                    </div>
                    <div className="llm-usage-card">
                      <span>Average latency</span>
                      <strong>{formatLatency(llmUsage.summary.average_latency_ms)}</strong>
                    </div>
                    <div className="llm-usage-card">
                      <span>P95 latency</span>
                      <strong>{formatLatency(llmUsage.summary.p95_latency_ms)}</strong>
                    </div>
                    <div className="llm-usage-card">
                      <span>Fallback count</span>
                      <strong>{llmUsage.summary.fallback_count}</strong>
                    </div>
                    <div className="llm-usage-card">
                      <span>Estimated cost</span>
                      <strong>{formatEstimatedCost(llmUsage.summary.estimated_cost)}</strong>
                    </div>
                  </div>
                ) : (
                  <p>No LLM usage yet.</p>
                )
              ) : (
                <p>LLM usage is not available.</p>
              )}
            </div>

          {orderedTrace.length > 0 && (
            <div className="card">
              <h3>Workflow Trace</h3>
              <ul className="job-list">
                {orderedTrace.map((span) => (
                  <li key={span.id} className="job-item">
                    <div className="job-item-header">
                      <strong>{phaseLabel(span.phase)}</strong>
                      <span className="badge">{spanStatusLabel(span.status)}</span>
                    </div>
                    <div>{span.name}</div>
                    <div className="muted-text">{summarizeSpan(span) || "No summary"}</div>
                    <div className="muted-text">
                      {formatChinaTime(span.created_at)}
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="card">
            <div className="job-item-header">
              <h3>Approval Requests</h3>
              <Link to="/approvals">Open Approval Center</Link>
            </div>
            {approvalRequests.length === 0 ? (
              <p>No approval requests yet.</p>
            ) : (
              <ul className="job-list">
                {approvalRequests.map((approval) => (
                  <li key={approval.id} className="job-item">
                    <div className="job-item-header">
                      <strong>{approval.step_name}</strong>
                      <span className="badge">{approval.status}</span>
                    </div>
                    <div className="muted-text">{approval.reason}</div>
                    <div className="muted-text">
                      {approval.risk_type} · {approval.risk_level}
                    </div>
                    <div className="muted-text">{formatChinaTime(approval.created_at)}</div>
                    {approval.status === "PENDING" && (
                      <div className="agent-review-actions">
                        <button
                          type="button"
                          className="button button-small"
                          onClick={() => resolveApproval(approval.id, "approve")}
                          disabled={Boolean(busyAction)}
                        >
                          Approve
                        </button>
                        <button
                          type="button"
                          className="button button-small button-secondary"
                          onClick={() => resolveApproval(approval.id, "reject")}
                          disabled={Boolean(busyAction)}
                        >
                          Reject
                        </button>
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            )}
            {pendingApprovals.length > 0 && (
              <p className="muted-text">
                Resolve pending approvals here or in the Approval Center before retrying risky actions.
              </p>
            )}
          </div>

          <div className="card">
            <button
              type="button"
              className="button button-secondary"
              onClick={copyDebugReport}
              disabled={loading}
            >
              Copy Debug Report
            </button>
          </div>

          {verificationResults.length > 0 && (
            <div className="card">
              <h3>Verification Results</h3>
              <div className="verification-grid">
                <div className="verification-card verification-verified">
                  <span>Verified</span>
                  <strong>{verificationSummary.verified}</strong>
                </div>
                <div className="verification-card verification-failed">
                  <span>Failed</span>
                  <strong>{verificationSummary.failed}</strong>
                </div>
                <div className="verification-card verification-skipped">
                  <span>Skipped</span>
                  <strong>{verificationSummary.skipped}</strong>
                </div>
              </div>
              {verificationSummary.failed > 0 && (
                <div className="verification-failures">
                  <h4>Failed verifications</h4>
                  <ul>
                    {verificationResults
                      .filter((r) => r.status === "FAILED")
                      .map((r) => (
                        <li key={r.id}>
                          <span className="verification-selector">{r.selector}</span>
                          <span className="verification-reason">
                            {verificationReasonLabel(r.reason)}
                          </span>
                        </li>
                      ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          <div className="card">
            <h3>Agent Reviews</h3>
            <div className="agent-review-actions">
              <button
                className="button button-small"
                type="button"
                onClick={() => runAgentReview("MAPPING_CRITIC")}
                disabled={isBusy || Boolean(runningReview)}
              >
                {runningReview === "MAPPING_CRITIC" ? "Running..." : "Run mapping review"}
              </button>
              <button
                className="button button-small"
                type="button"
                onClick={() => runAgentReview("SAFETY_REVIEW")}
                disabled={isBusy || Boolean(runningReview)}
              >
                {runningReview === "SAFETY_REVIEW" ? "Running..." : "Run safety review"}
              </button>
              <button
                className="button button-small"
                type="button"
                onClick={() => runAgentReview("EXECUTION_VERIFICATION")}
                disabled={isBusy || Boolean(runningReview)}
              >
                {runningReview === "EXECUTION_VERIFICATION" ? "Running..." : "Run verification review"}
              </button>
            </div>
            {agentReviews.length > 0 && (
              <div className="agent-review-list">
                {Object.entries(groupReviewsByRole(agentReviews)).map(([role, reviews]) => {
                  const latest = getLatestReview(reviews);
                  const itemsSummary = summarizeReviewItems(latest);
                  return (
                    <article key={role} className="agent-review-card">
                      <div className="agent-review-header">
                        <span className="agent-review-role">{roleLabel(role)}</span>
                        <span className={`agent-review-decision agent-review-decision-${latest.decision.toLowerCase()}`}>
                          {decisionLabel(latest.decision)}
                        </span>
                      </div>
                      {latest.output?.summary && (
                        <p className="agent-review-summary">{latest.output.summary}</p>
                      )}
                      {itemsSummary.total > 0 && (
                        <p className="agent-review-item-count">
                          {itemsSummary.total} item{itemsSummary.total > 1 ? "s" : ""}
                          {itemsSummary.issues > 0 && ` (${itemsSummary.issues} issue${itemsSummary.issues > 1 ? "s" : ""})`}
                        </p>
                      )}
                    </article>
                  );
                })}
              </div>
            )}
          </div>

          <div className="page-heading">
            <div>
              <p className="eyebrow">Task #{task.id}</p>
              <h2>Agent Run</h2>
              <p className="break-word">{task.url}</p>
            </div>
            <span className="badge badge-large">{runState.statusLabel}</span>
          </div>

          {task.status === "LOGIN_REQUIRED" && (
            <div className="message message-warning">
              This site requires login before the form can be extracted. Log in
              in the browser window, then close it to continue.
            </div>
          )}

          <article className="card run-panel">
            <div className="run-panel-header">
              <div>
                <p className="eyebrow">Current result</p>
                <h3>{runState.statusLabel}</h3>
                <p>{runState.description}</p>
              </div>
              {runState.primaryAction && (
                <button
                  className="button"
                  type="button"
                  onClick={runPrimaryAction}
                  disabled={primaryDisabled}
                >
                  {primaryLabel}
                </button>
              )}
            </div>

            <div className="run-summary-grid" aria-label="Task run summary">
              {runSummaryItems.map((item) => (
                <div key={item.key}>
                  <strong>{item.value}</strong>
                  <span>{item.label}</span>
                </div>
              ))}
            </div>

            <dl className="detail-list">
              <div>
                <dt>Raw status</dt>
                <dd>{task.status}</dd>
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

            {(task.status === "CREATED" ||
              task.status === "FAILED" ||
              task.status === "LOGIN_REQUIRED") && (
              <LlmMappingControls
                mode={mappingMode}
                onModeChange={setMappingMode}
                provider={selectedLlmProvider}
                onProviderChange={updateSelectedLlmProvider}
                providers={llmProviders}
                disabled={isBusy}
              />
            )}

            {(task.status === "READY_TO_FILL" ||
              task.status === "WAITING_APPROVAL" ||
              task.status === "COMPLETED") && (
              <Link className="text-button" to={`/tasks/${task.id}/review-mapping`}>
                Review mapped values
              </Link>
            )}
          </article>

          {taskJobs.length > 0 && newestJobSummary && (
            <div className="card">
              <h3>Background job</h3>
              <dl className="detail-list">
                <div>
                  <dt>Job type</dt>
                  <dd>{newestJobSummary.typeLabel}</dd>
                </div>
                <div>
                  <dt>Status</dt>
                  <dd>
                    <span className={`badge badge-${newestJobSummary.statusClass}`}>
                      {newestJobSummary.statusLabel}
                    </span>
                  </dd>
                </div>
                <div>
                  <dt>Attempts</dt>
                  <dd>{newestJobSummary.attempts} / {newestJobSummary.maxAttempts}</dd>
                </div>
                {newestJobSummary.error && (
                  <div>
                    <dt>Last error</dt>
                    <dd>{newestJobSummary.error}</dd>
                  </div>
                )}
              </dl>
              <p className="break-word">{jobStatusText}</p>
            </div>
          )}

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
                      <span>{formatChinaTime(screenshot.created_at)}</span>
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
