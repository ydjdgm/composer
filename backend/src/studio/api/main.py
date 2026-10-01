import logging
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import JSONResponse

from studio.api.routes import router
from studio.domain.jobs import StudioError
from studio.ports.storage import StorageError
from studio.settings import settings

config = settings()
app = FastAPI(title="Composer Studio", version="0.1.0")
app.include_router(router)


def error_response(request: Request, status: int, code: str, message: str):
    return JSONResponse(status_code=status, content={"error": {
        "code": code, "message": message,
        "request_id": request.scope.get("studio_request_id", str(uuid4()))}})


@app.exception_handler(StudioError)
async def studio_error(request, exc):
    return error_response(request, exc.status, exc.code, exc.message)


@app.exception_handler(StorageError)
async def storage_error(request, exc):
    status = 413 if exc.code == "file_too_large" else 503 if exc.code == "storage_unavailable" else 422
    return error_response(request, status, exc.code, exc.message)


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    return error_response(request, 422, "invalid_request", "요청 값과 필수 항목을 확인하세요.")


@app.exception_handler(HTTPException)
async def http_error(request, exc):
    return error_response(request, exc.status_code, "http_error", str(exc.detail))


@app.exception_handler(SQLAlchemyError)
async def database_error(request, exc):
    logging.getLogger("studio.api").error("request=%s category=%s",
        request.scope.get("studio_request_id"), type(exc).__name__)
    return error_response(request, 503, "database_unavailable", "DB 연결과 migration 적용 여부를 확인하세요.")


@app.exception_handler(Exception)
async def unexpected_error(request, exc):
    logging.getLogger("studio.api").error("request=%s category=%s",
        request.scope.get("studio_request_id"), type(exc).__name__)
    return error_response(request, 500, "internal_error", "요청 처리 중 오류가 발생했습니다.")


class RequestBoundary:
    """Bound bytes before multipart parsing and disallow cross-origin mutations."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        scope["studio_request_id"] = str(uuid4())
        request = Request(scope)
        origin = request.headers.get("origin")
        if scope["method"] not in {"GET", "HEAD", "OPTIONS"} and origin and origin not in config.allowed_origins:
            response = error_response(request, 403, "origin_denied", "허용되지 않은 요청 출처입니다.")
            return await response(scope, receive, send)
        upload = scope["method"] == "POST" and scope["path"].endswith("/references")
        max_bytes = config.max_upload_bytes + 1024 * 1024 if upload else 128 * 1024
        length = request.headers.get("content-length")
        if length:
            try:
                invalid = int(length) < 0 or int(length) > max_bytes
            except ValueError:
                invalid = True
            if invalid:
                response = error_response(request, 413, "request_too_large", "요청 크기 제한을 초과했습니다.")
                return await response(scope, receive, send)
        received = 0

        async def bounded_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > max_bytes:
                    raise HTTPException(413, "요청 크기 제한을 초과했습니다.")
            return message

        await self.app(scope, bounded_receive, send)


app.add_middleware(RequestBoundary)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]"])
app.add_middleware(CORSMiddleware, allow_origins=config.allowed_origins,
                   allow_methods=["GET", "POST", "PATCH"],
                   allow_headers=["Content-Type", "Idempotency-Key"], expose_headers=["Location"])
