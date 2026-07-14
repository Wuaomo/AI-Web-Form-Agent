import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useNavigate } from "react-router-dom";

import { api } from "../api";
import LlmMappingControls from "../components/LlmMappingControls";
import {
  getSavedLlmProvider,
  saveLlmProvider,
} from "../llmProviderPreference";
import Message from "../components/Message";
import {
  buildReviewGroups,
  computeAttentionSummary,
  fieldDisplayName,
  formatConfidence,
  formatMappingSummary,
  formatSourceSuggestion,
  getFieldChoiceOptions,
  getSourceSuggestionsByFieldId,
  hasFieldChoiceOptions,
  isReviewableField,
  needsMappingReview,
  needsRequiredInput,
  profileKeys,
  shouldShowAdvancedFieldDetails,
  shouldShowMappingSource,
  shouldShowProfileMemoryControl,
  valueControlLabel,
} from "../reviewMappingPresentation";
import {
  decisionLabel,
  roleLabel,
  getLatestReview,
  summarizeReviewItems,
  groupReviewsByRole,
} from "../agentReviewPresentation";

const CUSTOM_CHOICE_VALUE = "__custom__";

function checkboxControlValue(value) {
  const normalizedValue = (value || "").toLowerCase();
  if (["1", "true", "yes", "on"].includes(normalizedValue)) {
    return "true";
  }
  if (["0", "false", "no", "off"].includes(normalizedValue)) {
    return "false";
  }
  return "";
}

function ReviewMapping() {
  const { taskId } = useParams();
  const navigate = useNavigate();
  const [fields, setFields] = useState([]);
  const [llmProviders, setLlmProviders] = useState([]);
  const [mappingMode, setMappingMode] = useState("llm");
  const [selectedLlmProvider, setSelectedLlmProvider] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [customChoiceFields, setCustomChoiceFields] = useState({});
  const [fieldUpdateCount, setFieldUpdateCount] = useState(0);
  const [agentReviews, setAgentReviews] = useState([]);
  const [runningReview, setRunningReview] = useState(null);
  const [taskCheckpoints, setTaskCheckpoints] = useState([]);
  const agentReviewInFlight = useRef(false);
  const pendingValueUpdateTimers = useRef({});
  const pendingValueUpdates = useRef({});
  const pendingPolicyUpdateTimers = useRef({});
  const pendingPolicyUpdates = useRef({});
  const inFlightFieldUpdates = useRef(new Set());

  const loadFields = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [fieldItems, providerItems, reviewItems, checkpointItems] = await Promise.all([
        api.listTaskFields(taskId),
        api.listLlmProviders(),
        api.getTaskAgentReviews(taskId).catch(() => []),
        api.listTaskCheckpoints(taskId).catch(() => []),
      ]);
      setFields(fieldItems);
      setLlmProviders(providerItems);
      setAgentReviews(reviewItems);
      setTaskCheckpoints(checkpointItems);
      setSelectedLlmProvider(getSavedLlmProvider(providerItems));
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }, [taskId]);

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

  useEffect(() => {
    loadFields();
  }, [loadFields]);

  useEffect(() => {
    return () => {
      Object.values(pendingValueUpdateTimers.current).forEach((timerId) =>
        clearTimeout(timerId),
      );
      pendingValueUpdateTimers.current = {};
      pendingValueUpdates.current = {};
      Object.values(pendingPolicyUpdateTimers.current).forEach((timerId) =>
        clearTimeout(timerId),
      );
      pendingPolicyUpdateTimers.current = {};
      pendingPolicyUpdates.current = {};
    };
  }, []);

  async function generateMappings() {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      setFields(
        await api.mapTaskFields(taskId, {
          mode: mappingMode,
          provider: mappingMode === "llm" ? selectedLlmProvider : undefined,
        }),
      );
      setTaskCheckpoints(await api.listTaskCheckpoints(taskId).catch(() => []));
      setNotice("Agent mappings generated.");
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  }

  function updateSelectedLlmProvider(provider) {
    setSelectedLlmProvider(provider);
    saveLlmProvider(provider);
  }

  async function updateField(fieldId, changes) {
    setError("");
    setFieldUpdateCount((count) => count + 1);

    const request = api.updateTaskField(taskId, fieldId, changes);
    inFlightFieldUpdates.current.add(request);

    try {
      const updated = await request;
      setFields((current) =>
        current.map((field) => (field.id === updated.id ? updated : field)),
      );
      return updated;
    } catch (requestError) {
      setError(requestError.message);
      return null;
    } finally {
      inFlightFieldUpdates.current.delete(request);
      setFieldUpdateCount((count) => Math.max(count - 1, 0));
    }
  }

  function stageFieldValue(fieldId, mappedValue) {
    setFields((current) =>
      current.map((item) =>
        item.id === fieldId ? { ...item, mapped_value: mappedValue } : item,
      ),
    );
  }

  function scheduleFieldValueUpdate(fieldId, mappedValue) {
    pendingValueUpdates.current[fieldId] = mappedValue;
    const existingTimer = pendingValueUpdateTimers.current[fieldId];
    if (existingTimer) {
      clearTimeout(existingTimer);
    }
    pendingValueUpdateTimers.current[fieldId] = setTimeout(() => {
      delete pendingValueUpdateTimers.current[fieldId];
      const pendingValue = pendingValueUpdates.current[fieldId];
      delete pendingValueUpdates.current[fieldId];
      updateField(fieldId, { mapped_value: pendingValue || null });
    }, 250);
  }

  function schedulePolicyUpdate(fieldId, policy) {
    pendingPolicyUpdates.current[fieldId] = policy;
    const existingTimer = pendingPolicyUpdateTimers.current[fieldId];
    if (existingTimer) {
      clearTimeout(existingTimer);
    }
    pendingPolicyUpdateTimers.current[fieldId] = setTimeout(() => {
      delete pendingPolicyUpdateTimers.current[fieldId];
      const pendingPolicy = pendingPolicyUpdates.current[fieldId];
      delete pendingPolicyUpdates.current[fieldId];
      updateField(fieldId, { profile_memory_policy: pendingPolicy });
    }, 250);
  }

  async function flushPendingValueUpdates() {
    const entries = Object.entries(pendingValueUpdates.current);
    Object.values(pendingValueUpdateTimers.current).forEach((timerId) =>
      clearTimeout(timerId),
    );
    pendingValueUpdateTimers.current = {};
    pendingValueUpdates.current = {};

    if (entries.length === 0) {
      return true;
    }

    const results = await Promise.all(
      entries.map(([fieldId, mappedValue]) =>
        updateField(Number(fieldId), { mapped_value: mappedValue || null }),
      ),
    );
    return results.every(Boolean);
  }

  async function flushPendingPolicyUpdates() {
    const entries = Object.entries(pendingPolicyUpdates.current);
    Object.values(pendingPolicyUpdateTimers.current).forEach((timerId) =>
      clearTimeout(timerId),
    );
    pendingPolicyUpdateTimers.current = {};
    pendingPolicyUpdates.current = {};

    if (entries.length === 0) {
      return true;
    }

    const results = await Promise.all(
      entries.map(([fieldId, policy]) =>
        updateField(Number(fieldId), { profile_memory_policy: policy }),
      ),
    );
    return results.every(Boolean);
  }

  async function flushInFlightFieldUpdates() {
    const updates = Array.from(inFlightFieldUpdates.current);
    if (updates.length === 0) {
      return true;
    }

    const results = await Promise.allSettled(updates);
    return results.every((result) => result.status === "fulfilled");
  }

  function fieldUsesCustomChoice(field) {
    if (!hasFieldChoiceOptions(field)) {
      return false;
    }
    if (customChoiceFields[field.id]) {
      return true;
    }
    if (!field.mapped_value) {
      return false;
    }
    return !getFieldChoiceOptions(field).some(
      (option) => option.value === field.mapped_value,
    );
  }

  function updateCustomChoiceMode(fieldId, enabled) {
    setCustomChoiceFields((current) => ({ ...current, [fieldId]: enabled }));
  }

  function renderValueControl(field, { showLabel = true } = {}) {
    const fieldType = (field.field_type || "").toLowerCase();
    const label = valueControlLabel(field);

    if (fieldType === "checkbox") {
      const control = (
          <select
            aria-label={`${label} for ${fieldDisplayName(field)}`}
            value={checkboxControlValue(field.mapped_value)}
            onChange={(event) => {
              const mappedValue = event.target.value || null;
              stageFieldValue(field.id, mappedValue);
              updateField(field.id, { mapped_value: mappedValue });
            }}
          >
            <option value="">Not chosen</option>
            <option value="true">Checked</option>
            <option value="false">Unchecked</option>
          </select>
      );
      return showLabel ? <label>{label}{control}</label> : control;
    }

    if (hasFieldChoiceOptions(field)) {
      const usesCustomChoice = fieldUsesCustomChoice(field);
      const control = (
        <div className="field-value-stack">
          <select
            aria-label={`${label} for ${fieldDisplayName(field)}`}
            value={usesCustomChoice ? CUSTOM_CHOICE_VALUE : field.mapped_value || ""}
            onChange={(event) => {
              if (event.target.value === CUSTOM_CHOICE_VALUE) {
                updateCustomChoiceMode(field.id, true);
                stageFieldValue(field.id, "");
                return;
              }
              updateCustomChoiceMode(field.id, false);
              const mappedValue = event.target.value || null;
              stageFieldValue(field.id, mappedValue);
              updateField(field.id, { mapped_value: mappedValue });
            }}
          >
            <option value="">Not chosen</option>
            {getFieldChoiceOptions(field).map((option) => (
              <option key={`${option.label}-${option.value}`} value={option.value}>
                {option.label}
              </option>
            ))}
            <option value={CUSTOM_CHOICE_VALUE}>Custom...</option>
          </select>
          {usesCustomChoice && (
            <input
              aria-label={`Custom ${label.toLowerCase()} for ${fieldDisplayName(field)}`}
              value={field.mapped_value || ""}
              onChange={(event) => {
                stageFieldValue(field.id, event.target.value);
                scheduleFieldValueUpdate(field.id, event.target.value);
              }}
              onBlur={(event) =>
                updateField(field.id, {
                  mapped_value: event.target.value || null,
                })
              }
            />
          )}
        </div>
      );
      return showLabel ? <label>{label}{control}</label> : control;
    }

    const control = (
        <input
          aria-label={`${label} for ${fieldDisplayName(field)}`}
          value={field.mapped_value || ""}
          onChange={(event) => {
            stageFieldValue(field.id, event.target.value);
            scheduleFieldValueUpdate(field.id, event.target.value);
          }}
          onBlur={(event) =>
            updateField(field.id, {
              mapped_value: event.target.value || null,
            })
          }
        />
    );
    return showLabel ? <label>{label}{control}</label> : control;
  }

  function renderSourceControl(field) {
    return (
      <label>
        Use source
        <select
          aria-label={`Source for ${fieldDisplayName(field)}`}
          value={field.mapped_profile_key || ""}
          onChange={(event) =>
            updateField(field.id, {
              mapped_profile_key: event.target.value || null,
            })
          }
        >
          <option value="">Manual / not mapped</option>
          {profileKeys.map((key) => (
            <option key={key} value={key}>
              {key}
            </option>
          ))}
        </select>
      </label>
    );
  }

  async function confirmMapping() {
    if (requiredMissing.length > 0) {
      setError("Please enter values for all required fields before confirming.");
      return;
    }

    setBusy(true);
    setError("");
    try {
      const flushedValues = await flushPendingValueUpdates();
      if (!flushedValues) {
        return;
      }
      const flushedPolicies = await flushPendingPolicyUpdates();
      if (!flushedPolicies) {
        return;
      }
      const flushedFieldUpdates = await flushInFlightFieldUpdates();
      if (!flushedFieldUpdates) {
        setError("Please wait for field updates to finish before confirming.");
        return;
      }
      const result = await api.confirmMapping(taskId);
      navigate(`/tasks/${taskId}`, {
        state: {
          notice: "Mapping confirmed. Ready to fill the form.",
          profileUpdates: result?.profile_updates || [],
          profileSkipped: result?.profile_skipped || [],
        },
      });
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  }

  const selectedProvider = llmProviders.find(
    (provider) => provider.id === selectedLlmProvider,
  );
  const llmUnavailable = mappingMode === "llm" && !selectedProvider?.configured;
  const { requiredMissing, lowConfidence, unmapped } = computeAttentionSummary(fields);
  const reviewGroups = buildReviewGroups(fields);
  const showMappingSource = shouldShowMappingSource();
  const showAdvancedFieldDetails = shouldShowAdvancedFieldDetails();
  const showProfileMemoryControl = shouldShowProfileMemoryControl();
  const sourceSuggestionsByFieldId = getSourceSuggestionsByFieldId(taskCheckpoints);

  return (
    <section>
      <div className="page-heading">
        <div>
          <p className="eyebrow">Run #{taskId}</p>
          <h2>Review Mapping</h2>
          <p>Review what the agent will enter or select before filling this workflow run.</p>
        </div>
        <Link to={`/tasks/${taskId}`}>Back to run</Link>
      </div>

      <Message type="error">{error}</Message>
      <Message type="success">{notice}</Message>

      <LlmMappingControls
        mode={mappingMode}
        onModeChange={setMappingMode}
        provider={selectedLlmProvider}
        onProviderChange={updateSelectedLlmProvider}
        providers={llmProviders}
        disabled={busy}
      />

      {requiredMissing.length > 0 || lowConfidence.length > 0 || unmapped.length > 0 ? (
        <div className="attention-summary">
          <h3>Items requiring attention</h3>
          <div className="attention-summary-list">
            {requiredMissing.length > 0 && (
              <details className="attention-item attention-item-warning">
                <summary>
                  Required missing: {requiredMissing.length}
                </summary>
                <ul>
                  {requiredMissing.map((field) => (
                    <li key={field.id}>{fieldDisplayName(field)}</li>
                  ))}
                </ul>
              </details>
            )}
            {lowConfidence.length > 0 && (
              <details className="attention-item attention-item-info">
                <summary>
                  Low confidence: {lowConfidence.length}
                </summary>
                <ul>
                  {lowConfidence.map((field) => (
                    <li key={field.id}>{fieldDisplayName(field)}</li>
                  ))}
                </ul>
              </details>
            )}
            {unmapped.length > 0 && (
              <details className="attention-item attention-item-muted">
                <summary>
                  Unmapped: {unmapped.length}
                </summary>
                <ul>
                  {unmapped.map((field) => (
                    <li key={field.id}>{fieldDisplayName(field)}</li>
                  ))}
                </ul>
              </details>
            )}
          </div>
        </div>
      ) : null}

      <div className="button-row">
        <button
          className="button"
          type="button"
          onClick={generateMappings}
          disabled={busy || llmUnavailable}
        >
          Generate mappings
        </button>
        <button
          className="button button-secondary"
          type="button"
          onClick={confirmMapping}
          disabled={busy || fieldUpdateCount > 0 || fields.length === 0 || requiredMissing.length > 0}
        >
          Confirm mapping
        </button>
      </div>

      <section className="agent-reviews">
        <h3>Agent Reviews</h3>
        <div className="agent-review-actions">
          <button
            className="button button-small"
            type="button"
            onClick={() => runAgentReview("MAPPING_CRITIC")}
            disabled={busy || Boolean(runningReview)}
          >
            {runningReview === "MAPPING_CRITIC" ? "Running..." : "Run mapping review"}
          </button>
          <button
            className="button button-small"
            type="button"
            onClick={() => runAgentReview("SAFETY_REVIEW")}
            disabled={busy || Boolean(runningReview)}
          >
            {runningReview === "SAFETY_REVIEW" ? "Running..." : "Run safety review"}
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
      </section>

      {loading ? (
        <p>Loading fields...</p>
      ) : fields.length === 0 ? (
        <div className="card empty-state">
          <p>No fields found. Create the run again or check the run logs.</p>
        </div>
      ) : reviewGroups.length === 0 ? (
        <div className="card empty-state">
          <p>
            No reviewable fields found. Create the run again or check the run
            logs.
          </p>
        </div>
      ) : (
        <div className="review-form">
          {reviewGroups.map((group) => (
            <section className="review-form-section" key={group.title}>
              <div className="review-form-heading">
                <h3>{group.title}</h3>
                <span className="badge">{group.fields.length} fields</span>
              </div>

              <div className="review-field-list">
                {group.fields.map((field) => (
                  <article
                    className={`review-form-row${
                      needsMappingReview(field) ? " review-form-row-needs-review" : ""
                    }`}
                    key={field.id}
                  >
                    <div className="review-form-input">
                      <label className="review-field-control">
                        <span className="review-field-label">
                          <span>{fieldDisplayName(field)}</span>
                          {field.required && <span className="required">*</span>}
                        </span>
                        {renderValueControl(field, { showLabel: false })}
                      </label>
                      {showMappingSource && (
                        <p className="review-field-source">
                          {formatMappingSummary(field)} ·{" "}
                          {formatConfidence(field.confidence)}
                        </p>
                      )}
                      {sourceSuggestionsByFieldId.has(field.id) && (
                        <p className="review-field-source">
                          {formatSourceSuggestion(sourceSuggestionsByFieldId.get(field.id))}
                        </p>
                      )}
                      {showAdvancedFieldDetails && field.element_ref && (
                        <details className="technical-details review-field-details">
                          <summary>Field details</summary>
                          <dl>
                            <div>
                              <dt>Reference</dt>
                              <dd>{field.element_ref}</dd>
                            </div>
                          </dl>
                        </details>
                      )}
                      {showProfileMemoryControl && isReviewableField(field) && (
                        <label className="profile-memory-policy">
                          Memory:
                          <select
                            value={field.profile_memory_policy || "auto"}
                            onChange={(event) =>
                              schedulePolicyUpdate(field.id, event.target.value)
                            }
                          >
                            <option value="auto">Auto</option>
                            <option value="do_not_save">Do not save</option>
                            <option value="force_save">Force save</option>
                          </select>
                        </label>
                      )}
                    </div>

                    {needsMappingReview(field) && (
                      <aside className="review-field-assist">
                        <div className="review-field-assist-heading">
                          <strong>
                            {needsRequiredInput(field)
                              ? "Needs a value"
                              : "Check this match"}
                          </strong>
                          <span>{formatConfidence(field.confidence)}</span>
                        </div>
                        <p>
                          {needsRequiredInput(field)
                            ? "This required field is empty."
                            : "The agent is less confident here."}
                        </p>
                        {renderSourceControl(field)}
                      </aside>
                    )}
                  </article>
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </section>
  );
}

export default ReviewMapping;
