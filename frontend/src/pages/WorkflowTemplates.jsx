import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api";
import Message from "../components/Message";
import {
  buildWorkflowTemplateCreatePath,
  sortWorkflowTemplates,
  templateAvailabilityLabel,
} from "../workflowTemplatePresentation";

function WorkflowTemplates() {
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .listWorkflowTemplates()
      .then((items) => setTemplates(sortWorkflowTemplates(items)))
      .catch((requestError) => setError(requestError.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <section>
      <div className="page-heading">
        <div>
          <p className="eyebrow">Workflows</p>
          <h2>Workflow Templates</h2>
          <p>Choose an available template to start a new workflow run.</p>
        </div>
      </div>

      <Message type="error">{error}</Message>

      {loading ? (
        <p>Loading workflow templates...</p>
      ) : templates.length === 0 ? (
        <div className="card empty-state">
          <p>No workflow templates available.</p>
        </div>
      ) : (
        <div className="workflow-template-grid">
          {templates.map((template) => (
            <article key={template.id} className="card workflow-template-card">
              <div className="workflow-template-header">
                <div>
                  <h3>{template.name}</h3>
                  <p>{template.description}</p>
                </div>
                <span className="badge">{templateAvailabilityLabel(template)}</span>
              </div>
              {template.enabled ? (
                <Link
                  className="button"
                  to={buildWorkflowTemplateCreatePath(template.id)}
                >
                  Create
                </Link>
              ) : (
                <span className="muted">This template is coming soon.</span>
              )}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

export default WorkflowTemplates;
