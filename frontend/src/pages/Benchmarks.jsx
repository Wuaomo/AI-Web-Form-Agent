import { useEffect, useState } from "react";

import { api } from "../api";
import Message from "../components/Message";
import {
  caseFailureCount,
  failureReasonLabel,
  metricEntries,
  selectDefaultProviderId,
  shouldDisableBenchmarkRun,
  summaryMetricEntries,
  summarizeBenchmarkRun,
} from "../benchmarkPresentation";

function Benchmarks() {
  const [runs, setRuns] = useState([]);
  const [selectedRun, setSelectedRun] = useState(null);
  const [mode, setMode] = useState("rules");
  const [providers, setProviders] = useState([]);
  const [selectedProviderId, setSelectedProviderId] = useState("");
  const [providersError, setProvidersError] = useState("");
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

  async function loadProviders() {
    setProvidersError("");
    try {
      const items = await api.listLlmProviders();
      const providersList = Array.isArray(items) ? items : [];
      setProviders(providersList);
      setSelectedProviderId((current) => {
        if (current && providersList.some((provider) => provider?.id === current)) {
          return current;
        }
        return selectDefaultProviderId(providersList);
      });
    } catch (requestError) {
      setProviders([]);
      setSelectedProviderId("");
      setProvidersError(requestError.message);
    }
  }

  useEffect(() => {
    loadProviders();
  }, []);

  async function runBenchmarks() {
    setBusy(true);
    setError("");
    try {
      const options =
        mode === "llm"
          ? { mode: "llm", provider: selectedProviderId }
          : { mode: "rules" };
      const run = await api.runBenchmarks(options);
      setRuns((current) => [run, ...current]);
      setSelectedRun(run);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  }

  const summary = summarizeBenchmarkRun(selectedRun || {});
  const selectedProvider =
    providers.find((provider) => provider?.id === selectedProviderId) || null;
  const disableRunButton = busy || shouldDisableBenchmarkRun(mode, selectedProvider);
  const setupHint =
    mode === "llm" && selectedProvider?.configured !== true ? selectedProvider?.setup_hint : "";

  return (
    <section>
      <div className="page-heading">
        <div>
          <p className="eyebrow">Evaluation</p>
          <h2>Benchmarks</h2>
          <p>Run local benchmark forms and inspect extraction and mapping accuracy.</p>
        </div>
        <div
          style={{
            display: "flex",
            gap: "0.75rem",
            flexWrap: "wrap",
            alignItems: "flex-end",
            justifyContent: "flex-end",
          }}
        >
          <label style={{ width: 160 }}>
            Mode
            <select value={mode} onChange={(event) => setMode(event.target.value)}>
              <option value="rules">rules</option>
              <option value="llm">llm</option>
            </select>
          </label>
          {mode === "llm" && (
            <label style={{ width: 260 }}>
              Provider
              <select
                value={selectedProviderId}
                onChange={(event) => setSelectedProviderId(event.target.value)}
                disabled={providers.length === 0}
              >
                {providers.length === 0 ? (
                  <option value="">No providers available</option>
                ) : (
                  providers.map((provider) => (
                    <option key={provider.id} value={provider.id}>
                      {provider.configured === true
                        ? provider.display_name
                        : `${provider.display_name} - not configured`}
                    </option>
                  ))
                )}
              </select>
            </label>
          )}
          <button className="button" type="button" onClick={runBenchmarks} disabled={disableRunButton}>
            {busy ? "Running..." : "Run benchmarks"}
          </button>
        </div>
      </div>

      <Message type="error">{error}</Message>
      <Message type="warning">{providersError}</Message>
      <Message type="warning">{setupHint}</Message>

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
                <h3>Run configuration</h3>
                <dl className="metric-list">
                  <div>
                    <dt>Mode</dt>
                    <dd>{selectedRun.mode || "rules"}</dd>
                  </div>
                  {(selectedRun.mode || "rules") === "llm" && (
                    <div>
                      <dt>Provider</dt>
                      <dd>{selectedRun.provider || selectedRun.provider_id || "—"}</dd>
                    </div>
                  )}
                </dl>
              </div>

              <div className="card">
                <h3>Summary metrics</h3>
                <dl className="metric-list">
                  {summaryMetricEntries(selectedRun.summary_metrics).map((metric) => (
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
                  {(selectedRun.case_results || []).map((caseResult) => (
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
                      {(caseResult.failures || []).length > 0 && (
                        <table className="data-table">
                          <thead>
                            <tr>
                              <th>Selector</th>
                              <th>Expected</th>
                              <th>Actual</th>
                              <th>Reason</th>
                              <th>Detail</th>
                            </tr>
                          </thead>
                          <tbody>
                            {(caseResult.failures || []).map((failure, index) => (
                              <tr key={`${failure.selector}-${index}`}>
                                <td>{failure.selector}</td>
                                <td>{failure.expected_profile_key || "none"}</td>
                                <td>{failure.actual_profile_key || "none"}</td>
                                <td>{failureReasonLabel(failure.reason)}</td>
                                <td>{failure.detail || "—"}</td>
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

