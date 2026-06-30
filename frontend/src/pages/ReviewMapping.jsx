import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { api } from "../api";
import LlmMappingControls from "../components/LlmMappingControls";
import {
  getSavedLlmProvider,
  saveLlmProvider,
} from "../llmProviderPreference";
import Message from "../components/Message";
import {
  buildReviewGroups,
  fieldDisplayName,
  fieldFormTitle,
  fieldHint,
  fieldSectionTitle,
  formatConfidence,
  formatMappingSummary,
  getFieldChoiceOptions,
  hasFieldChoiceOptions,
  needsMappingReview,
  needsRequiredInput,
  profileKeys,
  valueControlLabel,
} from "../reviewMappingPresentation";

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

  const loadFields = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [fieldItems, providerItems] = await Promise.all([
        api.listTaskFields(taskId),
        api.listLlmProviders(),
      ]);
      setFields(fieldItems);
      setLlmProviders(providerItems);
      setSelectedLlmProvider(getSavedLlmProvider(providerItems));
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }, [taskId]);

  useEffect(() => {
    loadFields();
  }, [loadFields]);

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
    try {
      const updated = await api.updateTaskField(taskId, fieldId, changes);
      setFields((current) =>
        current.map((field) => (field.id === updated.id ? updated : field)),
      );
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  function stageFieldValue(fieldId, mappedValue) {
    setFields((current) =>
      current.map((item) =>
        item.id === fieldId ? { ...item, mapped_value: mappedValue } : item,
      ),
    );
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
      const control = (
          <select
            aria-label={`${label} for ${fieldDisplayName(field)}`}
            value={field.mapped_value || ""}
            onChange={(event) => {
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
          </select>
      );
      return showLabel ? <label>{label}{control}</label> : control;
    }

    const control = (
        <input
          aria-label={`${label} for ${fieldDisplayName(field)}`}
          value={field.mapped_value || ""}
          onChange={(event) => stageFieldValue(field.id, event.target.value)}
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
    if (missingRequiredFields.length > 0) {
      setError("Please enter values for all required fields before confirming.");
      return;
    }

    setBusy(true);
    setError("");
    try {
      await api.confirmMapping(taskId);
      navigate(`/tasks/${taskId}`, {
        state: { notice: "Mapping confirmed. Ready to fill the form." },
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
  const missingRequiredFields = fields.filter(needsRequiredInput);
  const reviewGroups = buildReviewGroups(fields);

  return (
    <section>
      <div className="page-heading">
        <div>
          <p className="eyebrow">Task #{taskId}</p>
          <h2>Review Mapping</h2>
          <p>Review what the agent will enter or select before filling the form.</p>
        </div>
        <Link to={`/tasks/${taskId}`}>Back to task</Link>
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

      {missingRequiredFields.length > 0 && (
        <div className="message message-warning">
          Required info still needed:{" "}
          {missingRequiredFields.map(fieldDisplayName).join(", ")}.
        </div>
      )}

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
          disabled={busy || fields.length === 0 || missingRequiredFields.length > 0}
        >
          Confirm mapping
        </button>
      </div>

      {loading ? (
        <p>Loading fields...</p>
      ) : fields.length === 0 ? (
        <div className="card empty-state">
          <p>No fields found. Create the task again or check the task logs.</p>
        </div>
      ) : reviewGroups.length === 0 ? (
        <div className="card empty-state">
          <p>
            No reviewable fields found. Create the task again or check the task
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
                      <p className="review-field-source">
                        {formatMappingSummary(field)} ·{" "}
                        {formatConfidence(field.confidence)}
                      </p>
                      {fieldHint(field) && <p className="field-meta">{fieldHint(field)}</p>}
                      {field.current_value && (
                        <p className="field-meta">Current: {field.current_value}</p>
                      )}
                      {(fieldFormTitle(field) ||
                        fieldSectionTitle(field) ||
                        field.element_ref) && (
                        <details className="technical-details review-field-details">
                          <summary>Field details</summary>
                          <dl>
                            {fieldFormTitle(field) && (
                              <div>
                                <dt>Form</dt>
                                <dd>{fieldFormTitle(field)}</dd>
                              </div>
                            )}
                            {fieldSectionTitle(field) && (
                              <div>
                                <dt>Section</dt>
                                <dd>{fieldSectionTitle(field)}</dd>
                              </div>
                            )}
                            {field.element_ref && (
                              <div>
                                <dt>Reference</dt>
                                <dd>{field.element_ref}</dd>
                              </div>
                            )}
                          </dl>
                        </details>
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
