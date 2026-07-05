import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api";
import { formatChinaTime } from "../dateTime";
import Message from "../components/Message";

function ApprovalCenter() {
  const [approvals, setApprovals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function loadApprovals() {
    const items = await api.listApprovals({ status: "PENDING" });
    setApprovals(items);
  }

  useEffect(() => {
    loadApprovals()
      .catch((requestError) => setError(requestError.message))
      .finally(() => setLoading(false));
  }, []);

  async function resolveApproval(approvalId, action) {
    setBusyId(approvalId);
    setError("");
    setNotice("");
    try {
      if (action === "approve") {
        await api.approveApproval(approvalId);
        setNotice("Approval granted.");
      } else {
        await api.rejectApproval(approvalId);
        setNotice("Approval rejected.");
      }
      await loadApprovals();
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
          <p className="eyebrow">Workflow approvals</p>
          <h2>Approval Center</h2>
        </div>
      </div>

      <Message type="error">{error}</Message>
      <Message type="success">{notice}</Message>

      <div className="card">
        {loading ? (
          <p>Loading approvals...</p>
        ) : approvals.length === 0 ? (
          <p>No pending approvals.</p>
        ) : (
          <ul className="job-list">
            {approvals.map((approval) => (
              <li key={approval.id} className="job-item">
                <div className="job-item-header">
                  <strong>{approval.step_name}</strong>
                  <span className="badge">{approval.status}</span>
                </div>
                <div>Task #{approval.task_id}</div>
                <div className="muted-text">{approval.reason}</div>
                <div className="muted-text">
                  {approval.risk_type} · {approval.risk_level} · {formatChinaTime(approval.created_at)}
                </div>
                <div className="agent-review-actions">
                  <button
                    type="button"
                    className="button button-small"
                    onClick={() => resolveApproval(approval.id, "approve")}
                    disabled={busyId === approval.id}
                  >
                    {busyId === approval.id ? "Working..." : "Approve"}
                  </button>
                  <button
                    type="button"
                    className="button button-small button-secondary"
                    onClick={() => resolveApproval(approval.id, "reject")}
                    disabled={busyId === approval.id}
                  >
                    Reject
                  </button>
                  <Link className="button button-small button-secondary" to={`/tasks/${approval.task_id}`}>
                    Open Task
                  </Link>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

export default ApprovalCenter;
