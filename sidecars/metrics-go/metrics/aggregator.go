package metrics

import (
	"sync"
	"time"
)

type Event struct {
	EventType   string `json:"event_type"`
	TaskID      int    `json:"task_id"`
	JobID       int    `json:"job_id"`
	JobType     string `json:"job_type"`
	DurationMS  int    `json:"duration_ms"`
	WorkerID    string `json:"worker_id"`
	CreatedAt   string `json:"created_at"`
}

type DurationStats struct {
	Total int `json:"total"`
	Count int `json:"count"`
	Avg   int `json:"avg"`
}

type MetricsSnapshot struct {
	TotalEvents         int                `json:"total_events"`
	JobsByStatus        map[string]int     `json:"jobs_by_status"`
	JobsByType          map[string]int     `json:"jobs_by_type"`
	AvgDurationByJobType map[string]DurationStats `json:"avg_duration_by_job_type"`
	WorkerLastSeen      map[string]string  `json:"worker_last_seen"`
	RetryCount          int                `json:"retry_count"`
}

type Aggregator struct {
	mu                  sync.RWMutex
	totalEvents         int
	jobsByStatus        map[string]int
	jobsByType          map[string]int
	avgDurationByJobType map[string]DurationStats
	workerLastSeen      map[string]string
	retryCount          int
}

func NewAggregator() *Aggregator {
	return &Aggregator{
		jobsByStatus:        make(map[string]int),
		jobsByType:          make(map[string]int),
		avgDurationByJobType: make(map[string]DurationStats),
		workerLastSeen:      make(map[string]string),
	}
}

func (a *Aggregator) Record(event Event) {
	a.mu.Lock()
	defer a.mu.Unlock()

	a.totalEvents++

	switch event.EventType {
	case "job_enqueued":
		a.jobsByStatus["enqueued"]++
		if event.JobType != "" {
			a.jobsByType[event.JobType]++
		}
	case "job_started":
		a.jobsByStatus["started"]++
	case "job_succeeded":
		a.jobsByStatus["succeeded"]++
	case "job_failed":
		a.jobsByStatus["failed"]++
	case "job_retry_scheduled":
		a.jobsByStatus["retry_scheduled"]++
		a.retryCount++
	case "checkpoint_written":
		a.jobsByStatus["checkpoint_written"]++
	}

	if event.JobType != "" && event.DurationMS > 0 {
		stats := a.avgDurationByJobType[event.JobType]
		stats.Total += event.DurationMS
		stats.Count++
		stats.Avg = stats.Total / stats.Count
		a.avgDurationByJobType[event.JobType] = stats
	}

	if event.WorkerID != "" {
		if event.CreatedAt != "" {
			a.workerLastSeen[event.WorkerID] = event.CreatedAt
		} else {
			a.workerLastSeen[event.WorkerID] = time.Now().UTC().Format(time.RFC3339)
		}
	}
}

func (a *Aggregator) Snapshot() MetricsSnapshot {
	a.mu.RLock()
	defer a.mu.RUnlock()

	jobsByStatus := make(map[string]int, len(a.jobsByStatus))
	for k, v := range a.jobsByStatus {
		jobsByStatus[k] = v
	}

	jobsByType := make(map[string]int, len(a.jobsByType))
	for k, v := range a.jobsByType {
		jobsByType[k] = v
	}

	avgDurationByJobType := make(map[string]DurationStats, len(a.avgDurationByJobType))
	for k, v := range a.avgDurationByJobType {
		avgDurationByJobType[k] = v
	}

	workerLastSeen := make(map[string]string, len(a.workerLastSeen))
	for k, v := range a.workerLastSeen {
		workerLastSeen[k] = v
	}

	return MetricsSnapshot{
		TotalEvents:         a.totalEvents,
		JobsByStatus:        jobsByStatus,
		JobsByType:          jobsByType,
		AvgDurationByJobType: avgDurationByJobType,
		WorkerLastSeen:      workerLastSeen,
		RetryCount:          a.retryCount,
	}
}