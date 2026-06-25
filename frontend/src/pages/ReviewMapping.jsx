import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { api } from "../api";
import LlmMappingControls from "../components/LlmMappingControls";
import {
  getSavedLlmProvider,
  saveLlmProvider,
} from "../llmProviderPreference";
import Message from "../components/Message";

const profileKeys = [
  "first_name",
  "last_name",
  "full_name",
  "email",
  "phone",
  "university",
  "major",
  "linkedin",
  "github",
  "self_intro",
];

const nonFillableFieldTypes = new Set([
  "button",
  "file",
  "submit",
  "reset",
  "image",
]);

function isFillableField(field) {
  return !nonFillableFieldTypes.has((field.field_type || "").toLowerCase());
}

function fieldDisplayName(field) {
  return field.label || field.name || field.placeholder || field.selector;
}

function needsRequiredInput(field) {
  return field.required && isFillableField(field) && !field.mapped_value;
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

  return (
    <section>
      <div className="page-heading">
        <div>
          <p className="eyebrow">Task #{taskId}</p>
          <h2>Review Mapping</h2>
          <p>Review profile keys and values before any form-filling step.</p>
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
      ) : (
        <div className="table-wrapper card">
          <table>
            <thead>
              <tr>
                <th>Form field</th>
                <th>Type</th>
                <th>Profile key</th>
                <th>Mapped value</th>
              </tr>
            </thead>
            <tbody>
              {fields.map((field) => (
                <tr className={needsRequiredInput(field) ? "row-needs-input" : ""} key={field.id}>
                  <td>
                    <strong>{fieldDisplayName(field)}</strong>
                    {field.required && <span className="required"> required</span>}
                    {needsRequiredInput(field) && (
                      <span className="required"> needs input</span>
                    )}
                  </td>
                  <td>{field.field_type || "—"}</td>
                  <td>
                    <select
                      aria-label={`Profile key for ${field.label || field.selector}`}
                      value={field.mapped_profile_key || ""}
                      onChange={(event) =>
                        updateField(field.id, {
                          mapped_profile_key: event.target.value || null,
                        })
                      }
                    >
                      <option value="">Not mapped</option>
                      {profileKeys.map((key) => (
                        <option key={key} value={key}>
                          {key}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <input
                      aria-label={`Mapped value for ${field.label || field.selector}`}
                      value={field.mapped_value || ""}
                      onChange={(event) =>
                        setFields((current) =>
                          current.map((item) =>
                            item.id === field.id
                              ? { ...item, mapped_value: event.target.value }
                              : item,
                          ),
                        )
                      }
                      onBlur={(event) =>
                        updateField(field.id, {
                          mapped_value: event.target.value || null,
                        })
                      }
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export default ReviewMapping;
