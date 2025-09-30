from __future__ import annotations


class APIError(Exception):
    status_code = 400
    error_code = "bad_request"
    def __init__(self, message: str | None = None, *, error: str | None = None, status: int | None = None):
        super().__init__(message or self.error_code)
        if error:
            self.error_code = error
        if status:
            self.status_code = status
        self.message = message or self.error_code

class ValidationError(APIError):
    status_code = 400
    error_code = "validation_error"

class NotFoundError(APIError):
    status_code = 404
    error_code = "not_found"

class UnauthorizedError(APIError):
    status_code = 401
    error_code = "unauthorized"

class ConflictError(APIError):
    status_code = 409
    error_code = "conflict"

class ForbiddenError(APIError):
    status_code = 403
    error_code = "forbidden"
