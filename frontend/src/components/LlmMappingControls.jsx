function LlmMappingControls({
  mode,
  onModeChange,
  provider,
  onProviderChange,
  providers,
  disabled = false,
}) {
  const selectedProvider =
    providers.find((item) => item.id === provider) || providers[0] || null;
  const hasProviderSelection = Boolean(provider);

  return (
    <div className="mapping-controls">
      <label>
        Mapping engine
        <select
          value={mode}
          onChange={(event) => onModeChange(event.target.value)}
          disabled={disabled}
        >
          <option value="llm">LLM semantic mapping</option>
          <option value="rules">Local rules</option>
        </select>
      </label>
      <label>
        Large model
        <select
          value={provider}
          onChange={(event) => onProviderChange(event.target.value)}
          disabled={disabled || mode !== "llm" || providers.length === 0}
        >
          <option value="">Choose provider</option>
          {providers.map((item) => (
            <option key={item.id} value={item.id}>
              {item.display_name} - {item.model}
              {item.configured ? "" : " - needs API key"}
            </option>
          ))}
        </select>
      </label>
      {mode === "llm" && !hasProviderSelection && (
        <p className="provider-status provider-status-warning">
          Choose a model provider. This choice will be remembered for future tasks.
        </p>
      )}
      {mode === "llm" && hasProviderSelection && selectedProvider && (
        <p
          className={
            selectedProvider.configured
              ? "provider-status provider-status-ok"
              : "provider-status provider-status-warning"
          }
        >
          {selectedProvider.configured
            ? `Ready: using ${selectedProvider.display_name} (${selectedProvider.model}).`
            : selectedProvider.setup_hint}
        </p>
      )}
    </div>
  );
}

export default LlmMappingControls;
