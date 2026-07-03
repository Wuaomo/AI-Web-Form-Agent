"""Job type and status constants for the async job scheduler.

These constants define the standard job types that can be queued for
asynchronous execution, and the status values that track job lifecycle.
All values are stable uppercase strings suitable for database storage
and API responses.

Job Types:
    ANALYZE_FORM - Form analysis workflow
    MAP_FIELDS - Field mapping workflow
    FILL_FORM - Form filling workflow
    RUN_BENCHMARK - Benchmark execution

Job Statuses:
    PENDING - Job is queued but not yet picked up
    RUNNING - Job is currently being executed
    SUCCEEDED - Job completed successfully
    FAILED - Job failed
    CANCELLED - Job was cancelled before completion
    RETRY_SCHEDULED - Job failed but is scheduled for retry
"""

JOB_TYPE_ANALYZE_FORM = "ANALYZE_FORM"
JOB_TYPE_MAP_FIELDS = "MAP_FIELDS"
JOB_TYPE_FILL_FORM = "FILL_FORM"
JOB_TYPE_RUN_BENCHMARK = "RUN_BENCHMARK"

JOB_STATUS_PENDING = "PENDING"
JOB_STATUS_RUNNING = "RUNNING"
JOB_STATUS_SUCCEEDED = "SUCCEEDED"
JOB_STATUS_FAILED = "FAILED"
JOB_STATUS_CANCELLED = "CANCELLED"
JOB_STATUS_RETRY_SCHEDULED = "RETRY_SCHEDULED"
