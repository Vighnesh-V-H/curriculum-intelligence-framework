class AppError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


class BadRequestError(AppError):
    def __init__(self, message: str, code: str = "bad_request") -> None:
        super().__init__(400, code, message)


class UnauthorizedError(AppError):
    def __init__(
        self,
        message: str = "Authentication required",
        code: str = "unauthorized",
    ) -> None:
        super().__init__(401, code, message)


class ForbiddenError(AppError):
    def __init__(self, message: str = "Access denied", code: str = "forbidden") -> None:
        super().__init__(403, code, message)


class NotFoundError(AppError):
    def __init__(self, message: str, code: str = "not_found") -> None:
        super().__init__(404, code, message)


class ConflictError(AppError):
    def __init__(self, message: str, code: str = "conflict") -> None:
        super().__init__(409, code, message)


class PayloadTooLargeError(AppError):
    def __init__(self, message: str, code: str = "file_too_large") -> None:
        super().__init__(413, code, message)


class ServiceUnavailableError(AppError):
    def __init__(self, message: str, code: str = "service_unavailable") -> None:
        super().__init__(503, code, message)
