"""Structured API errors."""

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from openrecognition.models.schemas import ErrorBody


class APIError(HTTPException):
    def __init__(self, status_code: int, code: str, message: str, detail=None):
        super().__init__(status_code=status_code, detail=message)
        self.error_code = code
        self.error_detail = detail


def unauthorized(message: str = "Invalid or missing API key") -> APIError:
    return APIError(401, "UNAUTHORIZED", message)


def forbidden(message: str = "Insufficient scope") -> APIError:
    return APIError(403, "FORBIDDEN", message)


def not_found(message: str = "Not found") -> APIError:
    return APIError(404, "NOT_FOUND", message)


def bad_request(code: str, message: str, detail=None) -> APIError:
    return APIError(400, code, message, detail)


def rate_limited(message: str = "Too many login attempts") -> APIError:
    return APIError(429, "RATE_LIMITED", message)


def maintenance() -> APIError:
    return APIError(503, "MAINTENANCE", "Service in maintenance mode")


async def audio_decode_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    body = ErrorBody(
        code="INVALID_MEDIA",
        message=str(exc),
    )
    return JSONResponse(status_code=400, content=body.model_dump())


async def api_error_handler(_request: Request, exc: APIError) -> JSONResponse:
    body = ErrorBody(
        code=getattr(exc, "error_code", "ERROR"),
        message=str(exc.detail),
        detail=getattr(exc, "error_detail", None),
    )
    return JSONResponse(status_code=exc.status_code, content=body.model_dump())


async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    code = "HTTP_ERROR"
    if exc.status_code == 401:
        code = "UNAUTHORIZED"
    elif exc.status_code == 403:
        code = "FORBIDDEN"
    elif exc.status_code == 404:
        code = "NOT_FOUND"
    body = ErrorBody(code=code, message=str(exc.detail))
    return JSONResponse(status_code=exc.status_code, content=body.model_dump())
