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
          <p className="eyebrow">Overview</p>
          <h2>Dashboard</h2>
          <p>Create a reusable profile, then start a form analysis task.</p>
        </div>
        <Link className="button" to="/tasks/new">
          Create task
        </Link>
      </div>

      <div className="card-grid">
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
          <h3>1. Prepare profile</h3>
          <p>Save the information you commonly use in forms.</p>
          <Link to="/profiles">Manage profiles</Link>
        </article>

        <article className="card">
          <h3>2. Create a task</h3>
          <p>Create a task using a target URL and one profile.</p>
          <Link to="/tasks/new">Create a task</Link>
        </article>
      </div>

      <section className="section-block">
        <div className="section-heading">
          <h3>Tasks</h3>
          <Link to="/tasks/new">New task</Link>
        </div>

        <Message type="error">{tasksError}</Message>

        {tasksLoading ? (
          <p>Loading tasks...</p>
        ) : tasks.length === 0 ? (
          <div className="card empty-state">
            <p>No tasks yet. Create one to start an agent workflow.</p>
          </div>
        ) : (
          <div className="table-wrapper card">
            <table>
              <thead>
                <tr>
                  <th>Task</th>
                  <th>Status</th>
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
