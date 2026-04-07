# context.md §3 — Hexagonal Architecture: zero framework imports in domain layer.
# context.md §10 — HTTP Error Code Mapping (mapped to HTTP in error_handler.py):
#   NotFoundError      → 404  NOT_FOUND
#   PolicyViolation    → 422  POLICY_VIOLATION
#   ValidationError    → 400  VALIDATION_ERROR  (context.md maps to 422 for input; 400 used here)
#   ConflictError      → 409  CONFLICT
#   RateLimitError     → 429  RATE_LIMIT_EXCEEDED
#   BlockchainSimulationError → 502  BLOCKCHAIN_DRY_RUN_FAILED
#   AuthenticationError → 401 UNAUTHORIZED
#   AuthorizationError → 403  FORBIDDEN
#   DomainError (base) → 500  INTERNAL_ERROR


class DomainError(Exception):
    """
    Base domain exception. All business-rule violations derive from this.

    Attributes:
        message:    Human-readable description of the error.
        error_code: Machine-readable snake_case code for API consumers.
    """

    error_code: str = "INTERNAL_ERROR"

    def __init__(self, message: str, error_code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if error_code is not None:
            self.error_code = error_code


class NotFoundError(DomainError):
    """Raised when a requested aggregate or entity does not exist."""

    error_code = "NOT_FOUND"

    def __init__(self, resource: str, identifier: object) -> None:
        super().__init__(f"{resource} not found: {identifier}")
        self.resource = resource
        self.identifier = identifier


class PolicyViolation(DomainError):
    """
    Raised when a business rule or domain policy is violated.
    Examples: offer above budget ceiling, transition in wrong state.
    """

    error_code = "POLICY_VIOLATION"


class ValidationError(DomainError):
    """
    Raised when input data fails domain-level validation.
    Examples: invalid PAN format, HSN code out of range.
    """

    error_code = "VALIDATION_ERROR"

    def __init__(self, message: str, field: str | None = None) -> None:
        super().__init__(message)
        self.field = field


class ConflictError(DomainError):
    """
    Raised when an operation conflicts with existing state.
    Examples: duplicate enterprise registration, escrow already funded.
    """

    error_code = "CONFLICT"


class RateLimitError(DomainError):
    """Raised when a rate limit is exceeded (API or LLM)."""

    error_code = "RATE_LIMIT_EXCEEDED"


class BlockchainSimulationError(DomainError):
    """
    Raised when algod.dryrun() fails before broadcast.
    context.md §12 SRS-SC-001: dry-run failure MUST prevent broadcast.
    """

    error_code = "BLOCKCHAIN_DRY_RUN_FAILED"


class AuthenticationError(DomainError):
    """Raised when authentication fails (missing/invalid/expired token)."""

    error_code = "UNAUTHORIZED"


class AuthorizationError(DomainError):
    """Raised when an authenticated user lacks the required role/permission."""

    error_code = "FORBIDDEN"
