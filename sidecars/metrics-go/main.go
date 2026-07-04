package main

import (
	"encoding/json"
	"log"
	"net/http"

	"ai-web-form-agent-metrics/metrics"
)

var aggregator = metrics.NewAggregator()

func main() {
	http.HandleFunc("/health", healthHandler)
	http.HandleFunc("/metrics", metricsHandler)
	http.HandleFunc("/events", eventsHandler)

	log.Println("Starting metrics sidecar on :9100")
	log.Fatal(http.ListenAndServe(":9100", nil))
}

func healthHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
}

func metricsHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(aggregator.Snapshot())
}

func eventsHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		w.WriteHeader(http.StatusMethodNotAllowed)
		return
	}

	var event metrics.Event
	if err := json.NewDecoder(r.Body).Decode(&event); err != nil {
		log.Printf("Error parsing event: %v", err)
		w.WriteHeader(http.StatusBadRequest)
		return
	}

	aggregator.Record(event)
	w.WriteHeader(http.StatusAccepted)
}