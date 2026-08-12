import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mangum import Mangum

from direhire.ai.private_routes import router as private_ai_router
from direhire.analyze.routes import router as analyze_router
from direhire.applications.routes import router as applications_router
from direhire.audit.routes import router as account_router
from direhire.auth.routes import router as auth_router
from direhire.config import get_settings
from direhire.entitlements.routes import router as entitlements_router
from direhire.errors import AppError
from direhire.files.routes import router as files_router
from direhire.inbox.routes import router as inbox_router
from direhire.notifications.routes import router as notifications_router
from direhire.operations.routes import router as operations_router
from direhire.privacy.routes import router as privacy_router
from direhire.profiles.routes import router as profiles_router
from direhire.scheduling.routes import router as scheduling_router
from direhire.sources.routes import router as source_operations_router
from direhire.watches.routes import router as watches_router

settings = get_settings()
app = FastAPI(title="DireHire API", version="0.1.0", docs_url="/api/docs")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "X-CSRF-Token", "X-DireHire-User-ID"],
)


@app.middleware("http")
async def correlation_id(request: Request, call_next: object) -> object:
    request.state.correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    response = await call_next(request)  # type: ignore[operator]
    response.headers["X-Correlation-ID"] = request.state.correlation_id
    return response


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "retryable": exc.retryable,
                "correlation_id": request.state.correlation_id,
            }
        },
    )


@app.get("/api/v1/health", tags=["Operations"])
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(watches_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(account_router, prefix="/api/v1")
app.include_router(entitlements_router, prefix="/api/v1")
app.include_router(inbox_router, prefix="/api/v1")
app.include_router(scheduling_router, prefix="/api/v1")
app.include_router(source_operations_router, prefix="/api/v1")
app.include_router(applications_router, prefix="/api/v1")
app.include_router(notifications_router, prefix="/api/v1")
app.include_router(files_router, prefix="/api/v1")
app.include_router(profiles_router, prefix="/api/v1")
app.include_router(privacy_router, prefix="/api/v1")
app.include_router(private_ai_router, prefix="/api/v1")
app.include_router(analyze_router, prefix="/api/v1")
app.include_router(operations_router, prefix="/api/v1")

# AWS Lambda entry point. Lifespan work is intentionally kept out of cold starts.
handler = Mangum(app, lifespan="off")
