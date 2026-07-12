import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { api } from "../api";
import {
  getSavedLlmProvider,
  saveLlmProvider,
} from "../llmProviderPreference";
import Message from "../components/Message";
import {
  dockerDemoFormUrl,
  resolveWorkflowTypeSelection,
  sortWorkflowTemplates,
} from "../workflowTemplatePresentation";

function CreateTask() {
  const navigate = useNavigate();
  const location = useLocation();
  const [profiles, setProfiles] = useState([]);
  const [llmProviders, setLlmProviders] = useState([]);
  const [workflowTemplates, setWorkflowTemplates] = useState([]);
  const [selectedLlmProvider, setSelectedLlmProvider] = useState("");
  const [form, setForm] = useState({
    url: "",
    profile_id: "",
    description: "",
    workflow_type: "form_fill",
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    const requestedWorkflowType = new URLSearchParams(location.search).get(
      "workflow_type",
    );
    Promise.all([
      api.listProfiles(),
      api.listLlmProviders(),
      api.listWorkflowTemplates(),
    ])
      .then(([profileItems, providerItems, workflowItems]) => {
        const orderedWorkflows = sortWorkflowTemplates(workflowItems);
        const workflowSelection = resolveWorkflowTypeSelection(
          orderedWorkflows,
          requestedWorkflowType,
        );

        setProfiles(profileItems);
        setLlmProviders(providerItems);
        setWorkflowTemplates(orderedWorkflows);
        setSelectedLlmProvider(getSavedLlmProvider(providerItems));
        setNotice(workflowSelection.notice);
        if (profileItems.length) {
          setForm((current) => ({
            ...current,
            profile_id: String(profileItems[0].id),
            workflow_type:
              workflowSelection.selectedWorkflowType || current.workflow_type,
          }));
          return;
        }
        setForm((current) => ({
          ...current,
          workflow_type: workflowSelection.selectedWorkflowType || current.workflow_type,
        }));
      })
      .catch((requestError) => setError(requestError.message))
      .finally(() => setLoading(false));
  }, [location.search]);

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
      if (form.workflow_type === "web_data_extract") {
        await api.extractTaskPage(task.id);
        navigate(`/tasks/${task.id}`);
        return;
      }
      if (form.workflow_type === "job_research_summary") {
        await api.generateJobSummary(task.id);
        navigate(`/tasks/${task.id}`);
        return;
      }
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
  const selectedWorkflow = workflowTemplates.find(
    (workflow) => workflow.id === form.workflow_type,
  );
  const mappingUnavailable =
    form.workflow_type !== "web_data_extract" &&
    form.workflow_type !== "job_research_summary" &&
    (!selectedLlmProvider || !selectedProvider?.configured);
  const workflowUnavailable = !selectedWorkflow?.enabled;

  return (
    <section className="narrow-page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">New run</p>
          <h2>Create Workflow Run</h2>
          <p>Choose a profile, a workflow template, and the target form you want to prepare.</p>
        </div>
      </div>

      <Message type="error">{error}</Message>
      <Message type="warning">{notice}</Message>

      <form className="card form-card" onSubmit={submitTask}>
        <label>
          Workflow Template
          <select
            value={form.workflow_type}
            onChange={(event) =>
              setForm({ ...form, workflow_type: event.target.value })
            }
            required
            disabled={loading || workflowTemplates.length === 0}
          >
            {workflowTemplates.length === 0 && (
              <option value="">No workflows available</option>
            )}
            {workflowTemplates.map((workflow) => (
              <option
                key={workflow.id}
                value={workflow.id}
                disabled={!workflow.enabled}
              >
                {workflow.enabled
                  ? workflow.name
                  : `${workflow.name} (Coming soon)`}
              </option>
            ))}
          </select>
        </label>
        {selectedWorkflow && (
          <p className="muted">{selectedWorkflow.description}</p>
        )}

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
        <button
          type="button"
          className="text-button"
          onClick={() => setForm({ ...form, url: dockerDemoFormUrl() })}
        >
          Use Docker demo form
        </button>

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
            placeholder="Optional note about this workflow run"
          />
        </label>

        {form.workflow_type !== "web_data_extract" && form.workflow_type !== "job_research_summary" && (
          <>
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
          </>
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
            mappingUnavailable ||
            workflowUnavailable
          }
        >
          {saving ? "Creating, analyzing, and mapping..." : "Create run"}
        </button>
      </form>
    </section>
  );
}

export default CreateTask;
