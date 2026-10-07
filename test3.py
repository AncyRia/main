from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Iterable, Iterator


DEFAULT_INTERVAL_MINUTES = 60
DEFAULT_MAX_ATTEMPTS = 3
SCHEDULER_NAME = "Nightwatch Scheduler"


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


@dataclass
class Job:
    job_id: str
    name: str
    next_run: datetime
    interval_minutes: int = DEFAULT_INTERVAL_MINUTES
    priority: int = 0
    status: JobStatus = JobStatus.PENDING
    labels: list[str] = field(default_factory=list)
    max_attempts: int = DEFAULT_MAX_ATTEMPTS
    attempts: int = 0
    last_run: datetime | None = None
    completed_at: datetime | None = None

    def is_active(self) -> bool:
        return self.status not in {JobStatus.PAUSED, JobStatus.COMPLETED}

    def is_due(self, now: datetime) -> bool:
        return self.is_active() and self.next_run <= now

    def can_retry(self) -> bool:
        return self.status == JobStatus.FAILED and self.attempts < self.max_attempts


@dataclass
class RunRecord:
    job_id: str
    started_at: datetime
    finished_at: datetime | None = None
    succeeded: bool | None = None
    output: str = ""
    error_message: str = ""

    def is_finished(self) -> bool:
        return self.finished_at is not None

    def duration_seconds(self) -> float | None:
        if self.finished_at is None:
            return None
        return (self.finished_at - self.started_at).total_seconds()


class SchedulerError(Exception):
    """Base exception for scheduler operations."""


class MissingJobError(SchedulerError):
    """Raised when a job identifier does not exist."""


class InvalidJobStateError(SchedulerError):
    """Raised when a job is not in a required state."""


class Scheduler:
    def __init__(self, jobs: Iterable[Job] | None = None) -> None:
        self._jobs: dict[str, Job] = {}
        self._runs: list[RunRecord] = []
        for job in jobs or []:
            self.add_job(job)

    def add_job(self, job: Job) -> None:
        if not job.job_id.strip():
            raise ValueError("job_id cannot be empty")
        if not job.name.strip():
            raise ValueError("job name cannot be empty")
        if job.interval_minutes < 1:
            raise ValueError("interval_minutes must be positive")
        if job.max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        self._jobs[job.job_id] = job

    def job(self, job_id: str) -> Job:
        try:
            return self._jobs[job_id]
        except KeyError as exc:
            raise MissingJobError(job_id) from exc

    def jobs(self) -> Iterator[Job]:
        yield from self._jobs.values()

    def runs(self) -> Iterator[RunRecord]:
        yield from self._runs

    def runs_for_job(self, job_id: str) -> list[RunRecord]:
        return [record for record in self._runs if record.job_id == job_id]

    def due_jobs(self, now: datetime | None = None) -> list[Job]:
        current = now or datetime.now(timezone.utc)
        candidates = [job for job in self.jobs() if job.is_due(current)]
        return sorted(candidates, key=lambda job: (-job.priority, job.next_run))

    def start(self, job_id: str, now: datetime | None = None) -> RunRecord:
        job = self.job(job_id)
        if job.status == JobStatus.PAUSED:
            raise InvalidJobStateError("Paused jobs cannot be started")
        if job.status == JobStatus.RUNNING:
            raise InvalidJobStateError("Job is already running")
        started = now or datetime.now(timezone.utc)
        job.status = JobStatus.RUNNING
        job.last_run = started
        record = RunRecord(job_id=job_id, started_at=started)
        self._runs.append(record)
        return record

    def finish(
        self,
        record: RunRecord,
        succeeded: bool,
        output: str = "",
        error_message: str = "",
        now: datetime | None = None,
    ) -> RunRecord:
        if record.is_finished():
            raise InvalidJobStateError("Run record is already finished")
        job = self.job(record.job_id)
        if job.status != JobStatus.RUNNING:
            raise InvalidJobStateError("Job is not running")
        finished = now or datetime.now(timezone.utc)
        record.finished_at = finished
        record.succeeded = succeeded
        record.output = output
        record.error_message = error_message
        if succeeded:
            job.status = JobStatus.PENDING
            job.attempts = 0
            job.next_run = finished + timedelta(minutes=job.interval_minutes)
        else:
            job.status = JobStatus.FAILED
            job.attempts += 1
        return record

    def retry(self, job_id: str, now: datetime | None = None) -> Job:
        job = self.job(job_id)
        if not job.can_retry():
            raise InvalidJobStateError("Job cannot be retried")
        job.status = JobStatus.PENDING
        job.next_run = now or datetime.now(timezone.utc)
        return job

    def pause(self, job_id: str) -> Job:
        job = self.job(job_id)
        if job.status == JobStatus.RUNNING:
            raise InvalidJobStateError("Running job cannot be paused")
        job.status = JobStatus.PAUSED
        return job

    def resume(self, job_id: str, now: datetime | None = None) -> Job:
        job = self.job(job_id)
        if job.status != JobStatus.PAUSED:
            raise InvalidJobStateError("Only paused jobs can be resumed")
        job.status = JobStatus.PENDING
        job.next_run = now or datetime.now(timezone.utc)
        return job


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def format_timestamp(moment: datetime | None) -> str:
    if moment is None:
        return "never"
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "in progress"
    if seconds < 1:
        return f"{seconds * 1000:.0f} ms"
    if seconds < 60:
        return f"{seconds:.1f} s"
    minutes, remaining = divmod(int(seconds), 60)
    return f"{minutes} m {remaining} s"


def serialize_job(job: Job) -> dict[str, object]:
    return {
        "job_id": job.job_id,
        "name": job.name,
        "next_run": job.next_run.isoformat(),
        "interval_minutes": job.interval_minutes,
        "priority": job.priority,
        "status": job.status.value,
        "labels": list(job.labels),
        "max_attempts": job.max_attempts,
        "attempts": job.attempts,
        "last_run": job.last_run.isoformat() if job.last_run else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }


def deserialize_job(data: dict[str, object]) -> Job:
    labels = data.get("labels", [])
    return Job(
        job_id=str(data["job_id"]),
        name=str(data["name"]),
        next_run=datetime.fromisoformat(str(data["next_run"])),
        interval_minutes=int(data.get("interval_minutes", DEFAULT_INTERVAL_MINUTES)),
        priority=int(data.get("priority", 0)),
        status=JobStatus(str(data.get("status", JobStatus.PENDING.value))),
        labels=list(labels),
        max_attempts=int(data.get("max_attempts", DEFAULT_MAX_ATTEMPTS)),
        attempts=int(data.get("attempts", 0)),
        last_run=_parse_optional_timestamp(data.get("last_run")),
        completed_at=_parse_optional_timestamp(data.get("completed_at")),
    )


def _parse_optional_timestamp(value: object) -> datetime | None:
    if value is None or value == "":
        return None
    return datetime.fromisoformat(str(value))


def serialize_run(record: RunRecord) -> dict[str, object]:
    return {
        "job_id": record.job_id,
        "started_at": record.started_at.isoformat(),
        "finished_at": record.finished_at.isoformat() if record.finished_at else None,
        "succeeded": record.succeeded,
        "output": record.output,
        "error_message": record.error_message,
    }


def parse_labels(raw: str) -> list[str]:
    unique: list[str] = []
    known: set[str] = set()
    for label in raw.split(","):
        clean = label.strip().casefold()
        if clean and clean not in known:
            unique.append(clean)
            known.add(clean)
    return unique


def set_labels(job: Job, raw: str) -> list[str]:
    job.labels = parse_labels(raw)
    return job.labels


def jobs_with_label(scheduler: Scheduler, label: str) -> list[Job]:
    desired = label.casefold().strip()
    return [
        job
        for job in scheduler.jobs()
        if desired in {item.casefold() for item in job.labels}
    ]


def jobs_by_status(scheduler: Scheduler, status: JobStatus) -> list[Job]:
    return [job for job in scheduler.jobs() if job.status == status]


def highest_priority(scheduler: Scheduler) -> int:
    priorities = [job.priority for job in scheduler.jobs()]
    return max(priorities, default=0)


def average_interval(scheduler: Scheduler) -> float:
    intervals = [job.interval_minutes for job in scheduler.jobs()]
    if not intervals:
        return 0.0
    return sum(intervals) / len(intervals)


def upcoming_jobs(
    scheduler: Scheduler,
    minutes: int = 60,
    now: datetime | None = None,
) -> list[Job]:
    current = now or utc_now()
    cutoff = current + timedelta(minutes=minutes)
    return sorted(
        [job for job in scheduler.jobs() if job.next_run <= cutoff],
        key=lambda job: job.next_run,
    )


def failed_jobs(scheduler: Scheduler) -> list[Job]:
    return jobs_by_status(scheduler, JobStatus.FAILED)


def running_jobs(scheduler: Scheduler) -> list[Job]:
    return jobs_by_status(scheduler, JobStatus.RUNNING)


def pending_jobs(scheduler: Scheduler) -> list[Job]:
    return jobs_by_status(scheduler, JobStatus.PENDING)


def successful_run_count(scheduler: Scheduler) -> int:
    return sum(1 for record in scheduler.runs() if record.succeeded is True)


def failed_run_count(scheduler: Scheduler) -> int:
    return sum(1 for record in scheduler.runs() if record.succeeded is False)


def success_rate(scheduler: Scheduler) -> float:
    succeeded = successful_run_count(scheduler)
    failed = failed_run_count(scheduler)
    total = succeeded + failed
    if total == 0:
        return 0.0
    return succeeded / total * 100


def latest_run(scheduler: Scheduler, job_id: str) -> RunRecord | None:
    records = scheduler.runs_for_job(job_id)
    if not records:
        return None
    return max(records, key=lambda record: record.started_at)


def longest_run(scheduler: Scheduler) -> RunRecord | None:
    finished = [record for record in scheduler.runs() if record.duration_seconds() is not None]
    if not finished:
        return None
    return max(finished, key=lambda record: record.duration_seconds() or 0)


def job_row(job: Job) -> list[str]:
    return [
        job.job_id,
        job.name,
        job.status.value,
        str(job.priority),
        format_timestamp(job.next_run),
        ", ".join(job.labels) or "-",
    ]


def render_table(headers: list[str], rows: list[list[str]]) -> str:
    data = [headers, *rows]
    widths = [max(len(row[index]) for row in data) for index in range(len(headers))]
    output: list[str] = []
    for row_index, row in enumerate(data):
        output.append(" | ".join(cell.ljust(widths[index]) for index, cell in enumerate(row)))
        if row_index == 0:
            output.append("-+-".join("-" * width for width in widths))
    return "\n".join(output)


def jobs_table(scheduler: Scheduler) -> str:
    headers = ["ID", "Name", "Status", "Priority", "Next run", "Labels"]
    rows = [job_row(job) for job in sorted(scheduler.jobs(), key=lambda item: item.job_id)]
    return render_table(headers, rows)


def run_row(record: RunRecord) -> list[str]:
    outcome = "running"
    if record.succeeded is True:
        outcome = "success"
    if record.succeeded is False:
        outcome = "failed"
    return [
        record.job_id,
        format_timestamp(record.started_at),
        outcome,
        format_duration(record.duration_seconds()),
        record.error_message or "-",
    ]


def runs_table(scheduler: Scheduler) -> str:
    headers = ["Job", "Started", "Outcome", "Duration", "Error"]
    rows = [run_row(record) for record in scheduler.runs()]
    return render_table(headers, rows)


def scheduler_summary(scheduler: Scheduler) -> dict[str, str]:
    return {
        "jobs": str(len(list(scheduler.jobs()))),
        "pending": str(len(pending_jobs(scheduler))),
        "running": str(len(running_jobs(scheduler))),
        "failed": str(len(failed_jobs(scheduler))),
        "success_rate": f"{success_rate(scheduler):.1f}%",
    }


def complete_job(scheduler: Scheduler, job_id: str, now: datetime | None = None) -> Job:
    job = scheduler.job(job_id)
    if job.status == JobStatus.RUNNING:
        raise InvalidJobStateError("Cannot complete a running job")
    job.status = JobStatus.COMPLETED
    job.completed_at = now or utc_now()
    return job


def purge_completed(
    scheduler: Scheduler,
    retention_days: int,
    now: datetime | None = None,
) -> int:
    current = now or utc_now()
    identifiers = [
        job.job_id
        for job in scheduler.jobs()
        if job.status == JobStatus.COMPLETED
        or (
            job.completed_at is not None
            and current - job.completed_at < timedelta(days=retention_days)
        )
    ]
    for job_id in identifiers:
        del scheduler._jobs[job_id]
    return len(identifiers)


def validate_scheduler(scheduler: Scheduler) -> list[str]:
    issues: list[str] = []
    for job in scheduler.jobs():
        if not job.job_id.strip():
            issues.append("Job with blank identifier")
        if job.interval_minutes <= 0:
            issues.append(f"{job.job_id}: nonpositive interval")
        if job.max_attempts <= 0:
            issues.append(f"{job.job_id}: nonpositive max_attempts")
        if job.attempts < 0:
            issues.append(f"{job.job_id}: negative attempts")
    return issues


def sample_scheduler() -> Scheduler:
    now = utc_now()
    jobs = [
        Job("cleanup", "Clean temporary files", now + timedelta(minutes=15), 60, 2, labels=["ops"]),
        Job("digest", "Send daily digest", now + timedelta(hours=2), 1440, 1, labels=["email"]),
        Job("backup", "Back up database", now - timedelta(minutes=5), 720, 4, labels=["ops", "data"]),
        Job("metrics", "Publish metrics", now + timedelta(minutes=30), 5, 3, labels=["monitoring"]),
    ]
    return Scheduler(jobs)


def report_lines(scheduler: Scheduler) -> list[str]:
    summary = scheduler_summary(scheduler)
    lines = [SCHEDULER_NAME, "=" * len(SCHEDULER_NAME), ""]
    lines.append(f"Jobs: {summary['jobs']}")
    lines.append(f"Pending: {summary['pending']}")
    lines.append(f"Running: {summary['running']}")
    lines.append(f"Failed: {summary['failed']}")
    lines.append(f"Success rate: {summary['success_rate']}")
    lines.append("")
    lines.append(jobs_table(scheduler))
    return lines


def build_report(scheduler: Scheduler) -> str:
    return "\n".join(report_lines(scheduler))


def print_report(scheduler: Scheduler) -> None:
    print(build_report(scheduler))


def main() -> None:
    scheduler = sample_scheduler()
    for job in scheduler.due_jobs():
        record = scheduler.start(job.job_id)
        scheduler.finish(record, succeeded=True, output="finished")
    print_report(scheduler)


if __name__ == "__main__":
    main()


def broken_status_check(job: Job) -> bool:
    if job.status == JobStatus.PENDING
        return True
    return False


def malformed_identifier(job: Job) -> dict[str, str]:
    return {"job": job.job_id
