import { useEffect, useState } from "react";

import { api } from "../api";
import Message from "../components/Message";
import {
  caseFailureCount,
  metricEntries,
  summarizeBenchmarkRun,
} from "../benchmarkPresentation";

function Benchmarks() {
  const [runs, setRuns] = useState([]);
  const [selectedRun, setSelectedRun] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function loadRuns() {
    setError("");
    try {
      const items = await api.listBenchmarkRuns();
      setRuns(items);
      setSelectedRun(items[0] || null);
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  useEffect(() => {
    loadRuns();
  }, []);

  async function runBenchmarks() {
    setBusy(true);
    setError("");
    try {
      const run = await api.runBenchmarks({ mode: "rules" });
      setRuns((current) => [run, ...current]);
      setSelectedRun(run);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  }

  const summary = summarizeBenchmarkRun(selectedRun || {});

  return (
    <section>
      <div className="page-heading">
        <div>
          <p className="eyebrow">Evaluation</p>
          <h2>Benchmarks</h2>
          <p>Run local benchmark forms and inspect extraction and mapping accuracy.</p>
        </div>
        <button className="button" type="button" onClick={runBenchmarks} disabled={busy}>
          {busy ? "Running..." : "Run benchmarks"}
        </button>
      </div>

      <Message type="error">{error}</Message>

      {!selectedRun ? (
        <div className="card empty-state">
          <p>No benchmark runs yet.</p>
        </div>
      ) : (
        <>
          <div className="metric-grid">
            <div className="metric-card">
              <span>Average score</span>
              <strong>{summary.averageScore}</strong>
            </div>
            <div className="metric-card">
              <span>Cases</span>
              <strong>{summary.totalCases}</strong>
            </div>
            <div className="metric-card">
              <span>Failures</span>
              <strong>{summary.totalFailures}</strong>
            </div>
          </div>

          <div className="benchmark-layout">
            <aside className="card benchmark-runs">
              <h3>Runs</h3>
              {runs.map((run) => (
                <button
                  key={run.id}
                  type="button"
                  className={selectedRun.id === run.id ? "active" : ""}
                  onClick={() => setSelectedRun(run)}
                >
                  <span>Run #{run.id}</span>
                  <strong>{Math.round(run.average_score * 100)}%</strong>
                </button>
              ))}
            </aside>

            <div className="benchmark-detail">
              <div className="card">
                <h3>Summary metrics</h3>
                <dl className="metric-list">
                  {metricEntries(selectedRun.summary_metrics).map((metric) => (
                    <div key={metric.key}>
                      <dt>{metric.label}</dt>
                      <dd>{metric.value}</dd>
                    </div>
                  ))}
                </dl>
              </div>

              <div className="card">
                <h3>Case results</h3>
                <div className="benchmark-case-list">
                  {selectedRun.case_results.map((caseResult) => (
                    <details key={caseResult.id} open={caseFailureCount(caseResult) > 0}>
                      <summary>
                        <span>{caseResult.title}</span>
                        <strong>{caseFailureCount(caseResult)} failures</strong>
                      </summary>
                      <dl className="metric-list compact">
                        {metricEntries(caseResult.metrics).map((metric) => (
                          <div key={metric.key}>
                            <dt>{metric.label}</dt>
                            <dd>{metric.value}</dd>
                          </div>
                        ))}
                      </dl>
                      {caseResult.failures.length > 0 && (
                        <table className="data-table">
                          <thead>
                            <tr>
                              <th>Selector</th>
                              <th>Expected</th>
                              <th>Actual</th>
                              <th>Reason</th>
                            </tr>
                          </thead>
                          <tbody>
                            {caseResult.failures.map((failure, index) => (
                              <tr key={`${failure.selector}-${index}`}>
                                <td>{failure.selector}</td>
                                <td>{failure.expected_profile_key || "none"}</td>
                                <td>{failure.actual_profile_key || "none"}</td>
                                <td>{failure.reason}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      )}
                    </details>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </section>
  );
}

export default Benchmarks;

