package main

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"ai-web-form-agent-metrics/metrics"
)

func TestHealthEndpoint(t *testing.T) {
	req, err := http.NewRequest("GET", "/health", nil)
	if err != nil {
		t.Fatal(err)
	}

	rr := httptest.NewRecorder()
	handler := http.HandlerFunc(healthHandler)
	handler.ServeHTTP(rr, req)

	if status := rr.Code; status != http.StatusOK {
		t.Errorf("health handler returned wrong status code: got %v want %v", status, http.StatusOK)
	}

	var response map[string]string
	if err := json.NewDecoder(rr.Body).Decode(&response); err != nil {
		t.Errorf("Failed to decode health response: %v", err)
	}

	if response["status"] != "ok" {
		t.Errorf("health handler returned unexpected body: got %v want %v", response["status"], "ok")
	}
}

func TestMetricsEndpoint(t *testing.T) {
	req, err := http.NewRequest("GET", "/metrics", nil)
	if err != nil {
		t.Fatal(err)
	}

	rr := httptest.NewRecorder()
	handler := http.HandlerFunc(metricsHandler)
	handler.ServeHTTP(rr, req)

	if status := rr.Code; status != http.StatusOK {
		t.Errorf("metrics handler returned wrong status code: got %v want %v", status, http.StatusOK)
	}

	var response map[string]interface{}
	if err := json.NewDecoder(rr.Body).Decode(&response); err != nil {
		t.Errorf("Failed to decode metrics response: %v", err)
	}
}

func TestEventsEndpointPost(t *testing.T) {
	aggregator = metrics.NewAggregator()

	eventBody := `{"event_type":"job_succeeded","task_id":55,"job_id":101,"job_type":"MAP_FIELDS","duration_ms":1200,"worker_id":"worker-local-1","created_at":"2026-07-03T10:00:00Z"}`

	req, err := http.NewRequest("POST", "/events", bytes.NewBufferString(eventBody))
	if err != nil {
		t.Fatal(err)
	}
	req.Header.Set("Content-Type", "application/json")

	rr := httptest.NewRecorder()
	handler := http.HandlerFunc(eventsHandler)
	handler.ServeHTTP(rr, req)

	if status := rr.Code; status != http.StatusAccepted {
		t.Errorf("events handler returned wrong status code: got %v want %v", status, http.StatusAccepted)
	}

	snapshot := aggregator.Snapshot()
	if snapshot.TotalEvents != 1 {
		t.Errorf("Expected total events 1, got %d", snapshot.TotalEvents)
	}
	if snapshot.JobsByType["MAP_FIELDS"] != 1 {
		t.Errorf("Expected MAP_FIELDS count 1, got %d", snapshot.JobsByType["MAP_FIELDS"])
	}
}

func TestEventsEndpointMethodNotAllowed(t *testing.T) {
	req, err := http.NewRequest("GET", "/events", nil)
	if err != nil {
		t.Fatal(err)
	}

	rr := httptest.NewRecorder()
	handler := http.HandlerFunc(eventsHandler)
	handler.ServeHTTP(rr, req)

	if status := rr.Code; status != http.StatusMethodNotAllowed {
		t.Errorf("events handler returned wrong status code: got %v want %v", status, http.StatusMethodNotAllowed)
	}
}

func TestEventsEndpointInvalidJSON(t *testing.T) {
	req, err := http.NewRequest("POST", "/events", bytes.NewBufferString("invalid json"))
	if err != nil {
		t.Fatal(err)
	}
	req.Header.Set("Content-Type", "application/json")

	rr := httptest.NewRecorder()
	handler := http.HandlerFunc(eventsHandler)
	handler.ServeHTTP(rr, req)

	if status := rr.Code; status != http.StatusBadRequest {
		t.Errorf("events handler returned wrong status code for invalid JSON: got %v want %v", status, http.StatusBadRequest)
	}
}