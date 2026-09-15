"""
Máquina de estados do Job. Isolada para ser testada diretamente
(tests/unit/test_job_state_machine.py) sem depender de mais nada.
"""
from __future__ import annotations

from app.domain.exceptions import InvalidTransitionError
from app.domain.models import Job, JobStatus

# Transições permitidas, conforme o diagrama de workflow do enunciado
# e suporte à retomada de jobs interrompidos (Trilha de Criatividade).
_ALLOWED_TRANSITIONS: dict[JobStatus, set[JobStatus]] = {
    JobStatus.CREATED: {JobStatus.RUNNING},
    JobStatus.RUNNING: {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED},
    JobStatus.COMPLETED: set(),
    JobStatus.FAILED: {JobStatus.RUNNING},      # Permite retomar após falha
    JobStatus.CANCELLED: {JobStatus.RUNNING},   # Permite retomar após cancelamento
}


def can_transition(current: JobStatus, target: JobStatus) -> bool:
    return target in _ALLOWED_TRANSITIONS.get(current, set())


def transition(job: Job, target: JobStatus) -> Job:
    """
    Aplica a transição de estado no job, validando se é permitida.
    Levanta InvalidTransitionError caso contrário.

    Não faz side effects de persistência — quem chama decide se/quando salva.
    """
    if not can_transition(job.status, target):
        raise InvalidTransitionError(
            f"Transição inválida: {job.status} -> {target}"
        )
    job.status = target
    return job
