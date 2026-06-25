import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api } from "../api";
import Message from "../components/Message";

function CreateTask() {
  const navigate = useNavigate();
  const [profiles, setProfiles] = useState([]);
  const [form, setForm] = useState({ url: "", profile_id: "", description: "" });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .listProfiles()
      .then((items) => {
        setProfiles(items);
        if (items.length) {
          setForm((current) => ({ ...current, profile_id: String(items[0].id) }));
        }
      })
      .catch((requestError) => setError(requestError.message))
      .finally(() => setLoading(false));
  }, []);

  async function submitTask(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    let task = null;
    try {
      task = await api.createTask({
        ...form,
        profile_id: Number(form.profile_id),
        description: form.description || null,
      });
      await api.analyzeTask(task.id);
      navigate(`/tasks/${task.id}`);
    } catch (requestError) {
      if (task?.id) {
        navigate(`/tasks/${task.id}`);
        return;
      }
      setError(requestError.message);
      setSaving(false);
    }
  }

  return (
    <section className="narrow-page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">New automation</p>
          <h2>Create Task</h2>
          <p>Choose a profile and the web form you want to analyze.</p>
        </div>
      </div>

      <Message type="error">{error}</Message>

      <form className="card form-card" onSubmit={submitTask}>
        <label>
          Form URL
          <input
            type="url"
            value={form.url}
            onChange={(event) => setForm({ ...form, url: event.target.value })}
            placeholder="https://example.com/application"
            required
          />
        </label>

        <label>
          Profile
          <select
            value={form.profile_id}
            onChange={(event) => setForm({ ...form, profile_id: event.target.value })}
            required
            disabled={loading || profiles.length === 0}
          >
            {profiles.length === 0 && <option value="">No profiles available</option>}
            {profiles.map((profile) => (
              <option key={profile.id} value={profile.id}>
                {profile.profile_name}
              </option>
            ))}
          </select>
        </label>

        <label>
          Description
          <textarea
            rows="4"
            value={form.description}
            onChange={(event) => setForm({ ...form, description: event.target.value })}
            placeholder="Optional note about this task"
          />
        </label>

        {profiles.length === 0 && !loading && (
          <p>
            You need a profile first. <Link to="/profiles">Create a profile</Link>.
          </p>
        )}

        <button
          className="button"
          type="submit"
          disabled={saving || loading || profiles.length === 0}
        >
          {saving ? "Creating and analyzing..." : "Create task"}
        </button>
      </form>
    </section>
  );
}

export default CreateTask;
