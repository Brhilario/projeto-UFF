class DomainError(Exception):
    """Classe base para erros de domínio."""


class InvalidTransitionError(DomainError):
    """Transição de estado do Job não permitida."""


class InvalidFilterParamsError(DomainError):
    """cutoff_hz ou order fora dos limites válidos para o dataset."""


class DatasetNotFoundError(DomainError):
    """dataset_id referenciado não existe."""


class JobNotFoundError(DomainError):
    """job_id referenciado não existe."""


class JobCancelledError(DomainError):
    """Levantada internamente quando o cancel_token é acionado durante run_filter_job."""
