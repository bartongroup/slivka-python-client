import enum


class JobState(enum.Enum):
    PENDING = 'pending'
    "Request was submitted successfully and awaits further processing"
    REJECTED = 'rejected'
    "Request was rejected due to resource limitations"
    ACCEPTED = 'accepted'
    "Request was accepted and is scheduled for execution"
    QUEUED = 'queued'
    "Job was sent to the queuing system and waits for resources to become available"
    RUNNING = 'running'
    "Job is currently running"
    COMPLETED = 'completed'
    "Job has finished its execution successfully"
    INTERRUPTED = 'interrupted'
    "Job was interrupted during execution"
    DELETED = 'deleted'
    "Job was deleted from the queuing system"
    FAILED = 'failed'
    "Job finished with non-zero exit code"
    ERROR = 'error'
    "Job failed to run due to internal error"
    UNKNOWN = 'unknown'
    "Job status can not be determined"
