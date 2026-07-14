import { useEffect, useState } from "react";

import { api } from "../api";
import Message from "../components/Message";
import {
  buildModeDetail,
  caseFailureCount,
  compareRunMetrics,
  failureReasonLabel,
  formatDuration,
  formatRegressionStatus,
  metricEntries,
  parseModeDetail,
  selectDefaultProviderId,
  shouldDisableBenchmarkRun,
  sortCaseResults,
  summaryMetricEntries,
  summarizeBenchmarkRun,
} from "../benchmarkPresentation";

function Benchmarks() {
  const [runs, setRuns] = useState([]);
  const [selectedRun, setSelectedRun] = useState(null);
  const [mode, setMode] = useState("rules");
  const [stressMode, setStressMode] = useState("standard");
  const [memoryMode, setMemoryMode] = useState("off");
  const [baselineRunId, setBaselineRunId] = useState("");
  const [providers, setProviders] = useState([]);
  const [selectedProviderId, setSelectedProviderId] = useState("");
  const [providersError, setProvidersError] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const [compareRunAId, setCompareRunAId] = useState("");
  const [compareRunBId, setCompareRunBId] = useState("");

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

  useEffect(() => {
    if (mode === "rules") {
      setMemoryMode("off");
    } else if (mode === "rag_llm") {
      setMemoryMode("on");
    }
  }, [mode]);

  async function runBenchmarks() {
    setBusy(true);
    setError("");
    try {
      const normalizedMemoryMode = mode === "rag_llm" ? "on" : memoryMode;
      const options = {
        mode,
        stress_mode: stressMode,
        ...(mode === "llm" || mode === "rag_llm"
          ? { provider: selectedProviderId, memory_mode: normalizedMemoryMode }
          : {}),
        ...(baselineRunId ? { baseline_run_id: Number(baselineRunId) } : {}),
      };
      const run = await api.runBenchmarks(options);
      setRuns((current) => [run, ...current]);
      setSelectedRun(run);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  }

  async function copyMarkdownReport() {
    if (!selectedRun) return;
    try {
      const report = await api.getBenchmarkReport(selectedRun.id);
      await navigator.clipboard.writeText(report);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  const summary = summarizeBenchmarkRun(selectedRun || {});
  const selectedProvider =
    providers.find((provider) => provider?.id === selectedProviderId) || null;
  const disableRunButton = busy || shouldDisableBenchmarkRun(mode, selectedProvider);
  const setupHint =
    (mode === "llm" || mode === "rag_llm") && selectedProvider?.configured !== true
      ? selectedProvider?.setup_hint
      : "";

  const normalizedProviderId = mode === "rules" ? null : selectedProviderId || null;
  const normalizedMemoryMode = mode === "rules" ? "off" : mode === "rag_llm" ? "on" : memoryMode;
  const desiredModeDetail = buildModeDetail(stressMode, normalizedMemoryMode);
  const baselineCandidates = runs.filter((run) => {
    const runMode = run.mode || "rules";
    const runProvider = run.provider || null;
    const runDetail = run.mode_detail || null;
    if (runMode !== mode) return false;
    if (runProvider !== normalizedProviderId) return false;
    return runDetail === desiredModeDetail;
  });

  const compareRunA = runs.find((run) => String(run.id) === String(compareRunAId)) || null;
  const compareRunB = runs.find((run) => String(run.id) === String(compareRunBId)) || null;
  const compareEntries =
    compareRunA && compareRunB
      ? compareRunMetrics(compareRunA.summary_metrics || {}, compareRunB.summary_metrics || {})
      : [];

  return (
    <section>
      <div className="page-heading">
        <div>
          <p className="eyebrow">Evaluation</p>
          <h2>Evaluation Center</h2>
          <p>Run local evaluation fixtures and inspect extraction and mapping accuracy.</p>
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
              <option value="rag_llm">rag_llm</option>
              <option value="full_workflow">full_workflow</option>
            </select>
          </label>
          <label style={{ width: 160 }}>
            Stress Mode
            <select value={stressMode} onChange={(event) => setStressMode(event.target.value)}>
              <option value="standard">standard</option>
              <option value="cache_cold">cache_cold</option>
              <option value="cache_warm">cache_warm</option>
              <option value="concurrent">concurrent</option>
            </select>
          </label>
          {(mode === "llm" || mode === "rag_llm") && (
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
          {(mode === "llm" || mode === "rag_llm") && (
            <label style={{ width: 160 }}>
              Memory Mode
              <select
                value={normalizedMemoryMode}
                onChange={(event) => setMemoryMode(event.target.value)}
                disabled={mode === "rag_llm"}
              >
                <option value="off">off</option>
                <option value="on">on</option>
              </select>
            </label>
          )}
          <label style={{ width: 220 }}>
            Baseline
            <select value={baselineRunId} onChange={(event) => setBaselineRunId(event.target.value)}>
              <option value="">Auto</option>
              {baselineCandidates.map((run) => (
                <option key={run.id} value={run.id}>
                  Run #{run.id} ({Math.round(run.average_score * 100)}%)
                </option>
              ))}
            </select>
          </label>
          <button className="button" type="button" onClick={runBenchmarks} disabled={disableRunButton}>
            {busy ? "Running..." : "Run evaluation"}
          </button>
        </div>
      </div>

      <Message type="error">{error}</Message>
      <Message type="warning">{providersError}</Message>
      <Message type="warning">{setupHint}</Message>

      {!selectedRun ? (
        <div className="card empty-state">
          <p>No evaluation runs yet.</p>
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
            <div className="metric-card">
              <span>Duration</span>
              <strong>{formatDuration(selectedRun.duration_ms)}</strong>
            </div>
            <div className="metric-card">
              <span>Regressions</span>
              <strong>{selectedRun.regression_count || 0}</strong>
            </div>
            <div className="metric-card">
              <span>Improvements</span>
              <strong>{selectedRun.improvement_count || 0}</strong>
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
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
                  <h3>Run configuration</h3>
                  <button
                    className="button button-secondary"
                    type="button"
                    onClick={copyMarkdownReport}
                    disabled={busy}
                  >
                    {copied ? "Copied!" : "Copy Markdown Report"}
                  </button>
                </div>
                <dl className="metric-list">
                  <div>
                    <dt>Mode</dt>
                    <dd>{selectedRun.mode || "rules"}</dd>
                  </div>
                  {(selectedRun.mode || "rules") !== "rules" && (
                    <div>
                      <dt>Provider</dt>
                      <dd>{selectedRun.provider || selectedRun.provider_id || "—"}</dd>
                    </div>
                  )}
                  {selectedRun.mode_detail ? (
                    (() => {
                      const detail = parseModeDetail(selectedRun.mode_detail);
                      return (
                        <>
                          {detail.stressMode ? (
                            <div>
                              <dt>Stress Mode</dt>
                              <dd>{detail.stressMode}</dd>
                            </div>
                          ) : null}
                          {detail.memoryMode ? (
                            <div>
                              <dt>Memory Mode</dt>
                              <dd>{detail.memoryMode}</dd>
                            </div>
                          ) : null}
                          {!detail.stressMode && !detail.memoryMode ? (
                            <div>
                              <dt>Run Detail</dt>
                              <dd>{detail.modeDetail}</dd>
                            </div>
                          ) : null}
                        </>
                      );
                    })()
                  ) : null}
                  {selectedRun.baseline_run_id && (
                    <div>
                      <dt>Baseline Run</dt>
                      <dd>#{selectedRun.baseline_run_id}</dd>
                    </div>
                  )}
                  {selectedRun.regression_count > 0 || selectedRun.improvement_count > 0 ? (
                    <div>
                      <dt>Regression Status</dt>
                      <dd>{formatRegressionStatus(selectedRun.regression_count, selectedRun.improvement_count)}</dd>
                    </div>
                  ) : null}
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
                  {sortCaseResults(selectedRun.case_results || []).map((caseResult) => (
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

              {runs.length > 1 ? (
                <div className="card">
                  <h3>Compare runs</h3>
                  <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap", marginBottom: "1rem" }}>
                    <label style={{ width: 220 }}>
                      Run A
                      <select value={compareRunAId} onChange={(event) => setCompareRunAId(event.target.value)}>
                        <option value="">Select run</option>
                        {runs.map((run) => (
                          <option key={run.id} value={run.id}>
                            Run #{run.id} ({run.mode || "rules"})
                          </option>
                        ))}
                      </select>
                    </label>
                    <label style={{ width: 220 }}>
                      Run B
                      <select value={compareRunBId} onChange={(event) => setCompareRunBId(event.target.value)}>
                        <option value="">Select run</option>
                        {runs.map((run) => (
                          <option key={run.id} value={run.id}>
                            Run #{run.id} ({run.mode || "rules"})
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>
                  {compareRunA && compareRunB ? (
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Metric</th>
                          <th>A</th>
                          <th>B</th>
                          <th>Delta (A - B)</th>
                        </tr>
                      </thead>
                      <tbody>
                        {compareEntries.map((entry) => (
                          <tr key={entry.key}>
                            <td>{entry.label}</td>
                            <td>{entry.current}</td>
                            <td>{entry.baseline}</td>
                            <td>{entry.delta}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : (
                    <p style={{ margin: 0, color: "var(--muted)" }}>
                      Select two runs to compare summary metrics.
                    </p>
                  )}
                </div>
              ) : null}
            </div>
          </div>
        </>
      )}
    </section>
  );
}

export default Benchmarks;

