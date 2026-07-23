import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api, API_BASE_URL } from "../api";
import Message from "../components/Message";
import { formatChinaTime } from "../dateTime";

function Dashboard() {
  const [health, setHealth] = useState("checking");
  const [tasks, setTasks] = useState([]);
  const [profiles, setProfiles] = useState([]);
  const [tasksLoading, setTasksLoading] = useState(true);
  const [error, setError] = useState("");
  const [tasksError, setTasksError] = useState("");

  useEffect(() => {
    api
      .health()
      .then((result) => setHealth(result.status))
      .catch((requestError) => {
        setHealth("offline");
        setError(requestError.message);
      });
  }, []);

  useEffect(() => {
    Promise.all([api.listTasks(), api.listProfiles()])
      .then(([taskItems, profileItems]) => {
        setTasks(taskItems);
        setProfiles(profileItems);
      })
      .catch((requestError) => setTasksError(requestError.message))
      .finally(() => setTasksLoading(false));
  }, []);

  const profilesById = new Map(
    profiles.map((profile) => [profile.id, profile.profile_name]),
  );

  return (
    <section>
      <div className="page-heading">
        <div>
          <p className="eyebrow">Runs</p>
          <h2>Review-first AI Browser Workflow Assistant</h2>
          <p>Read web pages, suggest source-backed answers, require human review, fill the browser, verify the result, and stop before final submission.</p>
        </div>
        <Link className="button" to="/tasks/new">
          Create run
        </Link>
      </div>

      <div className="card-grid">
        <article className="card">
          <h3>Security Questionnaire</h3>
          <p>Extract questionnaire items, suggest answers from reviewed memory or local policy docs, show evidence, require review, then fill approved values in the browser.</p>
          <Link className="button button-primary" to="/tasks/new?workflow_type=security_questionnaire">
            Start demo
          </Link>
        </article>

        <article className="card">
          <h3>Vendor Onboarding</h3>
          <p>Reuse reviewed company profile data for vendor onboarding forms with approval gates before browser execution.</p>
          <Link className="button" to="/tasks/new?workflow_type=vendor_onboarding">
            Start
          </Link>
        </article>

        <article className="card">
          <h3>Generic Form Fill</h3>
          <p>Map profile values to ordinary web forms, review every value, fill the browser, and stop before submit.</p>
          <Link className="button" to="/tasks/new?workflow_type=form_fill">
            Start
          </Link>
        </article>

        <article className="card">
          <h3>Backend status</h3>
          <p className={`status status-${health}`}>
            <span aria-hidden="true" />
            {health === "checking" ? "Checking..." : health}
          </p>
          <p className="muted">{API_BASE_URL}</p>
          <Message type="error">{error}</Message>
        </article>

        <article className="card">
          <h3>Profiles</h3>
          <p>Save the information you commonly use in workflows.</p>
          <Link to="/profiles">Manage profiles</Link>
        </article>

        <article className="card">
          <h3>Workflows</h3>
          <p>Browse all workflow templates.</p>
          <Link to="/workflows">Open templates</Link>
        </article>
      </div>

      <section className="section-block">
        <div className="section-heading">
          <h3>Recent runs</h3>
          <Link to="/tasks/new">Create run</Link>
        </div>

        <Message type="error">{tasksError}</Message>

        {tasksLoading ? (
          <p>Loading workflow runs...</p>
        ) : tasks.length === 0 ? (
          <div className="card empty-state">
            <p>No workflow runs yet. Create one to start an agent workflow.</p>
          </div>
        ) : (
          <div className="table-wrapper card">
            <table>
              <thead>
                <tr>
                  <th>Run</th>
                  <th>Status</th>
                  <th>Workflow Type</th>
                  <th>Profile</th>
                  <th>Description</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {tasks.map((task) => (
                  <tr key={task.id}>
                    <td>
                      <Link className="break-word" to={`/tasks/${task.id}`}>
                        {task.url}
                      </Link>
                    </td>
                    <td>
                      <span className="badge">{task.status}</span>
                    </td>
                    <td>{task.workflow_type || "—"}</td>
                    <td>{profilesById.get(task.profile_id) || task.profile_id}</td>
                    <td>{task.description || "—"}</td>
                    <td>{formatChinaTime(task.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </section>
  );
}

export default Dashboard;
