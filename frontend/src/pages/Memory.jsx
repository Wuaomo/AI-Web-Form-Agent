import { useEffect, useState } from "react";

import { api } from "../api";
import Message from "../components/Message";
import {
  memoryFieldPreview,
  memoryProfileKeyLabel,
  memorySourceLabel,
  memoryStatusLabel,
} from "../memoryPresentation";

function Memory() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function loadMemory() {
    setLoading(true);
    setError("");
    try {
      setItems(await api.listWorkflowMemory());
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadMemory();
  }, []);

  async function deleteMemory(item) {
    if (!window.confirm(`Delete memory for ${memoryProfileKeyLabel(item)}?`)) {
      return;
    }
    setBusyId(item.id);
    setError("");
    setNotice("");
    try {
      await api.deleteWorkflowMemory(item.id);
      setItems((current) => current.filter((entry) => entry.id !== item.id));
      setNotice("Memory deleted.");
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <section>
      <div className="page-heading">
        <div>
          <p className="eyebrow">Reviewed memory</p>
          <h2>Memory</h2>
          <p>Review and remove saved field mappings used by retrieval.</p>
        </div>
        <button className="button button-secondary" type="button" onClick={loadMemory}>
          Refresh
        </button>
      </div>

      <Message type="error">{error}</Message>
      <Message type="success">{notice}</Message>

      {loading ? (
        <p>Loading memory...</p>
      ) : items.length === 0 ? (
        <div className="card empty-state">
          <h3>No reviewed memory yet</h3>
          <p>Confirmed safe mappings will appear here after review.</p>
        </div>
      ) : (
        <div className="card">
          <table className="data-table">
            <thead>
              <tr>
                <th>Field</th>
                <th>Profile key</th>
                <th>Source</th>
                <th>Status</th>
                <th>Reviewed</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id}>
                  <td>{memoryFieldPreview(item)}</td>
                  <td>{memoryProfileKeyLabel(item)}</td>
                  <td>{memorySourceLabel(item)}</td>
                  <td>{memoryStatusLabel(item)}</td>
                  <td>{item.reviewed_at || "-"}</td>
                  <td>
                    <button
                      className="text-button"
                      type="button"
                      onClick={() => deleteMemory(item)}
                      disabled={busyId === item.id}
                    >
                      {busyId === item.id ? "Deleting..." : "Delete"}
                    </button>
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

export default Memory;

