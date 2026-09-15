import pytest

from app.domain.exceptions import InvalidTransitionError
from app.domain.job_state_machine import can_transition, transition
from app.domain.models import Job, JobStatus


def make_job(status: JobStatus = JobStatus.CREATED) -> Job:
    job = Job(dataset_id="ds-1", cutoff_hz=60.0, order=4)
    job.status = status
    return job


@pytest.mark.parametrize(
    "current,target,expected",
    [
        (JobStatus.CREATED, JobStatus.RUNNING, True),
        (JobStatus.RUNNING, JobStatus.COMPLETED, True),
        (JobStatus.RUNNING, JobStatus.FAILED, True),
        (JobStatus.RUNNING, JobStatus.CANCELLED, True),
        (JobStatus.CANCELLED, JobStatus.RUNNING, True),  # Retomada permitida
        (JobStatus.FAILED, JobStatus.RUNNING, True),     # Retomada permitida
        (JobStatus.CREATED, JobStatus.COMPLETED, False),
        (JobStatus.COMPLETED, JobStatus.RUNNING, False), # COMPLETED é terminal
        (JobStatus.CANCELLED, JobStatus.COMPLETED, False),
        (JobStatus.FAILED, JobStatus.COMPLETED, False),
    ],
)
def test_can_transition(current, target, expected):
    assert can_transition(current, target) is expected


def test_transition_applies_valid_change():
    job = make_job(JobStatus.CREATED)
    transition(job, JobStatus.RUNNING)
    assert job.status == JobStatus.RUNNING


def test_transition_applies_resume_from_cancelled():
    job = make_job(JobStatus.CANCELLED)
    transition(job, JobStatus.RUNNING)
    assert job.status == JobStatus.RUNNING


def test_transition_raises_on_invalid_change():
    job = make_job(JobStatus.COMPLETED)
    with pytest.raises(InvalidTransitionError):
        transition(job, JobStatus.RUNNING)


def test_completed_state_has_no_outgoing_transitions():
    job = make_job(JobStatus.COMPLETED)
    for target in JobStatus:
        if target != JobStatus.COMPLETED:
            with pytest.raises(InvalidTransitionError):
                transition(job, target)

