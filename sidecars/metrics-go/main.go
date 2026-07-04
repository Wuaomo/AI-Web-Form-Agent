package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
)

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
	fmt.Fprintf(w, `{"status":"ok"}`)
}

func metricsHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	fmt.Fprintf(w, `{}`)
}

func eventsHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		w.WriteHeader(http.StatusMethodNotAllowed)
		return
	}

	var event map[string]interface{}
	if err := json.NewDecoder(r.Body).Decode(&event); err != nil {
		log.Printf("Error parsing event: %v", err)
	}

	w.WriteHeader(http.StatusAccepted)
}