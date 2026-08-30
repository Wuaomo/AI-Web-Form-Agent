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
  getLoginRequiredSummary,
  getRunFailureSummary,
  getTaskRunState,
  getVisibleRunSummaryItems,
  shouldOpenAdvancedByDefault,
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
  presentAgentStep,
  hasFailedSteps,
  hasPendingApproval,
} from "../agentStepPresentation";
import { buildPageIntakeBrief } from "../pageIntakePresentation";
import {
  buildTraceSummary,
  getVisibleTraceSpans,
  phaseLabel,
  shouldShowTraceExpansion,
  sortSpans,
  spanStatusLabel,
  summarizeSpan,
  traceJsonText,
} from "../workflowTracePresentation";
import {
  getWorkflowPlanSteps,
  workflowPlanApprovalLabel,
} from "../workflowPlanPresentation";
import {
  buildRunCockpitSummary,
  getRunCockpitPlanSteps,
  getRunCockpitToolCalls,
  getRunCockpitVerificationDetails,
  shouldShowRunCockpit,
} from "../runCockpitPresentation";
import { getExtractionData, getSummaryData } from "../webExtractionPresentation";
import {
  pendingApprovalRequests,
  shouldShowApprovalsOnMain,
} from "../taskDetailPresentation";

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
  const [taskPlan, setTaskPlan] = useState(null);
  const [approvalRequests, setApprovalRequests] = useState([]);
  const [workflowRuntime, setWorkflowRuntime] = useState(null);
  const [governedRuntime, setGovernedRuntime] = useState(null);
  const [runningReview, setRunningReview] = useState(null);
  const [showAllFailedSpans, setShowAllFailedSpans] = useState(false);
  const [summaryCopied, setSummaryCopied] = useState(false);
  const [agentSteps, setAgentSteps] = useState([]);
  const agentReviewInFlight = useRef(false);

  async function getTaskPlanOrNull(currentTaskId) {
    try {
      return await api.getTaskPlan(currentTaskId);
    } catch (requestError) {
      if (requestError.status === 404) {
        return null;
      }
      throw requestError;
    }
  }

  async function getWorkflowRuntimeOrNull(currentTaskId, workflowType) {
    if (workflowType !== "security_questionnaire") {
      return null;
    }
    try {
      return await api.getWorkflowState(currentTaskId);
    } catch (requestError) {
      if (requestError.status === 404) {
        return null;
      }
      throw requestError;
    }
  }

  async function getGovernedWorkflowRuntimeOrNull(currentTaskId) {
    try {
      return await api.getGovernedWorkflowState(currentTaskId);
    } catch (requestError) {
      if (requestError.status === 404) {
        return null;
      }
      throw requestError;
    }
  }

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
      getTaskPlanOrNull(taskId),
      api.listApprovals({ taskId }).catch(() => []),
      api.getTaskAgentSteps(taskId).catch(() => []),
      getGovernedWorkflowRuntimeOrNull(taskId),
    ])
      .then(async ([taskResult, screenshotItems, profileItems, providerItems, logItems, usageResult, checkpointItems, jobItems, verificationItems, reviewItems, traceItems, planResult, approvalItems, agentStepItems, governedRuntimeState]) => {
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
        setTaskPlan(planResult);
        setApprovalRequests(approvalItems);
        setAgentSteps(agentStepItems);
        setGovernedRuntime(governedRuntimeState);
        setSelectedLlmProvider(getSavedLlmProvider(providerItems));

        const runtimeState = await getWorkflowRuntimeOrNull(
          taskId,
          taskResult.workflow_type,
        );
        setWorkflowRuntime(runtimeState);
      })
      .catch((requestError) => setError(requestError.message))
      .finally(() => setLoading(false));
  }, [taskId]);

  useEffect(() => {
    setShowAllFailedSpans(false);
  }, [taskId]);

  async function refreshTaskData(nextTask = null) {
    const [taskResult, screenshotItems, logItems, usageResult, checkpointItems, jobItems, verificationItems, reviewItems, traceItems, planResult, approvalItems, agentStepItems, governedRuntimeState] = await Promise.all([
      nextTask ? Promise.resolve(nextTask) : api.getTask(taskId),
      api.listTaskScreenshots(taskId),
      api.listTaskLogs(taskId),
      api.getTaskLlmUsage(taskId).catch(() => null),
      api.listTaskCheckpoints(taskId).catch(() => []),
      api.listTaskJobs(taskId).catch(() => []),
      api.getTaskVerificationResults(taskId).catch(() => []),
      api.getTaskAgentReviews(taskId).catch(() => []),
      api.getTaskTrace(taskId).catch(() => []),
      getTaskPlanOrNull(taskId),
      api.listApprovals({ taskId }).catch(() => []),
      api.getTaskAgentSteps(taskId).catch(() => []),
      getGovernedWorkflowRuntimeOrNull(taskId),
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
    setTaskPlan(planResult);
    setApprovalRequests(approvalItems);
    setAgentSteps(agentStepItems);
    setGovernedRuntime(governedRuntimeState);
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

  async function startWorkflowRun() {
    setBusyAction("start-runtime");
    setError("");
    setNotice("");
    try {
      const runtimeState = await api.startWorkflow(taskId);
      setWorkflowRuntime(runtimeState);
      setNotice("Workflow started. Review suggestions before filling.");
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusyAction("");
    }
  }

  async function startGovernedWorkflowRun() {
    setBusyAction("start-governed-runtime");
    setError("");
    setNotice("");
    try {
      const runtimeState = await api.startGovernedWorkflow(taskId, {
        plannerMode: "deterministic",
      });
      setGovernedRuntime(runtimeState);
      await refreshTaskData();
      setNotice("Governed runtime started.");
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusyAction("");
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

  async function copyTraceJson() {
    try {
      await navigator.clipboard.writeText(traceJsonText(workflowTrace));
      setNotice("Trace JSON copied to clipboard.");
    } catch {
      setError("Failed to copy trace JSON.");
    }
  }

  async function copyResearchSummary() {
    if (!summaryData) return;
    const copyableText = `# Research Summary\n\n${summaryData.summary}\n\n## Key Requirements\n${summaryData.key_requirements.map((r, i) => `${i + 1}. ${r}`).join("\n")}\n\n## Action Checklist\n${summaryData.action_checklist.map((c, i) => `${i + 1}. ${c}`).join("\n")}\n\n## Risks / Missing Information\n${summaryData.risks.map((r, i) => `${i + 1}. ${r}`).join("\n")}`;
    try {
      await navigator.clipboard.writeText(copyableText);
      setSummaryCopied(true);
      setTimeout(() => setSummaryCopied(false), 2000);
    } catch {
      setError("Failed to copy research summary.");
    }
  }

  function updateSelectedLlmProvider(provider) {
    setSelectedLlmProvider(provider);
    saveLlmProvider(provider);
  }

  if (loading) {
    return <p>Loading workflow run...</p>;
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
  const traceSummary = buildTraceSummary(orderedTrace);
  const visibleFailedSpans = getVisibleTraceSpans(orderedTrace, showAllFailedSpans);
  const canExpandTrace = shouldShowTraceExpansion(orderedTrace);
  const failureSummary = getRunFailureSummary(task, taskCheckpoints, orderedTrace);
  const loginRequiredSummary = getLoginRequiredSummary(task);
  const attentionSummary = failureSummary || loginRequiredSummary;
  const plannedSteps = getWorkflowPlanSteps(taskPlan);
  const pendingApprovals = pendingApprovalRequests(approvalRequests);
  const showMainApprovals = shouldShowApprovalsOnMain(approvalRequests);
  const extractionData = getExtractionData(taskCheckpoints);
  const summaryData = getSummaryData(taskCheckpoints);
  const preflightBrief = buildPageIntakeBrief(taskCheckpoints);
  const showRunCockpit = shouldShowRunCockpit(governedRuntime);
  const runCockpitSummary = buildRunCockpitSummary(governedRuntime);
  const runCockpitPlanSteps = getRunCockpitPlanSteps(governedRuntime);
  const runCockpitToolCalls = getRunCockpitToolCalls(governedRuntime);
  const runCockpitVerificationDetails =
    getRunCockpitVerificationDetails(governedRuntime);

  async function resolveApproval(approval, action) {
    setBusyAction(`${action}-approval`);
    setError("");
    setNotice("");
    try {
      if (action === "approve") {
        await api.approveApproval(approval.id);
        if (approval.step_name.startsWith("memory_write:")) {
          setNotice("Approval granted. Re-confirm mapping to apply the approved profile write.");
        } else if (approval.step_name.startsWith("fill_field:")) {
          setNotice("Approval granted. Retry fill to continue.");
        } else if (approval.step_name === "submit_form") {
          setNotice("Approval granted. Retry submit to continue.");
        } else {
          setNotice("Approval granted.");
        }
      } else {
        await api.rejectApproval(approval.id);
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
    fill: "Applying...",
    approve: "Submitting...",
  };
  const primaryLabel =
    isBusy && primaryLabelByBusyAction[runState.primaryAction]
      ? primaryLabelByBusyAction[runState.primaryAction]
      : runState.primaryLabel;

  function nodeLabel(nodeId) {
    const labels = {
      start: "Starting",
      analyze_page: "Analyzing page",
      extract_questions: "Extracting questions",
      retrieve_reviewed_memory: "Retrieving memory",
      retrieve_policy_sources: "Retrieving policy sources",
      suggest_answers: "Suggesting answers",
      policy_check: "Checking policy",
      apply_review_decision: "Review pending",
      fill_browser: "Filling browser",
      verify_result: "Verifying result",
      finish: "Completed",
      fail: "Failed",
    };
    return labels[nodeId] || nodeId;
  }

  function runtimeDescription(runtime) {
    if (runtime.interrupt_at === "review") {
      return "Suggestions are ready. Review and approve before the agent fills the form.";
    }
    if (runtime.interrupt_at === "submit_approval") {
      return "Form filled and verified. Awaiting your submission approval.";
    }
    if (runtime.status === "COMPLETED") {
      return "Workflow completed successfully.";
    }
    if (runtime.status === "FAILED") {
      return runtime.error || "Workflow failed.";
    }
    return "Workflow is running...";
  }

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
        "Values applied. Review the screenshot before final submission.",
      );
      return;
    }
    if (runState.primaryAction === "approve") {
      runAction(
        "confirm",
        () => api.confirmSubmit(taskId),
        "Submitted after your approval.",
      );
    }
  }

  function renderApprovalRequestsCard(requests, { showEmpty = true } = {}) {
    if (!showEmpty && requests.length === 0) return null;
    return (
      <div className="card">
        <div className="job-item-header">
          <h3>Approval Requests</h3>
          <Link to="/approvals">Open Approval Center</Link>
        </div>
        {requests.length === 0 ? (
          <p>No approval requests yet.</p>
        ) : (
          <ul className="job-list">
            {requests.map((approval) => (
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
                      onClick={() => resolveApproval(approval, "approve")}
                      disabled={Boolean(busyAction)}
                    >
                      Approve
                    </button>
                    <button
                      type="button"
                      className="button button-small button-secondary"
                      onClick={() => resolveApproval(approval, "reject")}
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
        {requests.some((approval) => approval.status === "PENDING") && (
          <p className="muted-text">
            Resolve pending approvals here or in the Approval Center before retrying risky actions.
          </p>
        )}
      </div>
    );
  }

  function renderWorkflowPlanCard() {
    return (
      <div className="card">
        <h3>Workflow Plan</h3>
        {taskPlan ? (
          <>
            <p className="muted-text">{taskPlan.goal}</p>
            <ul className="job-list">
              {plannedSteps.map((step) => (
                <li key={step.step_id} className="job-item">
                  <div className="job-item-header">
                    <strong>{step.step_id}</strong>
                    {workflowPlanApprovalLabel(step) && (
                      <span className="badge">{workflowPlanApprovalLabel(step)}</span>
                    )}
                  </div>
                  <div>{step.tool}</div>
                  <div className="muted-text">{step.reason}</div>
                </li>
              ))}
            </ul>
          </>
        ) : (
          <p>No workflow plan has been created yet.</p>
        )}
      </div>
    );
  }

  function renderAgentStepsCard() {
    if (agentSteps.length === 0) return null;
    return (
      <div className="card">
        <div className="agent-steps-header">
          <h3>Agent Steps</h3>
          {hasFailedSteps(agentSteps) && (
            <span className="badge badge-danger">Failed steps</span>
          )}
          {hasPendingApproval(agentSteps) && (
            <span className="badge badge-warning">Awaiting approval</span>
          )}
        </div>
        <div className="agent-steps-timeline">
          {agentSteps.map((step, index) => {
            const presented = presentAgentStep(step);
            return (
              <div key={step.step_id} className="agent-step">
                <div className="agent-step-line-container">
                  <div className={`agent-step-line ${index === agentSteps.length - 1 ? "last" : ""}`} />
                  <div className={`agent-step-node ${presented.statusClass}`}>
                    <span className="agent-step-status-dot" />
                  </div>
                </div>
                <div className="agent-step-content">
                  <div className="agent-step-header">
                    <div>
                      <strong>{presented.toolLabel}</strong>
                      <span className="muted-text">{step.goal}</span>
                    </div>
                    <span className={`agent-step-status ${presented.statusClass}`}>
                      {presented.statusLabel}
                    </span>
                  </div>
                  {step.output_summary && (
                    <p className="agent-step-result">{step.output_summary}</p>
                  )}
                  {step.error && (
                    <div className="agent-step-error">
                      <strong>Error:</strong> {step.error}
                      {step.recovery_hint && (
                        <p className="agent-step-recovery">
                          <strong>Recovery:</strong> {step.recovery_hint}
                        </p>
                      )}
                    </div>
                  )}
                  {presented.evidenceLabels.length > 0 && (
                    <div className="agent-step-evidence">
                      <span className="muted-text">Evidence:</span>
                      {presented.evidenceLabels.map((label, i) => (
                        <span key={i} className="agent-step-evidence-tag">
                          {label}
                        </span>
                      ))}
                      {step.screenshot_id && (
                        <a
                          href={`${API_BASE_URL}/tasks/${taskId}/screenshots/${step.screenshot_id}`}
                          target="_blank"
                          rel="noreferrer"
                          className="agent-step-screenshot-link"
                        >
                          View screenshot
                        </a>
                      )}
                    </div>
                  )}
                  {presented.startedAtFormatted && (
                    <p className="muted-text agent-step-timestamp">
                      {presented.startedAtFormatted}
                    </p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  function renderRunCockpit() {
    return (
      <div className="runtime-status-panel run-cockpit-panel">
        <div className="runtime-status-header">
          <div>
            <p className="eyebrow">Run Cockpit</p>
            <h3>{showRunCockpit ? runCockpitSummary.status : "Not started"}</h3>
            <p>
              {showRunCockpit
                ? "Generic governed runtime state from the agent graph."
                : "Start the generic governed runtime to inspect plan, tool, governance, and verification state."}
            </p>
          </div>
          <button
            className="button button-secondary"
            type="button"
            onClick={startGovernedWorkflowRun}
            disabled={isBusy}
          >
            {busyAction === "start-governed-runtime"
              ? "Starting..."
              : "Start governed runtime"}
          </button>
        </div>

        {showRunCockpit && (
          <>
            <div className="runtime-summary-grid" aria-label="Run cockpit summary">
              <div>
                <strong>{runCockpitSummary.plannerMode}</strong>
                <span>Planner mode</span>
              </div>
              <div>
                <strong>{runCockpitSummary.currentTool}</strong>
                <span>Current tool call</span>
              </div>
              <div>
                <strong>{runCockpitSummary.governanceDecision}</strong>
                <span>Governance decision</span>
              </div>
              <div>
                <strong>{runCockpitSummary.toolResultCount}</strong>
                <span>Tool results</span>
              </div>
              <div>
                <strong>{runCockpitSummary.verificationSummary}</strong>
                <span>Verification</span>
              </div>
              <div>
                <strong>{runCockpitSummary.error || "None"}</strong>
                <span>Error</span>
              </div>
            </div>

            {runCockpitSummary.governanceReason && (
              <p className="muted-text">{runCockpitSummary.governanceReason}</p>
            )}

            <div className="run-cockpit-plan">
              <h4>Verification evidence</h4>
              {runCockpitVerificationDetails.mismatchCount > 0 ||
              runCockpitVerificationDetails.evidenceItems.length > 0 ? (
                <div className="evidence-list">
                  {runCockpitVerificationDetails.mismatchCount > 0 && (
                    <article className="evidence-item">
                      <strong>
                        {runCockpitVerificationDetails.mismatchCount} mismatch
                        {runCockpitVerificationDetails.mismatchCount > 1 ? "es" : ""}
                      </strong>
                      <ul className="blocked-reasons">
                        {runCockpitVerificationDetails.mismatches.map((mismatch) => (
                          <li key={mismatch}>{mismatch}</li>
                        ))}
                      </ul>
                      {runCockpitVerificationDetails.mismatchCount >
                        runCockpitVerificationDetails.mismatches.length && (
                        <p className="muted-text">
                          ...and{" "}
                          {runCockpitVerificationDetails.mismatchCount -
                            runCockpitVerificationDetails.mismatches.length}{" "}
                          more
                        </p>
                      )}
                    </article>
                  )}
                  {runCockpitVerificationDetails.evidenceItems.map(
                    (evidence, index) => (
                      <article className="evidence-item" key={`${index}-${evidence}`}>
                        <strong>Evidence {index + 1}</strong>
                        <p>{evidence}</p>
                      </article>
                    ),
                  )}
                </div>
              ) : (
                <p className="muted-text">
                  {runCockpitVerificationDetails.statusLabel === "Verified"
                    ? "Verified; no detailed evidence returned."
                    : "No verification evidence recorded yet."}
                </p>
              )}
            </div>

            <div className="run-cockpit-plan">
              <h4>Tool calls</h4>
              {runCockpitToolCalls.length > 0 ? (
                <ul className="job-list">
                  {runCockpitToolCalls.slice(-5).map((call) => (
                    <li key={call.id} className="job-item">
                      <div className="job-item-header">
                        <strong>{call.toolName}</strong>
                        <span className="badge">{call.status}</span>
                      </div>
                      <div className="muted-text">
                        {call.stepId} / {call.governanceDecision}
                      </div>
                      {(call.evidenceCount > 0 ||
                        call.proposalCount > 0 ||
                        call.verificationCandidateCount > 0) && (
                        <div className="muted-text">
                          {call.evidenceCount} evidence / {call.proposalCount} proposals /{" "}
                          {call.verificationCandidateCount} verification candidates
                        </div>
                      )}
                      {call.error && <div className="agent-step-error">{call.error}</div>}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="muted-text">No tool calls recorded yet.</p>
              )}
            </div>

            <div className="run-cockpit-plan">
              <h4>Plan steps</h4>
              {runCockpitPlanSteps.length > 0 ? (
                <ul className="job-list">
                  {runCockpitPlanSteps.map((step) => (
                    <li key={step.id} className="job-item">
                      <div className="job-item-header">
                        <strong>{step.id}</strong>
                        <span className="badge">{step.toolName}</span>
                      </div>
                      {step.reason && <div className="muted-text">{step.reason}</div>}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="muted-text">No plan steps returned.</p>
              )}
            </div>
          </>
        )}
      </div>
    );
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
          <div className="page-heading">
            <div>
              <p className="eyebrow">Run #{task.id}</p>
              <h2>Workflow Run</h2>
              <p className="break-word">{task.url}</p>
            </div>
            <span className="badge badge-large">{runState.statusLabel}</span>
          </div>

          {loginRequiredSummary && (
            <div className="message message-warning">
              {loginRequiredSummary.detail} {loginRequiredSummary.recoveryHint}
            </div>
          )}

          {preflightBrief && (
            <article className="card page-overview-card">
              <div>
                <p className="eyebrow">Preflight brief</p>
                <h3>Page Intake</h3>
                <p className="muted-text">
                  The agent reviewed the page before choosing this workflow.
                </p>
              </div>
              <div className="page-overview-grid">
                <div>
                  <dt>Page type</dt>
                  <dd>{preflightBrief.pageType}</dd>
                </div>
                <div>
                  <dt>Recommended workflow</dt>
                  <dd>{preflightBrief.workflowLabel}</dd>
                </div>
                <div>
                  <dt>Confidence</dt>
                  <dd>{preflightBrief.confidenceText}</dd>
                </div>
              </div>
              <dl className="detail-list">
                <div>
                  <dt>Status</dt>
                  <dd>{preflightBrief.status}</dd>
                </div>
                <div>
                  <dt>Fields found</dt>
                  <dd>{preflightBrief.detectedFieldCount}</dd>
                </div>
              </dl>
              {preflightBrief.riskLabels.length > 0 && (
                <div>
                  <h4>Risks</h4>
                  <div className="risk-list">
                    {preflightBrief.riskLabels.map((label) => (
                      <span key={label} className="badge badge-warning">
                        {label}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {preflightBrief.evidenceItems.length > 0 && (
                <div>
                  <h4>Evidence</h4>
                  <div className="evidence-list">
                    {preflightBrief.evidenceItems.slice(0, 3).map((item, index) => (
                      <div key={index} className="evidence-item">
                        <span className="badge">{item.source}</span>
                        <p className="muted-text">{item.text}</p>
                        <p>{item.reason}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </article>
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

            <div className="run-summary-grid" aria-label="Workflow run summary">
              {runSummaryItems.map((item) => (
                <div key={item.key}>
                  <strong>{item.value}</strong>
                  <span>{item.label}</span>
                </div>
              ))}
            </div>

            {renderRunCockpit()}

            {task.workflow_type === "security_questionnaire" && (
              <div className="runtime-status-panel">
                <div className="runtime-status-header">
                  <p className="eyebrow">Agent workflow</p>
                  <h3>
                    {workflowRuntime
                      ? workflowRuntime.current_node
                        ? nodeLabel(workflowRuntime.current_node)
                        : "Running"
                      : "Not started"}
                  </h3>
                  <p>
                    {workflowRuntime
                      ? runtimeDescription(workflowRuntime)
                      : "Start the agent workflow to analyze the page and suggest answers."}
                  </p>
                </div>
                {!workflowRuntime && (
                  <button
                    className="button"
                    type="button"
                    onClick={startWorkflowRun}
                    disabled={isBusy}
                  >
                    {busyAction === "start-runtime"
                      ? "Starting..."
                      : "Start agent workflow"}
                  </button>
                )}
                {workflowRuntime?.interrupt_at === "review" && (
                  <Link
                    className="button button-secondary"
                    to={`/tasks/${task.id}/review-mapping`}
                  >
                    Review suggestions
                  </Link>
                )}
                {workflowRuntime && (
                  <div className="runtime-summary-grid">
                    <div>
                      <strong>{workflowRuntime.suggestions?.length || 0}</strong>
                      <span>Suggestions</span>
                    </div>
                    <div>
                      <strong>
                        {workflowRuntime.policy_result?.blocked || 0}
                      </strong>
                      <span>Blocked by policy</span>
                    </div>
                    <div>
                      <strong>
                        {workflowRuntime.policy_sources?.length || 0}
                      </strong>
                      <span>Policy sources</span>
                    </div>
                    <div>
                      <strong>
                        {workflowRuntime.memory_hits?.length || 0}
                      </strong>
                      <span>Memory hits</span>
                    </div>
                  </div>
                )}
              </div>
            )}

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
                Review values
              </Link>
            )}
          </article>

          {attentionSummary && (
            <div className="card failure-summary-card">
              <div>
                <p className="eyebrow">Needs attention</p>
                <h3>{attentionSummary.title}</h3>
                <p>{attentionSummary.detail}</p>
                {attentionSummary.evidenceHint && <p>{attentionSummary.evidenceHint}</p>}
                <p>{attentionSummary.recoveryHint}</p>
                <p className="muted-text">{attentionSummary.source}</p>
              </div>
            </div>
          )}

          {showMainApprovals && renderApprovalRequestsCard(pendingApprovals, { showEmpty: false })}

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

          {extractionData && (
            <section className="section-block">
              <div className="section-heading">
                <h3>Extraction Result</h3>
              </div>
              <div className="card">
                {extractionData.title && (
                  <div className="extraction-title">
                    <h4>Page Title</h4>
                    <p>{extractionData.title}</p>
                  </div>
                )}
                {extractionData.headings && extractionData.headings.length > 0 && (
                  <div>
                    <h4>Headings ({extractionData.heading_count})</h4>
                    <ul className="extraction-list">
                      {extractionData.headings.map((heading, index) => (
                        <li key={index}>
                          <span className="badge badge-small">H{heading.level}</span>
                          <span>{heading.text}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {extractionData.links && extractionData.links.length > 0 && (
                  <div>
                    <h4>Links ({extractionData.link_count})</h4>
                    <ul className="extraction-list">
                      {extractionData.links.slice(0, 20).map((link, index) => (
                        <li key={index}>
                          <a href={link.href} target="_blank" rel="noreferrer">
                            {link.text || link.href}
                          </a>
                        </li>
                      ))}
                      {extractionData.links.length > 20 && (
                        <li className="muted-text">...and {extractionData.links.length - 20} more</li>
                      )}
                    </ul>
                  </div>
                )}
                {extractionData.tables && extractionData.tables.length > 0 && (
                  <div>
                    <h4>Tables ({extractionData.table_count})</h4>
                    <ul className="extraction-list">
                      {extractionData.tables.map((table, index) => (
                        <li key={index}>
                          <span>Headers: {table.headers.join(", ") || "none"}</span>
                          <span className="muted-text">{table.row_count} rows</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {extractionData.forms && extractionData.forms.length > 0 && (
                  <div>
                    <h4>Forms ({extractionData.form_count})</h4>
                    <ul className="extraction-list">
                      {extractionData.forms.map((form, index) => (
                        <li key={index}>
                          <span>{form.method || "GET"} {form.action || "(no action)"}</span>
                          <span className="muted-text">{form.field_count} fields</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {extractionData.text_block_count !== undefined && (
                  <div>
                    <h4>Text Blocks</h4>
                    <p>{extractionData.text_block_count} blocks extracted</p>
                  </div>
                )}
                <details className="technical-details">
                  <summary>View raw JSON</summary>
                  <pre className="trace-json-block">{JSON.stringify(extractionData, null, 2)}</pre>
                </details>
              </div>
            </section>
          )}

          {summaryData && (
            <section className="section-block">
              <div className="section-heading">
                <h3>Research Summary</h3>
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={copyResearchSummary}
                >
                  {summaryCopied ? "Copied!" : "Copy Report"}
                </button>
              </div>
              <div className="card">
                {summaryData.summary && (
                  <div>
                    <h4>Summary</h4>
                    <pre className="summary-text">{summaryData.summary}</pre>
                  </div>
                )}
                {summaryData.key_requirements && summaryData.key_requirements.length > 0 && (
                  <div>
                    <h4>Key Requirements</h4>
                    <ul className="extraction-list">
                      {summaryData.key_requirements.map((req, index) => (
                        <li key={index}>{req}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {summaryData.action_checklist && summaryData.action_checklist.length > 0 && (
                  <div>
                    <h4>Action Checklist</h4>
                    <ul className="extraction-list">
                      {summaryData.action_checklist.map((item, index) => (
                        <li key={index}>{item}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {summaryData.risks && summaryData.risks.length > 0 && (
                  <div>
                    <h4>Risks / Missing Information</h4>
                    <ul className="extraction-list">
                      {summaryData.risks.map((risk, index) => (
                        <li key={index} className="text-warning">{risk}</li>
                      ))}
                    </ul>
                  </div>
                )}
                <details className="technical-details">
                  <summary>View raw JSON</summary>
                  <pre className="trace-json-block">{JSON.stringify(summaryData, null, 2)}</pre>
                </details>
              </div>
            </section>
          )}

          <details
            className="advanced-panel"
            open={shouldOpenAdvancedByDefault(task)}
          >
            <summary>Advanced / Debug</summary>
            <div className="advanced-panel-body">
              {renderApprovalRequestsCard(approvalRequests)}
              {renderWorkflowPlanCard()}
              {renderAgentStepsCard()}

              <div className="card">
                <div className="workflow-trace-header">
                  <div>
                    <h3>Workflow Trace</h3>
                    <p className="muted-text">Trace stays compact by default and only expands failed spans.</p>
                  </div>
                  <div className="workflow-trace-actions">
                    <details className="technical-details">
                      <summary>View raw trace JSON</summary>
                      <pre className="trace-json-block">{traceJsonText(workflowTrace)}</pre>
                    </details>
                    <button
                      type="button"
                      className="button button-small button-secondary"
                      onClick={copyTraceJson}
                    >
                      Copy trace JSON
                    </button>
                  </div>
                </div>

                <div className="workflow-trace-summary" aria-label="Workflow trace summary">
                  <div>
                    <strong>{traceSummary.latestStatus}</strong>
                    <span>Latest status</span>
                  </div>
                  <div>
                    <strong>{traceSummary.totalSpanCount}</strong>
                    <span>Total spans</span>
                  </div>
                  <div>
                    <strong>{traceSummary.failedSpanCount}</strong>
                    <span>Failed spans</span>
                  </div>
                  <div>
                    <strong>{traceSummary.lastSpanLabel}</strong>
                    <span>Last phase/name</span>
                  </div>
                </div>

                {visibleFailedSpans.length > 0 ? (
                  <>
                    <ul className="job-list">
                      {visibleFailedSpans.map((span) => (
                        <li key={span.id} className="job-item">
                          <div className="job-item-header">
                            <strong>{phaseLabel(span.phase)}</strong>
                            <span className="badge">{spanStatusLabel(span.status)}</span>
                          </div>
                          <div>{span.name}</div>
                          <div className="muted-text">{summarizeSpan(span) || "No summary"}</div>
                          <div className="muted-text">{formatChinaTime(span.created_at)}</div>
                        </li>
                      ))}
                    </ul>
                    {canExpandTrace && !showAllFailedSpans && (
                      <button
                        type="button"
                        className="text-button"
                        onClick={() => setShowAllFailedSpans(true)}
                      >
                        Show more
                      </button>
                    )}
                  </>
                ) : orderedTrace.length === 0 ? (
                  <p className="muted-text">No trace spans recorded yet.</p>
                ) : null}
              </div>

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

              <div className="card">
                <button
                  type="button"
                  className="button button-secondary"
                  onClick={copyDebugReport}
                  disabled={loading || Boolean(busyAction)}
                >
                  Copy Debug Report
                </button>
              </div>

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
            </div>
          </details>
        </>
      )}
    </section>
  );
}

export default TaskDetail;
