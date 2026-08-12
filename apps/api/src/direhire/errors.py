from dataclasses import dataclass


@dataclass(slots=True)
class AppError(Exception):
    code: str
    message: str
    status_code: int
    retryable: bool = False


class NotFoundError(AppError):
    def __init__(self, message: str = "The requested resource was not found.") -> None:
        super().__init__("NOT_FOUND", message, 404)


class ConflictError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__("CONFLICT", message, 409)
