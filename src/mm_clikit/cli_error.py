"""CLI-recoverable error caught by TyperPlus error handler."""


class CliError(Exception):
    """Base exception for CLI errors automatically caught by TyperPlus.

    Subclass in consumer apps for domain-specific errors::

        class PomodoroError(CliError): ...

        raise PomodoroError("Timer not running", error_code="NOT_RUNNING")

    Args:
        message: Human-readable error description (becomes ``str(error)``).
        error_code: Machine-readable error code for JSON output.
        exit_code: Process exit code.

    """

    def __init__(self, message: str, *, error_code: str = "ERROR", exit_code: int = 1) -> None:
        """Initialize with a human-readable message and machine-readable code."""
        super().__init__(message)
        self.error_code = error_code
        self.exit_code = exit_code
