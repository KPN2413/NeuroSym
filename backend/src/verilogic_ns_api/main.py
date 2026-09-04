from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from verilogic_ns_api.api.router import api_router
from verilogic_ns_api.config import Settings, get_settings
from verilogic_ns_api.orchestration.factory import OrchestrationFactory
from verilogic_ns_api.orchestration.jobs import InMemoryJobManager
from verilogic_ns_api.orchestration.models import ApiErrorResponse, ProviderMode
from verilogic_ns_api.research_frontend.catalogue import ResearchCatalogueService
from verilogic_ns_api.research_frontend.models import ResearchApiError


def create_app(
    settings: Settings | None = None,
    *,
    orchestration_factory: OrchestrationFactory | None = None,
    job_manager: InMemoryJobManager | None = None,
    research_catalogue: ResearchCatalogueService | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    resolved_factory = orchestration_factory or OrchestrationFactory(
        provider_mode=ProviderMode(resolved_settings.orchestration_provider_mode)
    )
    resolved_jobs = job_manager or InMemoryJobManager(
        resolved_factory.create_for,
        maximum_queued_jobs=resolved_settings.orchestration_queue_size,
        retention_seconds=resolved_settings.orchestration_retention_seconds,
    )
    resolved_research_catalogue = research_catalogue or ResearchCatalogueService()

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        resolved_jobs.shutdown()
        resolved_factory.close()

    app = FastAPI(
        title=resolved_settings.service_name,
        version=resolved_settings.version,
        description="Local explainable neuro-symbolic reasoning API.",
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings
    app.state.orchestration_factory = resolved_factory
    app.state.job_manager = resolved_jobs
    app.state.research_catalogue = resolved_research_catalogue
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Accept", "Content-Type"],
    )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, _error: RequestValidationError
    ) -> JSONResponse:
        if request.url.path.startswith("/api/v1/neurosymbolic"):
            payload = ApiErrorResponse(
                code="INVALID_REQUEST",
                message="The request does not satisfy the versioned API contract.",
            )
            return JSONResponse(status_code=422, content=payload.model_dump(mode="json"))
        if request.url.path.startswith("/api/v1/research"):
            payload = ResearchApiError(
                code="INVALID_RESEARCH_REQUEST",
                message="The request does not satisfy the versioned research API contract.",
            )
            return JSONResponse(status_code=422, content=payload.model_dump(mode="json"))
        return JSONResponse(status_code=422, content={"detail": "Request validation failed."})

    @app.exception_handler(HTTPException)
    async def api_http_error_handler(request: Request, error: HTTPException) -> JSONResponse:
        if request.url.path.startswith("/api/v1/neurosymbolic"):
            if isinstance(error.detail, dict) and error.detail.get("schema_version") == "1.0":
                content = error.detail
            else:
                content = ApiErrorResponse(
                    code="API_ERROR",
                    message="The API could not complete the request.",
                ).model_dump(mode="json")
            return JSONResponse(status_code=error.status_code, content=content)
        if request.url.path.startswith("/api/v1/research"):
            if isinstance(error.detail, dict) and error.detail.get("schema_version") == "1.0":
                content = error.detail
            else:
                content = ResearchApiError(
                    code="RESEARCH_API_ERROR",
                    message="The research API could not complete the request.",
                ).model_dump(mode="json")
            return JSONResponse(status_code=error.status_code, content=content)
        return JSONResponse(status_code=error.status_code, content={"detail": error.detail})

    app.include_router(api_router)
    return app


app = create_app()
