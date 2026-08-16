import { useEffect, useState } from "react";

import { api } from "../api";
import Message from "../components/Message";

function KnowledgeSources() {
  const [sources, setSources] = useState([]);
  const [file, setFile] = useState(null);
  const [fileInputKey, setFileInputKey] = useState(0);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [busyId, setBusyId] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function loadSources() {
    setLoading(true);
    setError("");
    try {
      setSources(await api.listKnowledgeSources());
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadSources();
  }, []);

  async function uploadSource(event) {
    event.preventDefault();
    if (!file) {
      setError("Choose a .md or .txt knowledge source first.");
      return;
    }

    setSaving(true);
    setError("");
    setNotice("");
    try {
      const content = await file.text();
      await api.createKnowledgeSource({
        filename: file.name,
        content,
      });
      setFile(null);
      setFileInputKey((current) => current + 1);
      setNotice("Knowledge source uploaded.");
      await loadSources();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSaving(false);
    }
  }

  async function deleteSource(source) {
    if (!window.confirm(`Delete "${source.title}"?`)) {
      return;
    }
    setBusyId(source.id);
    setError("");
    setNotice("");
    try {
      await api.deleteKnowledgeSource(source.id);
      setSources((current) => current.filter((item) => item.id !== source.id));
      setNotice("Knowledge source deleted.");
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
          <p className="eyebrow">Retrieval evidence</p>
          <h2>Knowledge</h2>
          <p>Upload reviewed text or markdown sources used by questionnaire suggestions.</p>
        </div>
        <button className="button button-secondary" type="button" onClick={loadSources}>
          Refresh
        </button>
      </div>

      <Message type="error">{error}</Message>
      <Message type="success">{notice}</Message>

      <div className="two-column">
        <form className="card form-card" onSubmit={uploadSource}>
          <div className="section-heading">
            <h3>Upload source</h3>
          </div>

          <label>
            Knowledge file
            <input
              key={fileInputKey}
              type="file"
              accept=".md,.txt,text/markdown,text/plain"
              onChange={(event) => setFile(event.target.files?.[0] || null)}
            />
          </label>

          <p className="muted-text">
            Supported now: plain text and markdown. Uploaded sections are searched
            together with the built-in demo policy.
          </p>

          <button className="button" type="submit" disabled={saving}>
            {saving ? "Uploading..." : "Upload knowledge source"}
          </button>
        </form>

        <div>
          <div className="section-heading">
            <h3>Available sources</h3>
          </div>

          {loading ? (
            <p>Loading knowledge sources...</p>
          ) : sources.length === 0 ? (
            <div className="card empty-state">
              <h3>No knowledge sources yet</h3>
              <p>Upload a security policy, FAQ, or questionnaire answer guide.</p>
            </div>
          ) : (
            <div className="card">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Title</th>
                    <th>File</th>
                    <th>Chunks</th>
                    <th>Created</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {sources.map((source) => (
                    <tr key={source.id}>
                      <td>{source.title}</td>
                      <td>{source.filename}</td>
                      <td>{source.chunk_count}</td>
                      <td>{source.created_at || "-"}</td>
                      <td>
                        <button
                          className="text-button"
                          type="button"
                          onClick={() => deleteSource(source)}
                          disabled={busyId === source.id}
                        >
                          {busyId === source.id ? "Deleting..." : "Delete"}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

export default KnowledgeSources;
