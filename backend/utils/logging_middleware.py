"""
Request logging middleware: logs every request's path, method, status,
duration, and (on failure) error detail — both to stdout and to the
RequestLog DB table, satisfying the "log every request / inference time /
errors" requirement.
"""
import time
import logging
import traceback

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from backend.database.db import SessionLocal
from backend.database import crud

logger = logging.getLogger("request_logger")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        error_detail = None
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            status_code = 500
            error_detail = f"{e}\n{traceback.format_exc()}"
            logger.error("Unhandled error on %s %s: %s", request.method, request.url.path, e)
            raise
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.info("%s %s -> %s (%.1fms)", request.method, request.url.path, status_code, duration_ms)
            try:
                db = SessionLocal()
                crud.log_request(
                    db,
                    path=str(request.url.path),
                    method=request.method,
                    status_code=status_code,
                    duration_ms=round(duration_ms, 1),
                    error_detail=error_detail,
                )
                db.close()
            except Exception:
                logger.exception("Failed to write request log to DB")

        return response
