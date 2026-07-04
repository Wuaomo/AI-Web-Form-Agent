package metrics

import (
	"testing"
)

func TestRecordEventIncrementsTotal(t *testing.T) {
	agg := NewAggregator()

	event := Event{
		EventType: "job_succeeded",
		JobType:   "MAP_FIELDS",
	}

	agg.Record(event)
	snapshot := agg.Snapshot()

	if snapshot.TotalEvents != 1 {
		t.Errorf("Expected total events 1, got %d", snapshot.TotalEvents)
	}
}

func TestJobTypeCountsIncrement(t *testing.T) {
	agg := NewAggregator()

	agg.Record(Event{EventType: "job_succeeded", JobType: "MAP_FIELDS"})
	agg.Record(Event{EventType: "job_succeeded", JobType: "FILL_FORM"})
	agg.Record(Event{EventType: "job_succeeded", JobType: "MAP_FIELDS"})

	snapshot := agg.Snapshot()

	if snapshot.JobsByType["MAP_FIELDS"] != 2 {
		t.Errorf("Expected MAP_FIELDS count 2, got %d", snapshot.JobsByType["MAP_FIELDS"])
	}
	if snapshot.JobsByType["FILL_FORM"] != 1 {
		t.Errorf("Expected FILL_FORM count 1, got %d", snapshot.JobsByType["FILL_FORM"])
	}
}

func TestAverageDurationComputedCorrectly(t *testing.T) {
	agg := NewAggregator()

	agg.Record(Event{EventType: "job_succeeded", JobType: "MAP_FIELDS", DurationMS: 1000})
	agg.Record(Event{EventType: "job_succeeded", JobType: "MAP_FIELDS", DurationMS: 2000})
	agg.Record(Event{EventType: "job_succeeded", JobType: "MAP_FIELDS", DurationMS: 3000})

	snapshot := agg.Snapshot()

	stats := snapshot.AvgDurationByJobType["MAP_FIELDS"]
	if stats.Avg != 2000 {
		t.Errorf("Expected average duration 2000, got %d", stats.Avg)
	}
	if stats.Total != 6000 {
		t.Errorf("Expected total duration 6000, got %d", stats.Total)
	}
	if stats.Count != 3 {
		t.Errorf("Expected count 3, got %d", stats.Count)
	}
}

func TestWorkerLastSeenUpdated(t *testing.T) {
	agg := NewAggregator()

	agg.Record(Event{EventType: "job_started", WorkerID: "worker-1", CreatedAt: "2026-07-03T10:00:00Z"})
	agg.Record(Event{EventType: "job_succeeded", WorkerID: "worker-1", CreatedAt: "2026-07-03T10:01:00Z"})

	snapshot := agg.Snapshot()

	if snapshot.WorkerLastSeen["worker-1"] != "2026-07-03T10:01:00Z" {
		t.Errorf("Expected worker-1 last seen '2026-07-03T10:01:00Z', got '%s'", snapshot.WorkerLastSeen["worker-1"])
	}
}

func TestJobsByStatusCounts(t *testing.T) {
	agg := NewAggregator()

	agg.Record(Event{EventType: "job_enqueued"})
	agg.Record(Event{EventType: "job_started"})
	agg.Record(Event{EventType: "job_succeeded"})
	agg.Record(Event{EventType: "job_failed"})
	agg.Record(Event{EventType: "job_retry_scheduled"})

	snapshot := agg.Snapshot()

	if snapshot.JobsByStatus["enqueued"] != 1 {
		t.Errorf("Expected enqueued 1, got %d", snapshot.JobsByStatus["enqueued"])
	}
	if snapshot.JobsByStatus["started"] != 1 {
		t.Errorf("Expected started 1, got %d", snapshot.JobsByStatus["started"])
	}
	if snapshot.JobsByStatus["succeeded"] != 1 {
		t.Errorf("Expected succeeded 1, got %d", snapshot.JobsByStatus["succeeded"])
	}
	if snapshot.JobsByStatus["failed"] != 1 {
		t.Errorf("Expected failed 1, got %d", snapshot.JobsByStatus["failed"])
	}
	if snapshot.JobsByStatus["retry_scheduled"] != 1 {
		t.Errorf("Expected retry_scheduled 1, got %d", snapshot.JobsByStatus["retry_scheduled"])
	}
}

func TestRetryCount(t *testing.T) {
	agg := NewAggregator()

	agg.Record(Event{EventType: "job_retry_scheduled"})
	agg.Record(Event{EventType: "job_retry_scheduled"})
	agg.Record(Event{EventType: "job_succeeded"})

	snapshot := agg.Snapshot()

	if snapshot.RetryCount != 2 {
		t.Errorf("Expected retry count 2, got %d", snapshot.RetryCount)
	}
}

func TestEmptySnapshot(t *testing.T) {
	agg := NewAggregator()
	snapshot := agg.Snapshot()

	if snapshot.TotalEvents != 0 {
		t.Errorf("Expected total events 0, got %d", snapshot.TotalEvents)
	}
	if len(snapshot.JobsByStatus) != 0 {
		t.Errorf("Expected empty jobs by status, got %d entries", len(snapshot.JobsByStatus))
	}
	if len(snapshot.JobsByType) != 0 {
		t.Errorf("Expected empty jobs by type, got %d entries", len(snapshot.JobsByType))
	}
	if len(snapshot.WorkerLastSeen) != 0 {
		t.Errorf("Expected empty worker last seen, got %d entries", len(snapshot.WorkerLastSeen))
	}
	if snapshot.RetryCount != 0 {
		t.Errorf("Expected retry count 0, got %d", snapshot.RetryCount)
	}
}