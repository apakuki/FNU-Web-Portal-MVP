import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from src.backend.api.applications import router as applications_router
from src.backend.api.auth import router as auth_router
from src.backend.api.banner import router as banner_router
from src.backend.api.chatbot import router as chatbot_router
from src.backend.api.health import router as health_router
from src.backend.api.payments import router as payments_router
from src.backend.api.registration import router as registration_router
from src.backend.config import settings
from src.backend.rate_limit import limiter

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    is_prod = settings.environment == "production"

    app = FastAPI(
        title="FNU Web Portal API",
        version="0.1.0",
        docs_url=None if is_prod else "/api/docs",
        openapi_url=None if is_prod else "/api/openapi.json",
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
        allow_headers=["Authorization", "Content-Type"],
    )

    if is_prod:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=["portal.fnu.ac.fj", "localhost"])

    app.include_router(health_router, prefix="/api")
    app.include_router(auth_router, prefix="/api")
    app.include_router(banner_router, prefix="/api")
    app.include_router(applications_router, prefix="/api")
    app.include_router(registration_router)
    app.include_router(payments_router)
    app.include_router(chatbot_router)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.backend.main:app", host="0.0.0.0", port=8000, reload=True)
