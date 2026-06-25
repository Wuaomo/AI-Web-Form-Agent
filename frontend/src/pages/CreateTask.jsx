import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api } from "../api";
import {
  getSavedLlmProvider,
  saveLlmProvider,
} from "../llmProviderPreference";
import Message from "../components/Message";

function CreateTask() {
  const navigate = useNavigate();
  const [profiles, setProfiles] = useState([]);
  const [llmProviders, setLlmProviders] = useState([]);
  const [selectedLlmProvider, setSelectedLlmProvider] = useState("");
  const [form, setForm] = useState({ url: "", profile_id: "", description: "" });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([api.listProfiles(), api.listLlmProviders()])
      .then(([profileItems, providerItems]) => {
        setProfiles(profileItems);
        setLlmProviders(providerItems);
        setSelectedLlmProvider(getSavedLlmProvider(providerItems));
        if (profileItems.length) {
          setForm((current) => ({
            ...current,
            profile_id: String(profileItems[0].id),
          }));
        }
      })
      .catch((requestError) => setError(requestError.message))
      .finally(() => setLoading(false));
  }, []);

  function updateSelectedLlmProvider(provider) {
    setSelectedLlmProvider(provider);
    saveLlmProvider(provider);
  }

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
      const analyzedTask = await api.analyzeTask(task.id);
      if (analyzedTask.status === "LOGIN_REQUIRED") {
        navigate(`/tasks/${task.id}`, {
          state: {
            notice: "This form requires login before fields can be extracted.",
          },
        });
        return;
      }
      await api.mapTaskFields(task.id, {
        mode: "llm",
        provider: selectedLlmProvider,
      });
      navigate(`/tasks/${task.id}/review-mapping`);
    } catch (requestError) {
      if (task?.id) {
        navigate(`/tasks/${task.id}`, {
          state: { error: requestError.message },
        });
        return;
      }
      setError(requestError.message);
      setSaving(false);
    }
  }

  const selectedProvider = llmProviders.find(
    (provider) => provider.id === selectedLlmProvider,
  );
  const mappingUnavailable =
    !selectedLlmProvider || !selectedProvider?.configured;

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

        <label>
          Large model
          <select
            value={selectedLlmProvider}
            onChange={(event) => updateSelectedLlmProvider(event.target.value)}
            required
            disabled={loading || llmProviders.length === 0}
          >
            <option value="">Choose provider</option>
            {llmProviders.map((provider) => (
              <option key={provider.id} value={provider.id}>
                {provider.display_name} - {provider.model}
                {provider.configured ? "" : " - needs API key"}
              </option>
            ))}
          </select>
        </label>
        {!selectedLlmProvider && (
          <p className="provider-status provider-status-warning">
            Choose a model provider. This choice will be remembered.
          </p>
        )}
        {selectedLlmProvider && selectedProvider && !selectedProvider.configured && (
          <p className="provider-status provider-status-warning">
            {selectedProvider.setup_hint}
          </p>
        )}

        {profiles.length === 0 && !loading && (
          <p>
            You need a profile first. <Link to="/profiles">Create a profile</Link>.
          </p>
        )}

        <button
          className="button"
          type="submit"
          disabled={
            saving ||
            loading ||
            profiles.length === 0 ||
            mappingUnavailable
          }
        >
          {saving ? "Creating, analyzing, and mapping..." : "Create task"}
        </button>
      </form>
    </section>
  );
}

export default CreateTask;
