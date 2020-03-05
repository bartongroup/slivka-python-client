import enum


class JobState(enum.Enum):
    PENDING = 'pending'
    REJECTED = 'rejected'
    ACCEPTED = 'accepted'
    QUEUED = 'queued'
    RUNNING = 'running'
    COMPLETED = 'completed'
    INTERRUPTED = 'interrupted'
    DELETED = 'deleted'
    FAILED = 'failed'
    ERROR = 'error'
    UNKNOWN = 'unknown'

    def is_finished(self):
        return self not in (JobState.PENDING, JobState.ACCEPTED,
                            JobState.QUEUED, JobState.RUNNING)
