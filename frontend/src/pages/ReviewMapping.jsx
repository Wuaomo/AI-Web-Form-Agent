import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api } from "../api";
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

function ReviewMapping() {
  const { taskId } = useParams();
  const [fields, setFields] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const loadFields = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setFields(await api.listTaskFields(taskId));
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
      setFields(await api.mapTaskFields(taskId));
      setNotice("Agent mappings generated.");
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
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
    setBusy(true);
    setError("");
    try {
      const result = await api.confirmMapping(taskId);
      setNotice(`Mapping confirmed. Task status: ${result.status}.`);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  }

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

      <div className="button-row">
        <button className="button" type="button" onClick={generateMappings} disabled={busy}>
          Generate mappings
        </button>
        <button
          className="button button-secondary"
          type="button"
          onClick={confirmMapping}
          disabled={busy || fields.length === 0}
        >
          Confirm mapping
        </button>
      </div>

      {loading ? (
        <p>Loading fields...</p>
      ) : fields.length === 0 ? (
        <div className="card empty-state">
          <p>No fields found. Analyze the task first.</p>
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
                <tr key={field.id}>
                  <td>
                    <strong>{field.label || field.name || field.selector}</strong>
                    {field.required && <span className="required"> required</span>}
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
